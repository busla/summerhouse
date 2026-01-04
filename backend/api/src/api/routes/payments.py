"""Payment endpoints for processing transactions.

Provides REST endpoints for:
- Processing payments for reservations (JWT required)
- Creating Stripe Checkout sessions (JWT required)
- Getting payment status (public)
- Retrying failed payments (JWT required)
- Initiating refunds (JWT required, owner-only)

Integrates with Stripe for real payment processing.
"""

import os
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from shared.utils.logging import get_logger, log_payment_operation

logger = get_logger(__name__)
from starlette.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from api.dependencies import get_booking_service, get_payment_service
from api.models.payments import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    PaymentHistoryResponse,
    PaymentRequest,
    PaymentRetryRequest,
    RefundRequest,
    RefundResponse,
)
from api.security import AuthScope, require_auth, SecurityRequirement
from shared.models.enums import (
    PaymentMethod,
    PaymentProvider,
    ReservationStatus,
    TransactionStatus,
)
from shared.models.errors import BookingError, ErrorCode, get_user_friendly_stripe_message
from shared.models.payment import Payment, PaymentCreate, PaymentResult
from shared.services.booking import BookingService
from shared.services.dynamodb import get_dynamodb_service
from shared.services.payment_service import PaymentService
from shared.services.refund_policy_service import RefundPolicyService
from shared.services.stripe_service import StripeServiceError, get_stripe_service

router = APIRouter(tags=["payments"])


def _get_checkout_redirect_urls() -> tuple[str, str]:
    """Get checkout redirect URLs from environment.

    Returns:
        Tuple of (success_url, cancel_url)
    """
    base_url = os.getenv("FRONTEND_URL", "")
    if not base_url:
        raise ValueError("FRONTEND_URL environment variable not set")

    success_url = f"{base_url}/booking/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base_url}/booking/cancel"
    return success_url, cancel_url


def _convert_to_cents(amount: int | float) -> int:
    """Convert decimal amount to cents for Stripe.

    Args:
        amount: Amount in EUR (e.g., 1125.00 or Decimal("1125.00"))

    Returns:
        Amount in cents as integer (e.g., 112500)
    """
    return int(float(amount) * 100)


def _get_user_customer_id(request: Request) -> str | None:
    """Extract customer_id from request based on JWT sub claim."""
    user_sub = request.headers.get("x-user-sub")
    if not user_sub:
        return None

    db = get_dynamodb_service()
    customer = db.get_customer_by_cognito_sub(user_sub)
    return customer.get("customer_id") if customer else None


@router.post(
    "/payments/checkout-session",
    summary="Create Stripe Checkout session",
    description="""
Create a Stripe Checkout session for a reservation.

**Requires JWT authentication.**
**Only the reservation owner can create a checkout session.**

Returns a Stripe Checkout URL where the user can complete payment.
The payment is recorded as PENDING until confirmed by webhook.

**Notes:**
- Amount is taken from reservation total (not user-provided)
- Session expires after 30 minutes
- Use {CHECKOUT_SESSION_ID} placeholder in success_url for session ID
""",
    response_description="Checkout session details with redirect URL",
    response_model=CheckoutSessionResponse,
    status_code=HTTP_201_CREATED,
    responses={
        201: {
            "description": "Checkout session created successfully",
        },
        400: {
            "description": "Reservation not payable (cancelled or already paid)",
        },
        401: {
            "description": "JWT token required",
        },
        403: {
            "description": "Not authorized to pay for this reservation",
        },
        404: {
            "description": "Reservation not found",
        },
    },
)
async def create_checkout_session(
    request: Request,
    body: CheckoutSessionRequest,
    auth: SecurityRequirement = Depends(require_auth([AuthScope.OPENID])),
    payment_service: PaymentService = Depends(get_payment_service),
    booking_service: BookingService = Depends(get_booking_service),
) -> CheckoutSessionResponse:
    """Create Stripe Checkout session for a reservation.

    Creates a pending payment record and returns Stripe redirect URL.
    Payment confirmation happens via webhook (checkout.session.completed).
    """
    log_payment_operation(
        logger, "create_checkout_session_start", reservation_id=body.reservation_id
    )

    # Verify authentication (x-user-sub header injected by API Gateway)
    customer_id = _get_user_customer_id(request)
    if not customer_id:
        raise BookingError(
            code=ErrorCode.AUTH_REQUIRED,
            details={"message": "Authentication required"},
        )

    # Get reservation
    reservation = booking_service.get_reservation(body.reservation_id)
    if not reservation:
        raise BookingError(
            code=ErrorCode.RESERVATION_NOT_FOUND,
            details={"reservation_id": body.reservation_id},
        )

    # Verify ownership (authorization)
    if reservation.customer_id != customer_id:
        raise BookingError(
            code=ErrorCode.UNAUTHORIZED,
            details={"message": "You can only pay for your own reservations"},
        )

    # Check reservation is payable (pending only)
    if reservation.status == ReservationStatus.CANCELLED:
        raise BookingError(
            code=ErrorCode.RESERVATION_NOT_PAYABLE,
            details={"message": "Cannot pay for cancelled reservations"},
        )

    if reservation.status == ReservationStatus.CONFIRMED:
        raise BookingError(
            code=ErrorCode.RESERVATION_NOT_PAYABLE,
            details={"message": "Reservation is already paid"},
        )

    # total_amount is already stored in cents
    amount_cents = reservation.total_amount

    # Build description for Stripe line item
    description = f"Stay: {reservation.check_in} to {reservation.check_out}"

    # Get customer email for Stripe (optional but helpful)
    customer = booking_service.get_customer(customer_id) if customer_id else None
    customer_email = customer.email if customer else None

    # Use provided URLs or get from environment
    default_success_url, default_cancel_url = _get_checkout_redirect_urls()
    success_url = body.success_url or default_success_url
    cancel_url = body.cancel_url or default_cancel_url

    # Create Stripe Checkout session
    try:
        stripe_service = get_stripe_service()
        stripe_result = stripe_service.create_checkout_session(
            reservation_id=body.reservation_id,
            amount_cents=amount_cents,
            description=description,
            customer_email=customer_email,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"customer_id": customer_id} if customer_id else None,
        )
    except StripeServiceError as e:
        # FR-023: User-friendly error message, FR-024: Log Stripe error code
        user_message = get_user_friendly_stripe_message(e.stripe_error_code)
        logger.error(
            "Stripe checkout session creation failed: %s (stripe_code: %s)",
            str(e),
            e.stripe_error_code,
        )
        raise BookingError(
            code=ErrorCode.PAYMENT_FAILED,
            details={"error": user_message, "stripe_code": e.stripe_error_code or "unknown"},
        )

    # Create pending payment record in DynamoDB
    payment = payment_service.create_pending_stripe_payment(
        reservation_id=body.reservation_id,
        amount_cents=amount_cents,
        checkout_session_id=stripe_result["session_id"],
        payment_intent_id=stripe_result.get("payment_intent_id"),
    )

    log_payment_operation(
        logger,
        "create_checkout_session_success",
        payment_id=payment.payment_id,
        reservation_id=body.reservation_id,
        amount_cents=amount_cents,
        status="pending",
        checkout_session_id=stripe_result["session_id"],
    )

    return CheckoutSessionResponse(
        payment_id=payment.payment_id,
        checkout_session_id=stripe_result["session_id"],
        checkout_url=stripe_result["checkout_url"],
        expires_at=stripe_result["expires_at"],
        amount=amount_cents,
        currency="EUR",
    )


@router.post(
    "/payments",
    summary="Process payment",
    description="""
Process a payment for a reservation.

**Requires JWT authentication.**
**Only the reservation owner can pay.**

The payment amount is determined by the reservation total.
Currently uses a mock provider that always succeeds.

**Notes:**
- Amount is taken from reservation (not user-provided)
- On success, reservation status changes to CONFIRMED
- Supported methods: card, paypal, bank_transfer
""",
    response_description="Payment result with transaction status",
    response_model=PaymentResult,
    status_code=HTTP_201_CREATED,
    responses={
        201: {
            "description": "Payment processed successfully",
        },
        400: {
            "description": "Invalid payment request",
        },
        401: {
            "description": "JWT token required",
        },
        402: {
            "description": "Payment processing failed",
        },
        403: {
            "description": "Not authorized to pay for this reservation",
        },
        404: {
            "description": "Reservation not found",
        },
    },
)
async def process_payment(
    request: Request,
    body: PaymentRequest,
    auth: SecurityRequirement = Depends(require_auth([AuthScope.OPENID])),
    payment_service: PaymentService = Depends(get_payment_service),
    booking_service: BookingService = Depends(get_booking_service),
) -> PaymentResult:
    """Process payment for a reservation.

    Verifies ownership and processes payment.
    """
    # Get reservation
    reservation = booking_service.get_reservation(body.reservation_id)
    if not reservation:
        raise BookingError(
            code=ErrorCode.RESERVATION_NOT_FOUND,
            details={"reservation_id": body.reservation_id},
        )

    # Verify ownership
    customer_id = _get_user_customer_id(request)
    if reservation.customer_id != customer_id:
        raise BookingError(
            code=ErrorCode.UNAUTHORIZED,
            details={"message": "You can only pay for your own reservations"},
        )

    # Check reservation is payable
    if reservation.status == ReservationStatus.CANCELLED:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Cannot pay for cancelled reservations",
        )

    if reservation.status == ReservationStatus.CONFIRMED:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Reservation is already paid",
        )

    # Process payment
    payment_data = PaymentCreate(
        reservation_id=body.reservation_id,
        amount=reservation.total_amount,
        payment_method=body.payment_method,
    )

    result = payment_service.process_payment(payment_data)

    # If successful, confirm the reservation
    if result.status == TransactionStatus.COMPLETED:
        booking_service.confirm_reservation(body.reservation_id)

    # If failed, raise payment error
    if result.status == TransactionStatus.FAILED:
        raise BookingError(
            code=ErrorCode.PAYMENT_FAILED,
            details={"error": result.error_message or "Unknown payment error"},
        )

    return result


@router.get(
    "/payments/{reservation_id}",
    summary="Get payment status",
    description="""
Get payment status for a reservation.

**Public endpoint** - no authentication required.
Returns the most recent payment for the reservation.

**Notes:**
- Returns 404 if no payments found
- Amounts are in EUR cents
""",
    response_description="Payment details",
    response_model=Payment,
    responses={
        200: {
            "description": "Payment found",
        },
        404: {
            "description": "No payment found for reservation",
        },
    },
)
async def get_payment_status(
    reservation_id: str,
    payment_service: PaymentService = Depends(get_payment_service),
) -> Payment:
    """Get payment for a reservation.

    Returns the most recent payment record.
    """
    payments = payment_service.get_payments_for_reservation(reservation_id)

    if not payments:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"No payment found for reservation {reservation_id}",
        )

    # Return most recent (completed) payment, or most recent overall
    completed = [p for p in payments if p.status == TransactionStatus.COMPLETED]
    return completed[0] if completed else payments[0]


@router.get(
    "/payments/{reservation_id}/history",
    summary="Get payment history",
    description="""
Get full payment history for a reservation.

**Public endpoint** - no authentication required.
Returns all payment attempts with aggregate statistics.

**Notes:**
- Includes failed, pending, and completed payments
- Shows attempt count and refund summary
- Amounts are in EUR cents
""",
    response_description="Payment history with all attempts and statistics",
    response_model=PaymentHistoryResponse,
    responses={
        200: {
            "description": "Payment history retrieved",
        },
    },
)
async def get_payment_history(
    reservation_id: str,
    payment_service: PaymentService = Depends(get_payment_service),
) -> PaymentHistoryResponse:
    """Get full payment history for a reservation.

    Returns all payments with aggregate statistics including:
    - All payment attempts (failed, pending, completed)
    - Total attempt count
    - Current overall status
    - Total paid and refunded amounts
    """
    payments = payment_service.get_payments_for_reservation(reservation_id)

    # Calculate aggregates
    attempt_count = len(payments)
    completed_payments = [p for p in payments if p.status == TransactionStatus.COMPLETED]
    refunded_payments = [p for p in payments if p.status == TransactionStatus.REFUNDED]
    has_completed = len(completed_payments) > 0

    # Calculate totals (amounts in cents)
    total_paid = sum(p.amount for p in completed_payments)
    total_refunded = sum(p.refund_amount or 0 for p in refunded_payments)

    # Determine current status
    if refunded_payments:
        current_status = "refunded"
    elif completed_payments:
        current_status = "completed"
    elif any(p.status == TransactionStatus.PENDING for p in payments):
        current_status = "pending"
    elif payments:
        current_status = "failed"
    else:
        current_status = "pending"  # No payments yet

    return PaymentHistoryResponse(
        reservation_id=reservation_id,
        payments=payments,
        attempt_count=attempt_count,
        has_completed_payment=has_completed,
        current_status=current_status,
        total_paid=total_paid,
        total_refunded=total_refunded,
    )


@router.post(
    "/payments/{reservation_id}/retry",
    summary="Retry failed payment",
    description="""
Retry a failed payment for a reservation via Stripe Checkout.

**Requires JWT authentication.**
**Only the reservation owner can retry.**

Creates a new Stripe Checkout session for the retry attempt.
Maximum 3 payment attempts allowed per reservation (FR-025).

**Notes:**
- Only works if reservation is still pending
- Requires at least one previous failed/pending payment
- Returns 400 if max attempts (3) exceeded
- Returns attempt_number (1-3) in response
""",
    response_description="Checkout session details with redirect URL",
    response_model=CheckoutSessionResponse,
    status_code=HTTP_200_OK,
    responses={
        200: {
            "description": "Retry checkout session created",
        },
        400: {
            "description": "Invalid retry (no previous payment, max attempts exceeded, or reservation not pending)",
        },
        401: {
            "description": "JWT token required",
        },
        403: {
            "description": "Not authorized",
        },
        404: {
            "description": "Reservation not found",
        },
    },
)
async def retry_payment(
    request: Request,
    reservation_id: str,
    body: PaymentRetryRequest,
    auth: SecurityRequirement = Depends(require_auth([AuthScope.OPENID])),
    payment_service: PaymentService = Depends(get_payment_service),
    booking_service: BookingService = Depends(get_booking_service),
) -> CheckoutSessionResponse:
    """Retry a failed payment via Stripe Checkout.

    Creates a new Checkout session and returns the URL for retry.
    Enforces max 3 attempts per reservation (FR-025).
    """
    MAX_PAYMENT_ATTEMPTS = 3

    log_payment_operation(
        logger, "retry_payment_start", reservation_id=reservation_id
    )

    # Get reservation
    reservation = booking_service.get_reservation(reservation_id)
    if not reservation:
        raise BookingError(
            code=ErrorCode.RESERVATION_NOT_FOUND,
            details={"reservation_id": reservation_id},
        )

    # Verify ownership
    customer_id = _get_user_customer_id(request)
    if reservation.customer_id != customer_id:
        raise BookingError(
            code=ErrorCode.UNAUTHORIZED,
            details={"message": "You can only retry payments for your own reservations"},
        )

    # Check reservation is still payable
    if reservation.status == ReservationStatus.CONFIRMED:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Reservation is already paid",
        )

    if reservation.status == ReservationStatus.CANCELLED:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Cannot pay for cancelled reservations",
        )

    # Get previous payments to check attempt count and verify retry is valid
    previous_payments = payment_service.get_payments_for_reservation(reservation_id)
    attempt_count = len(previous_payments)

    # Must have at least one previous payment to retry
    if attempt_count == 0:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="No previous payment found. Use POST /payments/checkout-session instead.",
        )

    # Check max attempts (FR-025)
    if attempt_count >= MAX_PAYMENT_ATTEMPTS:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_PAYMENT_ATTEMPTS} payment attempts exceeded. Please contact support.",
        )

    # Calculate next attempt number
    attempt_number = attempt_count + 1

    # total_amount is already stored in cents
    amount_cents = reservation.total_amount

    # Build description for Stripe line item
    description = f"Stay: {reservation.check_in} to {reservation.check_out} (Attempt {attempt_number})"

    # Get customer email for Stripe
    db = get_dynamodb_service()
    customer = db.get_item("customers", {"customer_id": customer_id}) if customer_id else None
    customer_email = customer.get("email") if customer else None

    # Use provided URLs or get from environment
    default_success_url, default_cancel_url = _get_checkout_redirect_urls()
    success_url = body.success_url or default_success_url
    cancel_url = body.cancel_url or default_cancel_url

    # Create Stripe Checkout session
    try:
        stripe_service = get_stripe_service()
        stripe_result = stripe_service.create_checkout_session(
            reservation_id=reservation_id,
            amount_cents=amount_cents,
            description=description,
            customer_email=customer_email,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "customer_id": customer_id,
                "attempt_number": str(attempt_number),
            } if customer_id else {"attempt_number": str(attempt_number)},
        )
    except StripeServiceError as e:
        # FR-023: User-friendly error message, FR-024: Log Stripe error code
        user_message = get_user_friendly_stripe_message(e.stripe_error_code)
        logger.error(
            "Stripe retry checkout session creation failed: %s (stripe_code: %s)",
            str(e),
            e.stripe_error_code,
        )
        raise BookingError(
            code=ErrorCode.PAYMENT_FAILED,
            details={"error": user_message, "stripe_code": e.stripe_error_code or "unknown"},
        )

    # Create pending payment record in DynamoDB
    payment = payment_service.create_pending_stripe_payment(
        reservation_id=reservation_id,
        amount_cents=amount_cents,
        checkout_session_id=stripe_result["session_id"],
        payment_intent_id=stripe_result.get("payment_intent_id"),
    )

    log_payment_operation(
        logger,
        "retry_payment_success",
        payment_id=payment.payment_id,
        reservation_id=reservation_id,
        attempt_number=attempt_number,
        amount_cents=amount_cents,
        checkout_session_id=stripe_result["session_id"],
    )

    return CheckoutSessionResponse(
        payment_id=payment.payment_id,
        checkout_session_id=stripe_result["session_id"],
        checkout_url=stripe_result["checkout_url"],
        expires_at=stripe_result["expires_at"],
        amount=amount_cents,
        currency="EUR",
        attempt_number=attempt_number,
    )


@router.post(
    "/payments/refund/{payment_id}",
    summary="Initiate refund",
    description="""
Initiate a refund for a completed payment.

**Requires JWT authentication.**
**Only the reservation owner can request a refund.**

Refund amount is calculated based on cancellation policy:
- 14+ days before check-in: Full refund (100%)
- 7-13 days before check-in: Partial refund (50%)
- Less than 7 days before check-in: No refund

**Notes:**
- Only Stripe payments can be refunded
- Payment must be in "completed" status
- Each payment can only be refunded once
- Route uses `/payments/refund/{payment_id}` to avoid API Gateway path conflicts
""",
    response_description="Refund details including Stripe refund ID",
    response_model=RefundResponse,
    status_code=HTTP_200_OK,
    responses={
        200: {
            "description": "Refund processed successfully",
        },
        400: {
            "description": "Cannot refund (wrong status, already refunded, no Stripe ID, or policy forbids)",
        },
        401: {
            "description": "JWT token required",
        },
        403: {
            "description": "Not authorized to refund this payment",
        },
        404: {
            "description": "Payment not found",
        },
    },
)
async def initiate_refund(
    request: Request,
    payment_id: str,
    body: RefundRequest,
    auth: SecurityRequirement = Depends(require_auth([AuthScope.OPENID])),
    payment_service: PaymentService = Depends(get_payment_service),
    booking_service: BookingService = Depends(get_booking_service),
) -> RefundResponse:
    """Initiate refund for a completed payment.

    Applies refund policy based on check-in date and processes via Stripe.
    """
    log_payment_operation(logger, "initiate_refund_start", payment_id=payment_id)

    # Get payment
    payment = payment_service.get_payment(payment_id)
    if not payment:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"Payment {payment_id} not found",
        )

    # Verify ownership via reservation
    reservation = booking_service.get_reservation(payment.reservation_id)
    if not reservation:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"Reservation {payment.reservation_id} not found",
        )

    customer_id = _get_user_customer_id(request)
    if reservation.customer_id != customer_id:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="You can only refund payments for your own reservations",
        )

    # Validate payment status
    if payment.status == TransactionStatus.PENDING:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Cannot refund a payment that is not completed",
        )

    if payment.status == TransactionStatus.REFUNDED:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Payment has already been refunded",
        )

    # Require Stripe payment intent for refund
    if not payment.stripe_payment_intent_id:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Cannot refund: payment does not have a Stripe PaymentIntent",
        )

    # Calculate refund amount based on policy
    refund_policy = RefundPolicyService()
    check_in_date = reservation.check_in  # Already a date object
    cancellation_date = date.today()

    refund_calc = refund_policy.calculate_refund_amount(
        payment_amount=payment.amount,
        check_in_date=check_in_date,
        cancellation_date=cancellation_date,
    )

    # If policy forbids refund, return error
    if refund_calc["refund_amount"] == 0:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"No refund allowed per policy: {refund_calc['description']}",
        )

    # Process refund via Stripe
    try:
        stripe_service = get_stripe_service()
        stripe_result = stripe_service.create_refund(
            payment_intent_id=payment.stripe_payment_intent_id,
            amount_cents=refund_calc["refund_amount"],
            reason=body.reason,
        )
    except StripeServiceError as e:
        # FR-023: User-friendly error message, FR-024: Log Stripe error code
        user_message = get_user_friendly_stripe_message(e.stripe_error_code)
        logger.error(
            "Stripe refund failed: %s (stripe_code: %s)",
            str(e),
            e.stripe_error_code,
        )
        raise BookingError(
            code=ErrorCode.PAYMENT_FAILED,
            details={"error": user_message, "stripe_code": e.stripe_error_code or "unknown"},
        )

    # Update payment record
    refunded_at = datetime.now(timezone.utc)
    payment_service.update_payment_refund(
        payment_id=payment_id,
        refund_amount=stripe_result["amount"],
        stripe_refund_id=stripe_result["refund_id"],
        refunded_at=refunded_at,
    )

    log_payment_operation(
        logger,
        "initiate_refund_success",
        payment_id=payment_id,
        refund_amount=stripe_result["amount"],
        stripe_refund_id=stripe_result["refund_id"],
        policy_tier=refund_calc["policy_tier"],
    )

    return RefundResponse(
        payment_id=payment_id,
        stripe_refund_id=stripe_result["refund_id"],
        amount=stripe_result["amount"],
        status=stripe_result["status"],
        refunded_at=refunded_at,
    )
