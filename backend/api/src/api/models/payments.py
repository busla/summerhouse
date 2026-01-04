"""API models for payment endpoints.

Extends shared payment models with API-specific request formats.
Includes Stripe Checkout session and refund models.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from shared.models import Payment
from shared.models.enums import PaymentMethod


class PaymentRequest(BaseModel):
    """Request to process a payment.

    Amount is derived from the reservation - not user input.
    """

    model_config = ConfigDict(
        strict=True,
        json_schema_extra={
            "examples": [
                {
                    "reservation_id": "RES-2025-ABC123",
                    "payment_method": "card",
                }
            ]
        },
    )

    reservation_id: str = Field(
        ...,
        description="Reservation ID to pay for",
        examples=["RES-2025-ABC123"],
    )
    payment_method: PaymentMethod = Field(
        ...,
        description="Payment method to use (card, paypal, bank_transfer)",
        examples=["card"],
    )


class PaymentRetryRequest(BaseModel):
    """Request to retry a failed payment via Stripe Checkout.

    Creates a new Stripe Checkout session for retry.
    Success/cancel URLs are optional for API flexibility.
    """

    model_config = ConfigDict(
        strict=True,
        json_schema_extra={
            "examples": [
                {},
                {
                    "success_url": "https://example.com/booking/success?session_id={CHECKOUT_SESSION_ID}",
                    "cancel_url": "https://example.com/booking/cancel",
                },
            ]
        },
    )

    success_url: str | None = Field(
        default=None,
        description="URL to redirect after successful payment",
        examples=[
            "https://example.com/booking/success?session_id={CHECKOUT_SESSION_ID}"
        ],
    )
    cancel_url: str | None = Field(
        default=None,
        description="URL to redirect if payment is cancelled",
        examples=["https://example.com/booking/cancel"],
    )


# --- Stripe Checkout Models ---


class CheckoutSessionRequest(BaseModel):
    """Request to create a Stripe Checkout session.

    Amount is determined by the reservation total - not user-provided.
    Success/cancel URLs are optional for API flexibility.
    """

    model_config = ConfigDict(
        strict=True,
        json_schema_extra={
            "examples": [
                {
                    "reservation_id": "RES-2026-ABC123",
                    "success_url": "https://example.com/booking/success?session_id={CHECKOUT_SESSION_ID}",
                    "cancel_url": "https://example.com/booking/cancel",
                }
            ]
        },
    )

    reservation_id: str = Field(
        ...,
        min_length=1,
        description="Reservation to pay for",
        examples=["RES-2026-ABC123"],
    )
    success_url: str | None = Field(
        default=None,
        description="URL to redirect after successful payment",
        examples=[
            "https://example.com/booking/success?session_id={CHECKOUT_SESSION_ID}"
        ],
    )
    cancel_url: str | None = Field(
        default=None,
        description="URL to redirect if payment is cancelled",
        examples=["https://example.com/booking/cancel"],
    )


class CheckoutSessionResponse(BaseModel):
    """Response from creating a Stripe Checkout session.

    Used for both initial checkout and retry attempts.
    """

    model_config = ConfigDict(
        strict=True,
        json_schema_extra={
            "examples": [
                {
                    "payment_id": "PAY-2026-ABC123",
                    "checkout_session_id": "cs_test_abc123def456",
                    "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_abc123def456",
                    "expires_at": "2026-01-03T10:30:00Z",
                    "amount": 112500,
                    "currency": "EUR",
                    "attempt_number": 1,
                }
            ]
        },
    )

    payment_id: str = Field(
        ...,
        description="Internal payment ID for tracking",
        examples=["PAY-2026-ABC123"],
    )
    checkout_session_id: str = Field(
        ...,
        description="Stripe Checkout Session ID",
        examples=["cs_test_abc123def456"],
    )
    checkout_url: str = Field(
        ...,
        description="URL to redirect user to Stripe Checkout",
        examples=["https://checkout.stripe.com/c/pay/cs_test_abc123"],
    )
    expires_at: datetime = Field(
        ...,
        description="When the checkout session expires",
    )
    amount: int = Field(
        ...,
        ge=0,
        description="Payment amount in EUR cents",
        examples=[112500],
    )
    currency: str = Field(
        default="EUR",
        description="Currency code",
    )
    attempt_number: int | None = Field(
        default=None,
        ge=1,
        le=3,
        description="Payment attempt number (1-3). Present for retry requests.",
        examples=[1, 2, 3],
    )


# --- Refund Models ---


class RefundRequest(BaseModel):
    """Request to initiate a refund for a payment.

    Amount is optional - if not provided, full refund is assumed.
    Reason is optional but recommended for record-keeping.
    """

    model_config = ConfigDict(
        strict=True,
        json_schema_extra={
            "examples": [
                {
                    "amount": 56250,
                    "reason": "Customer cancelled 10 days before check-in (50% refund policy)",
                },
                {"reason": "Customer cancelled 20 days before check-in (full refund)"},
            ]
        },
    )

    amount: int | None = Field(
        default=None,
        ge=0,
        description="Refund amount in EUR cents. If not provided, refunds full amount.",
        examples=[56250],
    )
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Reason for refund",
        examples=["Customer cancelled 10 days before check-in (50% refund policy)"],
    )


class RefundResponse(BaseModel):
    """Response from initiating a refund."""

    model_config = ConfigDict(
        strict=True,
        json_schema_extra={
            "examples": [
                {
                    "payment_id": "PAY-2026-ABC123",
                    "stripe_refund_id": "re_3ABC123DEF456",
                    "amount": 56250,
                    "status": "succeeded",
                    "refunded_at": "2026-01-03T14:30:00Z",
                }
            ]
        },
    )

    payment_id: str = Field(
        ...,
        description="Original payment ID",
    )
    stripe_refund_id: str = Field(
        ...,
        description="Stripe Refund ID",
        examples=["re_3ABC123DEF456"],
    )
    amount: int = Field(
        ...,
        ge=0,
        description="Refunded amount in EUR cents",
    )
    status: str = Field(
        ...,
        description="Refund status: succeeded, pending, failed",
        examples=["succeeded"],
    )
    refunded_at: datetime = Field(
        ...,
        description="When refund was processed",
    )


# --- Payment Status Models ---


class PaymentStatusResponse(BaseModel):
    """Detailed payment status for a reservation.

    Includes full payment history and current state.
    """

    model_config = ConfigDict(
        strict=True,
        json_schema_extra={
            "examples": [
                {
                    "reservation_id": "RES-2026-ABC123",
                    "payment": None,
                    "has_completed_payment": False,
                    "is_refunded": False,
                    "refund_amount": None,
                    "payment_attempts": 0,
                }
            ]
        },
    )

    reservation_id: str
    payment: Payment | None = Field(
        default=None,
        description="Most recent/completed payment record",
    )
    has_completed_payment: bool = Field(
        ...,
        description="Whether a successful payment exists",
    )
    is_refunded: bool = Field(
        default=False,
        description="Whether payment has been refunded",
    )
    refund_amount: int | None = Field(
        default=None,
        description="Refund amount in EUR cents if refunded",
    )
    payment_attempts: int = Field(
        default=0,
        description="Number of payment attempts made",
    )


class PaymentHistoryResponse(BaseModel):
    """Full payment history for a reservation (FR-028 / T028).

    Includes all payment attempts, attempt count, and refund summary.
    """

    model_config = ConfigDict(
        strict=True,
        json_schema_extra={
            "examples": [
                {
                    "reservation_id": "RES-2026-ABC123",
                    "payments": [
                        {
                            "payment_id": "PAY-2026-FAILED1",
                            "status": "failed",
                            "amount": 112500,
                        },
                        {
                            "payment_id": "PAY-2026-SUCCESS",
                            "status": "completed",
                            "amount": 112500,
                        },
                    ],
                    "attempt_count": 2,
                    "has_completed_payment": True,
                    "current_status": "completed",
                    "total_paid": 112500,
                    "total_refunded": 0,
                }
            ]
        },
    )

    reservation_id: str = Field(
        ...,
        description="Reservation ID",
    )
    payments: list[Payment] = Field(
        default_factory=list,
        description="All payment records, ordered by created_at descending",
    )
    attempt_count: int = Field(
        ...,
        ge=0,
        description="Total number of payment attempts (including failed)",
    )
    has_completed_payment: bool = Field(
        ...,
        description="Whether any payment completed successfully",
    )
    current_status: str = Field(
        ...,
        description="Current overall status: pending, completed, refunded, failed",
    )
    total_paid: int = Field(
        default=0,
        ge=0,
        description="Total amount paid in EUR cents (completed payments)",
    )
    total_refunded: int = Field(
        default=0,
        ge=0,
        description="Total amount refunded in EUR cents",
    )
