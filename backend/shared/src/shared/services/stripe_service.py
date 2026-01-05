"""Stripe payment service for checkout sessions and refunds.

Provides integration with Stripe using the v8+ StripeClient pattern.
Retrieves API keys from SSM Parameter Store.
"""

import hashlib
import logging
import os
from datetime import datetime, timezone
from functools import lru_cache

import stripe
from stripe import StripeClient

from .ssm_service import SSMServiceError, get_ssm_service

logger = logging.getLogger(__name__)


class StripeServiceError(Exception):
    """Raised when a Stripe operation fails."""

    def __init__(self, message: str, stripe_error_code: str | None = None) -> None:
        """Initialize with message and optional Stripe error code.

        Args:
            message: Human-readable error message.
            stripe_error_code: Stripe-specific error code if available.
        """
        super().__init__(message)
        self.stripe_error_code = stripe_error_code


class StripeService:
    """Service for Stripe payment operations.

    Handles:
    - Checkout session creation
    - Webhook signature validation
    - Refund processing

    Usage:
        stripe_svc = get_stripe_service()
        session = stripe_svc.create_checkout_session(
            reservation_id="RES-2026-ABC123",
            amount_cents=112500,
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )
    """

    def __init__(self, environment: str | None = None) -> None:
        """Initialize Stripe service with credentials from SSM.

        Args:
            environment: Environment name (dev, prod). Defaults to ENVIRONMENT env var.
        """
        self._environment = environment or os.environ.get("ENVIRONMENT", "dev")
        self._ssm = get_ssm_service()
        self._client: StripeClient | None = None
        self._webhook_secret: str | None = None

    def _get_client(self) -> StripeClient:
        """Get or create the Stripe client (lazy initialization).

        Returns:
            Initialized StripeClient instance.

        Raises:
            StripeServiceError: If credentials cannot be retrieved.
        """
        if self._client is None:
            try:
                secret_key = self._ssm.get_parameter(
                    f"/booking/{self._environment}/stripe/secret_key"
                )
                self._client = StripeClient(secret_key)
                logger.info("Stripe client initialized for environment: %s", self._environment)
            except SSMServiceError as e:
                raise StripeServiceError(f"Failed to initialize Stripe client: {e}") from e
        return self._client

    def _get_webhook_secret(self) -> str:
        """Get the webhook signing secret.

        Returns:
            Webhook signing secret.

        Raises:
            StripeServiceError: If secret cannot be retrieved.
        """
        if self._webhook_secret is None:
            try:
                self._webhook_secret = self._ssm.get_parameter(
                    f"/booking/{self._environment}/stripe/webhook_secret"
                )
            except SSMServiceError as e:
                raise StripeServiceError(f"Failed to get webhook secret: {e}") from e
        return self._webhook_secret

    def create_checkout_session(
        self,
        *,
        reservation_id: str,
        amount_cents: int,
        description: str,
        customer_email: str | None = None,
        success_url: str,
        cancel_url: str,
        metadata: dict[str, str] | None = None,
    ) -> dict:
        """Create a Stripe Checkout session.

        Args:
            reservation_id: Reservation ID (used as idempotency key).
            amount_cents: Amount in EUR cents.
            description: Line item description.
            customer_email: Optional customer email for Stripe receipt.
            success_url: URL to redirect on success (supports {CHECKOUT_SESSION_ID}).
            cancel_url: URL to redirect on cancel.
            metadata: Additional metadata to include.

        Returns:
            Dict with session details:
                - session_id: Stripe checkout session ID
                - checkout_url: URL to redirect user
                - expires_at: When session expires

        Raises:
            StripeServiceError: If session creation fails.
        """
        client = self._get_client()

        # Build metadata with reservation reference
        session_metadata = {"reservation_id": reservation_id}
        if metadata:
            session_metadata.update(metadata)

        # Use reservation_id as idempotency key to prevent duplicate sessions
        idempotency_key = f"checkout_{reservation_id}"

        try:
            logger.info(
                "Creating Stripe checkout session for reservation %s, amount %d cents",
                reservation_id,
                amount_cents,
            )

            session = client.checkout.sessions.create(
                params={
                    "mode": "payment",
                    "payment_method_types": ["card"],
                    "line_items": [
                        {
                            "price_data": {
                                "currency": "eur",
                                "unit_amount": amount_cents,
                                "product_data": {
                                    "name": "Accommodation Booking",
                                    "description": description,
                                },
                            },
                            "quantity": 1,
                        }
                    ],
                    "success_url": success_url,
                    "cancel_url": cancel_url,
                    "metadata": session_metadata,
                    "customer_email": customer_email,
                    "expires_at": int(datetime.now(timezone.utc).timestamp()) + 1800,  # 30 min from now
                },
                options={"idempotency_key": idempotency_key},
            )

            logger.info(
                "Checkout session created: %s for reservation %s",
                session.id,
                reservation_id,
            )

            return {
                "session_id": session.id,
                "checkout_url": session.url,
                "expires_at": datetime.fromtimestamp(session.expires_at, tz=timezone.utc),
                "payment_intent_id": session.payment_intent,
            }

        except stripe.StripeError as e:
            error_code = getattr(e, "code", None)
            logger.error(
                "Stripe checkout session creation failed: %s (code: %s)",
                str(e),
                error_code,
            )
            raise StripeServiceError(
                f"Failed to create checkout session: {e}",
                stripe_error_code=error_code,
            ) from e

    def verify_webhook_signature(self, payload: bytes, signature: str) -> dict:
        """Verify a webhook signature and parse the event.

        Args:
            payload: Raw request body bytes.
            signature: Stripe-Signature header value.

        Returns:
            Parsed Stripe event dictionary.

        Raises:
            StripeServiceError: If signature is invalid.
        """
        webhook_secret = self._get_webhook_secret()

        try:
            event = stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
            logger.info("Webhook signature verified for event: %s", event["id"])
            return dict(event)

        except stripe.SignatureVerificationError as e:
            logger.warning("Invalid webhook signature: %s", str(e))
            raise StripeServiceError("Invalid webhook signature") from e

    def create_refund(
        self,
        *,
        payment_intent_id: str,
        amount_cents: int | None = None,
        reason: str | None = None,
    ) -> dict:
        """Create a refund for a payment.

        Args:
            payment_intent_id: Stripe PaymentIntent ID (pi_xxx).
            amount_cents: Refund amount in cents. If None, full refund.
            reason: Reason for refund (for records).

        Returns:
            Dict with refund details:
                - refund_id: Stripe refund ID
                - amount: Refunded amount in cents
                - status: Refund status

        Raises:
            StripeServiceError: If refund creation fails.
        """
        client = self._get_client()

        params: dict = {"payment_intent": payment_intent_id}
        if amount_cents is not None:
            params["amount"] = amount_cents
        if reason:
            params["metadata"] = {"reason": reason}

        try:
            logger.info(
                "Creating refund for PaymentIntent %s, amount %s cents",
                payment_intent_id,
                amount_cents or "full",
            )

            refund = client.refunds.create(params=params)

            logger.info(
                "Refund created: %s for PaymentIntent %s",
                refund.id,
                payment_intent_id,
            )

            return {
                "refund_id": refund.id,
                "amount": refund.amount,
                "status": refund.status,
            }

        except stripe.StripeError as e:
            error_code = getattr(e, "code", None)
            logger.error(
                "Stripe refund creation failed: %s (code: %s)",
                str(e),
                error_code,
            )
            raise StripeServiceError(
                f"Failed to create refund: {e}",
                stripe_error_code=error_code,
            ) from e

    @staticmethod
    def compute_payload_hash(payload: bytes) -> str:
        """Compute SHA-256 hash of webhook payload for deduplication.

        Args:
            payload: Raw webhook payload bytes.

        Returns:
            Hex-encoded SHA-256 hash.
        """
        return hashlib.sha256(payload).hexdigest()


@lru_cache(maxsize=1)
def get_stripe_service() -> StripeService:
    """Get the shared StripeService instance (singleton pattern).

    Returns:
        StripeService: Shared service instance.
    """
    return StripeService()
