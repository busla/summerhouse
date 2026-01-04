"""Webhook handler for processing Stripe events.

Provides business logic for handling webhook events separate from
HTTP routing concerns. This enables:
- Unit testing without HTTP overhead
- Reuse across different transport mechanisms
- Clean separation of concerns
"""

import datetime as dt
import logging
from typing import Any

from shared.models.stripe_webhook import StripeWebhookEvent
from shared.services.dynamodb import get_dynamodb_service
from shared.services.stripe_service import StripeService

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Handler for processing Stripe webhook events.

    Processes events and updates DynamoDB tables accordingly.
    Ensures idempotent processing using event_id tracking.
    """

    WEBHOOK_EVENTS_TABLE = "stripe-webhook-events"
    RESERVATIONS_TABLE = "reservations"
    PAYMENTS_TABLE = "payments"

    def __init__(self) -> None:
        """Initialize webhook handler."""
        self._db = get_dynamodb_service()

    def is_event_already_processed(self, event_id: str) -> bool:
        """Check if webhook event was already processed (idempotency).

        Args:
            event_id: Stripe event ID

        Returns:
            True if event was already processed
        """
        existing = self._db.get_item(self.WEBHOOK_EVENTS_TABLE, {"event_id": event_id})
        return existing is not None

    def log_event(
        self,
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

        self._db.put_item(self.WEBHOOK_EVENTS_TABLE, item)

    def process_checkout_completed(self, event: dict) -> tuple[str, str | None]:
        """Process checkout.session.completed event.

        Updates payment status to 'completed' and reservation status to 'confirmed'.
        Logs the event for idempotency and audit trail.

        Args:
            event: Parsed Stripe webhook event

        Returns:
            Tuple of (processing_result, error_message)
        """
        import hashlib
        import json

        event_id = event.get("id", "")
        event_type = event.get("type", "checkout.session.completed")

        # Compute payload hash
        payload_hash = hashlib.sha256(
            json.dumps(event, sort_keys=True).encode()
        ).hexdigest()

        event_data = event.get("data", {})
        session = event_data.get("object", {})
        metadata = session.get("metadata", {})

        reservation_id = metadata.get("reservation_id")
        payment_id = metadata.get("payment_id")
        payment_status = session.get("payment_status")
        payment_intent_id = session.get("payment_intent")
        session_id = session.get("id")
        amount_total = session.get("amount_total", 0)

        if not reservation_id:
            logger.warning(
                "checkout.session.completed without reservation_id in metadata"
            )
            error_msg = "Missing reservation_id in metadata"
            self.log_event(
                event_id=event_id,
                event_type=event_type,
                payload_hash=payload_hash,
                reservation_id=None,
                payment_id=payment_id,
                processing_result="error",
                error_message=error_msg,
            )
            return "error", error_msg

        # Only confirm if payment_status is 'paid'
        if payment_status != "paid":
            logger.warning(
                "checkout.session.completed with payment_status=%s (not 'paid'), skipping",
                payment_status,
            )
            skip_msg = f"Payment status is '{payment_status}', not 'paid'"
            self.log_event(
                event_id=event_id,
                event_type=event_type,
                payload_hash=payload_hash,
                reservation_id=reservation_id,
                payment_id=payment_id,
                processing_result="skipped",
                error_message=skip_msg,
            )
            return "skipped", skip_msg

        # Verify reservation exists before updating
        existing = self._db.get_item(self.RESERVATIONS_TABLE, {"reservation_id": reservation_id})
        if not existing:
            logger.warning(
                "checkout.session.completed for non-existent reservation: %s",
                reservation_id,
            )
            error_msg = f"Reservation {reservation_id} not found"
            self.log_event(
                event_id=event_id,
                event_type=event_type,
                payload_hash=payload_hash,
                reservation_id=reservation_id,
                payment_id=payment_id,
                processing_result="error",
                error_message=error_msg,
            )
            return "error", error_msg

        # Update reservation to confirmed
        try:
            self._db.update_item(
                self.RESERVATIONS_TABLE,
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
            error_msg = f"Failed to update reservation: {e}"
            self.log_event(
                event_id=event_id,
                event_type=event_type,
                payload_hash=payload_hash,
                reservation_id=reservation_id,
                payment_id=payment_id,
                processing_result="error",
                error_message=error_msg,
            )
            return "error", error_msg

        # Create or update payment record
        try:
            # Check if payment exists, otherwise create one
            if payment_id:
                self._db.update_item(
                    self.PAYMENTS_TABLE,
                    {"payment_id": payment_id},
                    "SET #status = :status, stripe_payment_intent_id = :pi, completed_at = :now, updated_at = :now",
                    {
                        ":status": "completed",
                        ":pi": payment_intent_id,
                        ":now": dt.datetime.now(dt.UTC).isoformat(),
                    },
                    {"#status": "status"},
                )
                logger.info("Payment %s marked as completed via webhook", payment_id)
            else:
                # Create new payment record if none exists
                import uuid
                new_payment_id = f"PAY-{uuid.uuid4().hex[:12].upper()}"
                now = dt.datetime.now(dt.UTC)
                self._db.put_item(
                    self.PAYMENTS_TABLE,
                    {
                        "payment_id": new_payment_id,
                        "reservation_id": reservation_id,
                        "stripe_checkout_session_id": session_id,
                        "stripe_payment_intent_id": payment_intent_id,
                        "amount_cents": amount_total,
                        "currency": "EUR",
                        "status": "completed",
                        "payment_method": "card",
                        "provider": "stripe",
                        "created_at": now.isoformat(),
                        "completed_at": now.isoformat(),
                    },
                )
                logger.info(
                    "Created payment %s for reservation %s via webhook",
                    new_payment_id,
                    reservation_id,
                )
        except Exception as e:
            logger.error("Failed to update/create payment: %s", e)
            # Payment update failure is not critical - reservation is confirmed

        # Log successful processing
        self.log_event(
            event_id=event_id,
            event_type=event_type,
            payload_hash=payload_hash,
            reservation_id=reservation_id,
            payment_id=payment_id,
            processing_result="success",
        )
        return "success", None

    def process_charge_refunded(self, event: dict) -> tuple[str, str | None]:
        """Process charge.refunded event.

        Updates payment record with refund information.

        Args:
            event: Parsed Stripe webhook event

        Returns:
            Tuple of (processing_result, error_message)
        """
        event_data = event.get("data", {})
        charge = event_data.get("object", {})
        metadata = charge.get("metadata", {})

        reservation_id = metadata.get("reservation_id")
        payment_intent_id = charge.get("payment_intent")
        amount_refunded = charge.get("amount_refunded", 0)

        if not reservation_id and not payment_intent_id:
            logger.warning("charge.refunded without reservation_id or payment_intent")
            return "skipped", "No reservation_id or payment_intent in event"

        # Find payment by reservation_id
        payments = []
        if reservation_id:
            items = self._db.query_by_gsi(
                self.PAYMENTS_TABLE,
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
            self._db.update_item(
                self.PAYMENTS_TABLE,
                {"payment_id": payment_id},
                "SET #status = :status, amount_refunded = :refund, refunded_at = :now, updated_at = :now",
                {
                    ":status": "refunded",
                    ":refund": amount_refunded,
                    ":now": dt.datetime.now(dt.UTC).isoformat(),
                },
                {"#status": "status"},
            )
            logger.info(
                "Payment %s updated with refund amount %d",
                payment_id,
                amount_refunded,
            )
        except Exception as e:
            logger.error("Failed to update payment %s with refund: %s", payment_id, e)
            return "error", f"Failed to update payment with refund: {e}"

        return "success", None
