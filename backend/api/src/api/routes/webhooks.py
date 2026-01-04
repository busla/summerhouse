"""Webhook endpoints for external service integrations.

Provides endpoints for:
- Stripe webhook events (checkout.session.completed, charge.refunded)

These endpoints do NOT require JWT authentication as they receive
signed payloads from external services.
"""

import datetime as dt
from typing import Any

from fastapi import APIRouter, Request

from shared.utils.logging import get_logger, log_webhook_event

logger = get_logger(__name__)
from pydantic import BaseModel
from starlette.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from shared.models.errors import BookingError, ErrorCode
from shared.services.dynamodb import get_dynamodb_service
from shared.services.stripe_service import (
    StripeService,
    StripeServiceError,
    get_stripe_service,
)

router = APIRouter(tags=["webhooks"])


# === Response Models ===


class WebhookResponse(BaseModel):
    """Standard webhook response."""

    received: bool
    event_id: str | None = None
    event_type: str | None = None
    processing_result: str  # "success", "duplicate", "skipped", "error"
    message: str | None = None


class WebhookErrorResponse(BaseModel):
    """Error response for webhook failures."""

    success: bool = False
    message: str
    recovery: str | None = None


# === Webhook Event Table ===

WEBHOOK_EVENTS_TABLE = "stripe-webhook-events"

# Event types we handle
HANDLED_EVENT_TYPES = {
    "checkout.session.completed",
    "charge.refunded",
}


# === Helper Functions ===


def _is_event_already_processed(event_id: str) -> bool:
    """Check if webhook event was already processed (idempotency).

    Args:
        event_id: Stripe event ID

    Returns:
        True if event was already processed
    """
    db = get_dynamodb_service()
    existing = db.get_item(WEBHOOK_EVENTS_TABLE, {"event_id": event_id})
    return existing is not None


def _log_webhook_event(
    event_id: str,
    event_type: str,
    payload_hash: str,
    reservation_id: str | None,
    payment_id: str | None,
    processing_result: str,
    error_message: str | None = None,
) -> None:
    """Log webhook event to DynamoDB for idempotency and audit trail.

    Args:
        event_id: Stripe event ID
        event_type: Event type (checkout.session.completed, etc.)
        payload_hash: SHA-256 hash of payload
        reservation_id: Associated reservation ID (if any)
        payment_id: Associated payment ID (if any)
        processing_result: Result (success, duplicate, skipped, error)
        error_message: Error message if processing failed
    """
    db = get_dynamodb_service()
    now = dt.datetime.now(dt.UTC)

    item: dict[str, Any] = {
        "event_id": event_id,
        "event_type": event_type,
        "processed_at": now.isoformat(),
        "payload_hash": payload_hash,
        "processing_result": processing_result,
    }

    if reservation_id:
        item["reservation_id"] = reservation_id
    if payment_id:
        item["payment_id"] = payment_id
    if error_message:
        item["error_message"] = error_message

    db.put_item(WEBHOOK_EVENTS_TABLE, item)


def _handle_checkout_session_completed(event_data: dict) -> tuple[str, str | None]:
    """Process checkout.session.completed event.

    Updates payment status to 'paid' and reservation status to 'confirmed'.

    Args:
        event_data: Event data object from Stripe

    Returns:
        Tuple of (processing_result, error_message)
    """
    session = event_data.get("object", {})
    metadata = session.get("metadata", {})

    reservation_id = metadata.get("reservation_id")
    payment_id = metadata.get("payment_id")
    payment_status = session.get("payment_status")
    payment_intent_id = session.get("payment_intent")

    if not reservation_id:
        logger.warning(
            "checkout.session.completed without reservation_id in metadata"
        )
        return "error", "Missing reservation_id in metadata"

    # Only confirm if payment_status is 'paid'
    if payment_status != "paid":
        logger.warning(
            "checkout.session.completed with payment_status=%s (not 'paid'), skipping",
            payment_status,
        )
        return "skipped", f"Payment status is '{payment_status}', not 'paid'"

    db = get_dynamodb_service()

    # Update reservation to confirmed
    try:
        db.update_item(
            "reservations",
            {"reservation_id": reservation_id},
            "SET #status = :status, payment_status = :payment_status, updated_at = :now",
            {
                ":status": "confirmed",
                ":payment_status": "paid",
                ":now": dt.datetime.now(dt.UTC).isoformat(),
            },
            {"#status": "status"},  # status is reserved word
        )
        logger.info("Reservation %s confirmed via webhook", reservation_id)
    except Exception as e:
        logger.error("Failed to update reservation %s: %s", reservation_id, e)
        return "error", f"Failed to update reservation: {e}"

    # Update payment status if we have the payment_id
    if payment_id:
        try:
            db.update_item(
                "payments",
                {"payment_id": payment_id},
                "SET #status = :status, stripe_payment_intent_id = :pi, completed_at = :now, updated_at = :now",
                {
                    ":status": "paid",
                    ":pi": payment_intent_id,
                    ":now": dt.datetime.now(dt.UTC).isoformat(),
                },
                {"#status": "status"},
            )
            log_webhook_event(
                logger,
                "checkout.session.completed",
                "payment_updated",
                payment_id=payment_id,
                result="paid",
            )
        except Exception as e:
            logger.error("Failed to update payment %s: %s", payment_id, e)
            # Payment update failure is not critical - reservation is confirmed

    log_webhook_event(
        logger,
        "checkout.session.completed",
        "reservation_confirmed",
        reservation_id=reservation_id,
        payment_id=payment_id,
        result="success",
    )
    return "success", None


def _handle_charge_refunded(event_data: dict) -> tuple[str, str | None]:
    """Process charge.refunded event.

    Updates payment record with refund information.

    Args:
        event_data: Event data object from Stripe

    Returns:
        Tuple of (processing_result, error_message)
    """
    charge = event_data.get("object", {})
    metadata = charge.get("metadata", {})

    reservation_id = metadata.get("reservation_id")
    payment_intent_id = charge.get("payment_intent")
    amount_refunded = charge.get("amount_refunded", 0)

    if not reservation_id and not payment_intent_id:
        logger.warning("charge.refunded without reservation_id or payment_intent")
        return "skipped", "No reservation_id or payment_intent in event"

    db = get_dynamodb_service()

    # Find payment by reservation_id or payment_intent_id
    # Try to find via payment_intent_id first (more reliable)
    payments = []
    if reservation_id:
        items = db.query_by_gsi(
            "payments",
            "reservation-index",
            "reservation_id",
            reservation_id,
        )
        payments = list(items)

    if not payments:
        logger.warning(
            "No payment found for refund event (reservation=%s, pi=%s)",
            reservation_id,
            payment_intent_id,
        )
        return "error", "Payment not found for refund"

    # Update the most recent payment
    payment = payments[0]
    payment_id = payment["payment_id"]

    try:
        db.update_item(
            "payments",
            {"payment_id": payment_id},
            "SET #status = :status, amount_refunded = :refund, refunded_at = :now, updated_at = :now",
            {
                ":status": "refunded",
                ":refund": amount_refunded,
                ":now": dt.datetime.now(dt.UTC).isoformat(),
            },
            {"#status": "status"},
        )
        log_webhook_event(
            logger,
            "charge.refunded",
            "refund_processed",
            reservation_id=reservation_id,
            payment_id=payment_id,
            result="success",
            amount_refunded=amount_refunded,
        )
    except Exception as e:
        logger.error("Failed to update payment %s with refund: %s", payment_id, e)
        return "error", f"Failed to update payment with refund: {e}"

    return "success", None


# === Webhook Endpoint ===


@router.post(
    "/webhooks/stripe",
    summary="Receive Stripe webhook events",
    description="""
Endpoint for Stripe webhook events. Handles:
- checkout.session.completed: Confirms reservation and marks payment as paid
- charge.refunded: Updates payment with refund information

**No authentication required** - signature is verified using Stripe webhook secret.

**Idempotent**: Duplicate events (same event_id) return 200 with 'duplicate' result.
""",
    response_model=WebhookResponse,
    responses={
        200: {
            "description": "Event received and processed (or acknowledged)",
            "model": WebhookResponse,
        },
        400: {
            "description": "Invalid signature or missing header",
            "model": WebhookErrorResponse,
        },
    },
)
async def handle_stripe_webhook(request: Request) -> WebhookResponse:
    """Handle incoming Stripe webhook events.

    Verifies signature, checks for duplicates, and processes the event.
    """
    # Get signature header
    signature = request.headers.get("Stripe-Signature")
    if not signature:
        logger.warning("Webhook request missing Stripe-Signature header")
        raise BookingError(
            code=ErrorCode.INVALID_WEBHOOK_SIGNATURE,
            details={"message": "Missing Stripe-Signature header"},
        )

    # Get raw body for signature verification
    payload = await request.body()

    # Verify signature
    try:
        stripe_service = get_stripe_service()
        event = stripe_service.verify_webhook_signature(payload, signature)
    except StripeServiceError as e:
        logger.warning("Webhook signature verification failed: %s", e)
        raise BookingError(
            code=ErrorCode.INVALID_WEBHOOK_SIGNATURE,
            details={"message": "Invalid webhook signature"},
        )

    event_id = event.get("id")
    event_type = event.get("type")
    event_data = event.get("data", {})

    log_webhook_event(
        logger,
        event_type,
        event_id,
        result="received",
    )

    # Compute payload hash for deduplication
    payload_hash = StripeService.compute_payload_hash(payload)

    # Check for duplicate (idempotency)
    if _is_event_already_processed(event_id):
        log_webhook_event(
            logger,
            event_type,
            event_id,
            result="duplicate",
        )
        return WebhookResponse(
            received=True,
            event_id=event_id,
            event_type=event_type,
            processing_result="duplicate",
            message="Event already processed",
        )

    # Extract reservation_id from metadata for logging
    session_object = event_data.get("object", {})
    metadata = session_object.get("metadata", {})
    reservation_id = metadata.get("reservation_id")
    payment_id = metadata.get("payment_id")

    # Process based on event type
    if event_type not in HANDLED_EVENT_TYPES:
        logger.info("Unhandled event type %s, skipping", event_type)
        _log_webhook_event(
            event_id=event_id,
            event_type=event_type,
            payload_hash=payload_hash,
            reservation_id=reservation_id,
            payment_id=payment_id,
            processing_result="skipped",
        )
        return WebhookResponse(
            received=True,
            event_id=event_id,
            event_type=event_type,
            processing_result="skipped",
            message=f"Event type '{event_type}' not handled",
        )

    # Handle specific event types
    processing_result = "success"
    error_message = None

    if event_type == "checkout.session.completed":
        processing_result, error_message = _handle_checkout_session_completed(event_data)
    elif event_type == "charge.refunded":
        processing_result, error_message = _handle_charge_refunded(event_data)

    # Log the event
    _log_webhook_event(
        event_id=event_id,
        event_type=event_type,
        payload_hash=payload_hash,
        reservation_id=reservation_id,
        payment_id=payment_id,
        processing_result=processing_result,
        error_message=error_message,
    )

    return WebhookResponse(
        received=True,
        event_id=event_id,
        event_type=event_type,
        processing_result=processing_result,
        message=error_message if processing_result == "error" else None,
    )
