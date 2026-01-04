"""Payment model for transaction records."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .enums import PaymentMethod, PaymentProvider, TransactionStatus


class Payment(BaseModel):
    """A payment transaction for a reservation.

    Amounts are stored in EUR cents.
    Supports both mock provider (testing) and Stripe (production).
    """

    model_config = ConfigDict(strict=True)

    payment_id: str = Field(..., description="Unique payment ID")
    reservation_id: str = Field(..., description="Reference to Reservation")
    amount: int = Field(..., ge=0, description="Amount in EUR cents")
    currency: str = Field(default="EUR", description="Currency code")
    status: TransactionStatus = Field(..., description="Transaction status")
    payment_method: PaymentMethod = Field(..., description="Payment method used")
    provider: PaymentProvider = Field(..., description="Payment provider")
    provider_transaction_id: str | None = Field(
        default=None,
        description="External transaction reference (PaymentIntent ID for Stripe)",
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    completed_at: datetime | None = Field(
        default=None, description="Completion timestamp"
    )
    error_message: str | None = Field(
        default=None, description="Error details if failed"
    )

    # Stripe-specific fields (optional for backward compatibility)
    stripe_checkout_session_id: str | None = Field(
        default=None,
        description="Stripe Checkout Session ID (cs_xxx)",
        examples=["cs_test_abc123def456"],
    )
    stripe_payment_intent_id: str | None = Field(
        default=None,
        description="Stripe PaymentIntent ID (pi_xxx) - also stored in provider_transaction_id",
        examples=["pi_3ABC123DEF456"],
    )
    stripe_refund_id: str | None = Field(
        default=None,
        description="Stripe Refund ID (re_xxx) if refunded",
        examples=["re_3ABC123DEF456"],
    )
    refund_amount: int | None = Field(
        default=None,
        ge=0,
        description="Refund amount in EUR cents (if partial or full refund)",
    )
    refunded_at: datetime | None = Field(
        default=None,
        description="Timestamp when refund was processed",
    )


class PaymentCreate(BaseModel):
    """Data required to initiate a payment."""

    model_config = ConfigDict(strict=True)

    reservation_id: str
    amount: int = Field(..., ge=0)
    payment_method: PaymentMethod


class PaymentResult(BaseModel):
    """Result of a payment operation.

    For Stripe Checkout, includes the redirect URL.
    For mock provider, includes transaction status only.
    """

    model_config = ConfigDict(strict=True)

    payment_id: str
    status: TransactionStatus
    provider_transaction_id: str | None = None
    error_message: str | None = None

    # Stripe Checkout redirect URL
    checkout_url: str | None = Field(
        default=None,
        description="Stripe Checkout URL for payment redirect",
        examples=["https://checkout.stripe.com/c/pay/cs_test_abc123"],
    )
    expires_at: datetime | None = Field(
        default=None,
        description="When the checkout session expires (30 minutes)",
    )
