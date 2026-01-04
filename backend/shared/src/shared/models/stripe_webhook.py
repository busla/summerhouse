"""Stripe webhook event model for idempotency and auditing."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StripeWebhookEvent(BaseModel):
    """Log of a received Stripe webhook event.

    Used for:
    - Idempotency: prevent processing same event twice
    - Auditing: track all webhook deliveries
    - Debugging: investigate payment issues
    """

    model_config = ConfigDict(strict=True)

    event_id: str = Field(
        ...,
        description="Stripe event ID (evt_xxx)",
        examples=["evt_1ABC123DEF456"],
    )
    event_type: str = Field(
        ...,
        description="Stripe event type",
        examples=["checkout.session.completed", "charge.refunded"],
    )
    processed_at: datetime = Field(
        ...,
        description="When the event was processed",
    )
    payload_hash: str = Field(
        ...,
        description="SHA-256 hash of payload for deduplication",
        examples=["a1b2c3d4e5f6..."],
    )
    reservation_id: str | None = Field(
        default=None,
        description="Associated reservation ID from metadata",
    )
    payment_id: str | None = Field(
        default=None,
        description="Associated payment ID if created/updated",
    )
    processing_result: str = Field(
        default="success",
        description="Result of processing: success, duplicate, error",
    )
    error_message: str | None = Field(
        default=None,
        description="Error details if processing failed",
    )
