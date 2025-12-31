"""Payment endpoints for processing transactions.

Provides REST endpoints for:
- Processing payments for reservations (JWT required)
- Getting payment status (public)
- Retrying failed payments (JWT required)

Currently uses a mock payment provider that always succeeds.
In production, integrate with Stripe, PayPal, etc.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from api.dependencies import get_booking_service, get_payment_service
from api.models.payments import PaymentRequest, PaymentRetryRequest
from api.security import AuthScope, require_auth, SecurityRequirement
from shared.models.enums import ReservationStatus, TransactionStatus
from shared.models.errors import BookingError, ErrorCode
from shared.models.payment import Payment, PaymentCreate, PaymentResult
from shared.services.booking import BookingService
from shared.services.dynamodb import get_dynamodb_service
from shared.services.payment_service import PaymentService

router = APIRouter(tags=["payments"])


def _get_user_guest_id(request: Request) -> str | None:
    """Extract guest_id from request based on JWT sub claim."""
    user_sub = request.headers.get("x-user-sub")
    if not user_sub:
        return None

    db = get_dynamodb_service()
    guest = db.get_guest_by_cognito_sub(user_sub)
    return guest.get("guest_id") if guest else None


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
    guest_id = _get_user_guest_id(request)
    if reservation.guest_id != guest_id:
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


@router.post(
    "/payments/{reservation_id}/retry",
    summary="Retry failed payment",
    description="""
Retry a failed payment for a reservation.

**Requires JWT authentication.**
**Only the reservation owner can retry.**

Allows retrying with the same or different payment method.

**Notes:**
- Only works if reservation is still pending
- Can optionally use a different payment method
""",
    response_description="New payment result",
    response_model=PaymentResult,
    responses={
        200: {
            "description": "Retry processed",
        },
        400: {
            "description": "Invalid retry request (no failed payment to retry)",
        },
        401: {
            "description": "JWT token required",
        },
        402: {
            "description": "Payment failed again",
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
) -> PaymentResult:
    """Retry a failed payment.

    Uses same or different payment method.
    """
    # Get reservation
    reservation = booking_service.get_reservation(reservation_id)
    if not reservation:
        raise BookingError(
            code=ErrorCode.RESERVATION_NOT_FOUND,
            details={"reservation_id": reservation_id},
        )

    # Verify ownership
    guest_id = _get_user_guest_id(request)
    if reservation.guest_id != guest_id:
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

    # Get previous payment to determine method
    previous_payments = payment_service.get_payments_for_reservation(reservation_id)
    failed_payment = next(
        (p for p in previous_payments if p.status == TransactionStatus.FAILED),
        None,
    )

    # Determine payment method
    payment_method = body.payment_method
    if not payment_method:
        if failed_payment:
            payment_method = failed_payment.payment_method
        else:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="No previous payment found. Use POST /api/payments instead.",
            )

    # Process new payment
    payment_data = PaymentCreate(
        reservation_id=reservation_id,
        amount=reservation.total_amount,
        payment_method=payment_method,
    )

    result = payment_service.process_payment(payment_data)

    # If successful, confirm the reservation
    if result.status == TransactionStatus.COMPLETED:
        booking_service.confirm_reservation(reservation_id)

    # If failed, raise payment error
    if result.status == TransactionStatus.FAILED:
        raise BookingError(
            code=ErrorCode.PAYMENT_FAILED,
            details={"error": result.error_message or "Unknown payment error"},
        )

    return result
