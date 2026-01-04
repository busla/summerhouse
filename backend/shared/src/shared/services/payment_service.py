"""Payment service for processing transactions.

This service handles payment processing for reservations.
Currently implements a mock payment provider that always succeeds.
In production, integrate with Stripe, PayPal, etc.
"""

import datetime as dt
import uuid
from typing import TYPE_CHECKING, Any

from shared.models import (
    Payment,
    PaymentCreate,
    PaymentMethod,
    PaymentProvider,
    PaymentResult,
    PaymentStatus,
    ReservationStatus,
    TransactionStatus,
)

if TYPE_CHECKING:
    from .dynamodb import DynamoDBService


class PaymentService:
    """Service for processing payments and managing transactions."""

    PAYMENTS_TABLE = "payments"
    RESERVATIONS_TABLE = "reservations"

    def __init__(self, db: "DynamoDBService") -> None:
        """Initialize payment service.

        Args:
            db: DynamoDB service instance
        """
        self.db = db

    def _generate_payment_id(self, prefix: str = "TXN") -> str:
        """Generate a unique payment/transaction ID.

        Args:
            prefix: ID prefix (TXN for mock, PAY for Stripe)

        Returns:
            Unique ID like TXN-ABC123DEF456 or PAY-ABC123DEF456
        """
        return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"

    def create_pending_stripe_payment(
        self,
        reservation_id: str,
        amount_cents: int,
        checkout_session_id: str,
        payment_intent_id: str | None = None,
    ) -> Payment:
        """Create a pending payment record for Stripe Checkout.

        This is called when creating a Stripe Checkout session. The payment
        starts in PENDING status and will be updated to COMPLETED by the
        webhook handler when Stripe confirms the payment.

        Args:
            reservation_id: Reservation being paid for
            amount_cents: Payment amount in EUR cents
            checkout_session_id: Stripe Checkout Session ID
            payment_intent_id: Stripe PaymentIntent ID (if available)

        Returns:
            Created Payment record with PENDING status
        """
        payment_id = self._generate_payment_id(prefix="PAY")
        now = dt.datetime.now(dt.UTC)

        payment = Payment(
            payment_id=payment_id,
            reservation_id=reservation_id,
            amount=amount_cents,
            currency="EUR",
            status=TransactionStatus.PENDING,
            payment_method=PaymentMethod.CARD,  # Stripe Checkout is card-based
            provider=PaymentProvider.STRIPE,
            provider_transaction_id=checkout_session_id,
            created_at=now,
            completed_at=None,  # Set by webhook when payment completes
        )

        # Store payment record
        self.db.put_item(self.PAYMENTS_TABLE, self._payment_to_item(payment))

        return payment

    def process_payment(
        self,
        data: PaymentCreate,
    ) -> PaymentResult:
        """Process a payment for a reservation.

        This is a mock implementation that always succeeds.
        In production, this would integrate with Stripe, PayPal, etc.

        Args:
            data: Payment creation data

        Returns:
            PaymentResult with status and transaction info
        """
        # Generate payment ID
        payment_id = self._generate_payment_id()
        now = dt.datetime.now(dt.UTC)

        # MOCK: Simulate payment processing
        # In production, call Stripe/PayPal API here
        payment_success = True

        if not payment_success:
            # Handle payment failure (won't happen in mock)
            return PaymentResult(
                payment_id=payment_id,
                status=TransactionStatus.FAILED,
                error_message="Payment processing failed. Please try again.",
            )

        # Create payment record
        payment = Payment(
            payment_id=payment_id,
            reservation_id=data.reservation_id,
            amount=data.amount,
            currency="EUR",
            status=TransactionStatus.COMPLETED,
            payment_method=data.payment_method,
            provider=PaymentProvider.MOCK,
            provider_transaction_id=f"MOCK-{uuid.uuid4().hex[:8]}",
            created_at=now,
            completed_at=now,
        )

        # Store payment record
        self.db.put_item(self.PAYMENTS_TABLE, self._payment_to_item(payment))

        return PaymentResult(
            payment_id=payment_id,
            status=TransactionStatus.COMPLETED,
            provider_transaction_id=payment.provider_transaction_id,
        )

    def get_payment(self, payment_id: str) -> Payment | None:
        """Get a payment by ID.

        Args:
            payment_id: Payment/transaction ID

        Returns:
            Payment object or None if not found
        """
        item = self.db.get_item(self.PAYMENTS_TABLE, {"payment_id": payment_id})
        return self._item_to_payment(item) if item else None

    def get_payments_for_reservation(self, reservation_id: str) -> list[Payment]:
        """Get all payments for a reservation.

        Args:
            reservation_id: Reservation ID

        Returns:
            List of Payment objects
        """
        items = self.db.query_by_gsi(
            self.PAYMENTS_TABLE,
            "reservation-index",
            "reservation_id",
            reservation_id,
        )
        return [self._item_to_payment(item) for item in items]

    def process_refund(
        self,
        payment_id: str,
        amount: int,
        reason: str | None = None,
    ) -> PaymentResult:
        """Process a refund for an existing payment.

        Args:
            payment_id: Original payment ID
            amount: Amount to refund in cents
            reason: Optional refund reason

        Returns:
            PaymentResult with refund status
        """
        original = self.get_payment(payment_id)
        if not original:
            return PaymentResult(
                payment_id=payment_id,
                status=TransactionStatus.FAILED,
                error_message="Original payment not found.",
            )

        if original.status != TransactionStatus.COMPLETED:
            return PaymentResult(
                payment_id=payment_id,
                status=TransactionStatus.FAILED,
                error_message="Can only refund completed payments.",
            )

        if amount > original.amount:
            return PaymentResult(
                payment_id=payment_id,
                status=TransactionStatus.FAILED,
                error_message=f"Refund amount ({amount}) exceeds payment ({original.amount}).",
            )

        # Generate refund payment ID
        refund_id = self._generate_payment_id()
        now = dt.datetime.now(dt.UTC)

        # MOCK: Simulate refund processing
        # In production, call provider's refund API
        refund_success = True

        if not refund_success:
            return PaymentResult(
                payment_id=refund_id,
                status=TransactionStatus.FAILED,
                error_message="Refund processing failed.",
            )

        # Create refund record (negative amount convention)
        refund = Payment(
            payment_id=refund_id,
            reservation_id=original.reservation_id,
            amount=-amount,  # Negative for refund
            currency="EUR",
            status=TransactionStatus.COMPLETED,
            payment_method=original.payment_method,
            provider=PaymentProvider.MOCK,
            provider_transaction_id=f"MOCK-REFUND-{uuid.uuid4().hex[:8]}",
            created_at=now,
            completed_at=now,
        )

        self.db.put_item(self.PAYMENTS_TABLE, self._payment_to_item(refund))

        # Update original payment to link refund
        self.db.update_item(
            self.PAYMENTS_TABLE,
            {"payment_id": payment_id},
            "SET refund_id = :rid, updated_at = :now",
            {":rid": refund_id, ":now": now.isoformat()},
        )

        return PaymentResult(
            payment_id=refund_id,
            status=TransactionStatus.COMPLETED,
            provider_transaction_id=refund.provider_transaction_id,
        )

    def validate_payment_method(self, method: str) -> tuple[bool, PaymentMethod | None]:
        """Validate a payment method string.

        Args:
            method: Payment method string (e.g., 'card', 'paypal')

        Returns:
            Tuple of (is_valid, PaymentMethod or None)
        """
        try:
            return True, PaymentMethod(method)
        except ValueError:
            return False, None

    def get_supported_methods(self) -> list[str]:
        """Get list of supported payment methods.

        Returns:
            List of payment method values
        """
        return [m.value for m in PaymentMethod]

    # Conversion helpers

    def update_payment_refund(
        self,
        payment_id: str,
        refund_amount: int,
        stripe_refund_id: str,
        refunded_at: dt.datetime,
    ) -> None:
        """Update payment record with refund details.

        Updates the payment status to REFUNDED and stores refund metadata.

        Args:
            payment_id: Payment ID to update
            refund_amount: Refund amount in cents
            stripe_refund_id: Stripe Refund ID (e.g., re_xxx)
            refunded_at: Timestamp of refund
        """
        self.db.update_item(
            self.PAYMENTS_TABLE,
            {"payment_id": payment_id},
            "SET #status = :status, refund_amount = :amount, stripe_refund_id = :rid, refunded_at = :rat",
            {
                ":status": TransactionStatus.REFUNDED.value,
                ":amount": refund_amount,
                ":rid": stripe_refund_id,
                ":rat": refunded_at.isoformat(),
            },
            {"#status": "status"},  # status is a reserved word
        )

    def _payment_to_item(self, payment: Payment) -> dict[str, Any]:
        """Convert Payment model to DynamoDB item."""
        item: dict[str, Any] = {
            "payment_id": payment.payment_id,
            "reservation_id": payment.reservation_id,
            "amount": payment.amount,
            "currency": payment.currency,
            "status": payment.status.value,
            "payment_method": payment.payment_method.value,
            "provider": payment.provider.value,
            "created_at": payment.created_at.isoformat(),
        }
        if payment.provider_transaction_id:
            item["provider_transaction_id"] = payment.provider_transaction_id
        if payment.completed_at:
            item["completed_at"] = payment.completed_at.isoformat()
        if payment.error_message:
            item["error_message"] = payment.error_message
        # Stripe-specific fields
        if payment.stripe_checkout_session_id:
            item["stripe_checkout_session_id"] = payment.stripe_checkout_session_id
        if payment.stripe_payment_intent_id:
            item["stripe_payment_intent_id"] = payment.stripe_payment_intent_id
        if payment.stripe_refund_id:
            item["stripe_refund_id"] = payment.stripe_refund_id
        if payment.refund_amount is not None:
            item["refund_amount"] = payment.refund_amount
        if payment.refunded_at:
            item["refunded_at"] = payment.refunded_at.isoformat()
        return item

    def _item_to_payment(self, item: dict[str, Any]) -> Payment:
        """Convert DynamoDB item to Payment model.

        Maps all fields including Stripe-specific fields for FR-028.
        """
        return Payment(
            payment_id=item["payment_id"],
            reservation_id=item["reservation_id"],
            amount=int(item["amount"]),
            currency=item.get("currency", "EUR"),
            status=TransactionStatus(item["status"]),
            payment_method=PaymentMethod(item["payment_method"]),
            provider=PaymentProvider(item["provider"]),
            provider_transaction_id=item.get("provider_transaction_id"),
            created_at=dt.datetime.fromisoformat(item["created_at"]),
            completed_at=(
                dt.datetime.fromisoformat(item["completed_at"])
                if item.get("completed_at")
                else None
            ),
            error_message=item.get("error_message"),
            # Stripe-specific fields (FR-028)
            stripe_checkout_session_id=item.get("stripe_checkout_session_id"),
            stripe_payment_intent_id=item.get("stripe_payment_intent_id"),
            stripe_refund_id=item.get("stripe_refund_id"),
            refund_amount=(
                int(item["refund_amount"]) if item.get("refund_amount") else None
            ),
            refunded_at=(
                dt.datetime.fromisoformat(item["refunded_at"])
                if item.get("refunded_at")
                else None
            ),
        )
