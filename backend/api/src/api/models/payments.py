"""API models for payment endpoints.

Extends shared payment models with API-specific request formats.
"""

from pydantic import BaseModel, ConfigDict, Field

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
    """Request to retry a failed payment.

    If payment_method is not provided, uses the same method as the original.
    """

    model_config = ConfigDict(
        strict=True,
        json_schema_extra={
            "examples": [
                {"payment_method": "paypal"},
                {},
            ]
        },
    )

    payment_method: PaymentMethod | None = Field(
        default=None,
        description="New payment method (optional, uses original if not provided)",
    )
