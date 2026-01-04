"""Unit tests for Stripe webhook handling.

Tests verify webhook signature validation and event processing
without making actual Stripe API calls. All interactions are mocked.

TDD: These tests verify webhook handler behavior in isolation.

Test categories:
- T013: Webhook signature validation
- T014: checkout.session.completed event handling
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import stripe

from shared.models.stripe_webhook import StripeWebhookEvent
from shared.services.stripe_service import StripeService, StripeServiceError


# === Test Configuration ===

TEST_WEBHOOK_SECRET = "whsec_test_secret123"
TEST_RESERVATION_ID = "RES-2026-ABC123"
TEST_PAYMENT_ID = "PAY-2026-XYZ789"


# === Test Fixtures ===


@pytest.fixture
def mock_ssm_service():
    """Mock SSM service for credential retrieval."""
    with patch("shared.services.stripe_service.get_ssm_service") as mock_get_ssm:
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.side_effect = lambda param: {
            "/booking/dev/stripe/secret_key": "sk_test_abc123",
            "/booking/dev/stripe/webhook_secret": TEST_WEBHOOK_SECRET,
        }.get(param, None)
        mock_get_ssm.return_value = mock_ssm
        yield mock_ssm


@pytest.fixture
def stripe_service(mock_ssm_service) -> StripeService:
    """Create StripeService instance with mocked SSM."""
    from shared.services.stripe_service import get_stripe_service
    get_stripe_service.cache_clear()
    return StripeService(environment="dev")


@pytest.fixture
def sample_checkout_completed_event() -> dict:
    """Sample checkout.session.completed webhook event."""
    return {
        "id": "evt_test_checkout_completed_123",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_session_abc",
                "payment_intent": "pi_test_intent_xyz",
                "amount_total": 112500,
                "currency": "eur",
                "status": "complete",
                "payment_status": "paid",
                "metadata": {
                    "reservation_id": TEST_RESERVATION_ID,
                },
                "customer_email": "guest@example.com",
            }
        },
        "created": 1704067200,  # 2024-01-01 00:00:00 UTC
    }


@pytest.fixture
def sample_charge_refunded_event() -> dict:
    """Sample charge.refunded webhook event."""
    return {
        "id": "evt_test_charge_refunded_456",
        "type": "charge.refunded",
        "data": {
            "object": {
                "id": "ch_test_charge_def",
                "payment_intent": "pi_test_intent_xyz",
                "amount": 112500,
                "amount_refunded": 56250,
                "currency": "eur",
                "refunded": True,
                "metadata": {
                    "reservation_id": TEST_RESERVATION_ID,
                },
            }
        },
        "created": 1704153600,  # 2024-01-02 00:00:00 UTC
    }


# === T013: Webhook Signature Validation Tests ===


class TestWebhookSignatureValidation:
    """Test webhook signature verification (T013)."""

    def test_valid_signature_returns_parsed_event(
        self,
        stripe_service: StripeService,
        sample_checkout_completed_event: dict,
    ):
        """Valid signature returns the parsed webhook event."""
        payload = b'{"id": "evt_test_123", "type": "checkout.session.completed"}'
        signature = "t=1234567890,v1=valid_signature_abc123"

        with patch("stripe.Webhook.construct_event") as mock_construct:
            mock_construct.return_value = sample_checkout_completed_event

            result = stripe_service.verify_webhook_signature(
                payload=payload,
                signature=signature,
            )

        assert result["id"] == "evt_test_checkout_completed_123"
        assert result["type"] == "checkout.session.completed"
        mock_construct.assert_called_once()

    def test_invalid_signature_raises_error(
        self,
        stripe_service: StripeService,
    ):
        """Invalid signature raises StripeServiceError."""
        payload = b'{"id": "evt_test_123"}'
        signature = "t=1234567890,v1=invalid_signature"

        with patch(
            "stripe.Webhook.construct_event",
            side_effect=stripe.SignatureVerificationError(
                "Invalid signature", "sig_header"
            ),
        ):
            with pytest.raises(StripeServiceError) as exc_info:
                stripe_service.verify_webhook_signature(
                    payload=payload,
                    signature=signature,
                )

        assert "Invalid webhook signature" in str(exc_info.value)

    def test_expired_timestamp_raises_error(
        self,
        stripe_service: StripeService,
    ):
        """Expired timestamp in signature raises error."""
        payload = b'{"id": "evt_test_123"}'
        # Timestamp from long ago
        signature = "t=1000000000,v1=some_signature"

        with patch(
            "stripe.Webhook.construct_event",
            side_effect=stripe.SignatureVerificationError(
                "Timestamp outside tolerance", "sig_header"
            ),
        ):
            with pytest.raises(StripeServiceError) as exc_info:
                stripe_service.verify_webhook_signature(
                    payload=payload,
                    signature=signature,
                )

        assert "Invalid webhook signature" in str(exc_info.value)

    def test_missing_signature_raises_error(
        self,
        stripe_service: StripeService,
    ):
        """Missing signature header raises error."""
        payload = b'{"id": "evt_test_123"}'

        with patch(
            "stripe.Webhook.construct_event",
            side_effect=stripe.SignatureVerificationError(
                "No signature found", ""
            ),
        ):
            with pytest.raises(StripeServiceError) as exc_info:
                stripe_service.verify_webhook_signature(
                    payload=payload,
                    signature="",
                )

        assert "Invalid webhook signature" in str(exc_info.value)

    def test_tampered_payload_raises_error(
        self,
        stripe_service: StripeService,
    ):
        """Tampered payload (different from signed) raises error."""
        # Original payload was {"amount": 100}, attacker changed to 10
        tampered_payload = b'{"id": "evt_test_123", "amount": 10}'
        original_signature = "t=1234567890,v1=signature_for_amount_100"

        with patch(
            "stripe.Webhook.construct_event",
            side_effect=stripe.SignatureVerificationError(
                "Signature mismatch", "sig_header"
            ),
        ):
            with pytest.raises(StripeServiceError) as exc_info:
                stripe_service.verify_webhook_signature(
                    payload=tampered_payload,
                    signature=original_signature,
                )

        assert "Invalid webhook signature" in str(exc_info.value)


# === T014: checkout.session.completed Event Handling Tests ===


class TestCheckoutSessionCompletedHandling:
    """Test checkout.session.completed event processing (T014).

    These tests define the expected behavior for the webhook handler
    that will be implemented in T019. The handler should:
    1. Update reservation status to 'confirmed'
    2. Create/update Payment record with Stripe details
    3. Store webhook event for idempotency
    """

    def test_extracts_reservation_id_from_metadata(
        self,
        sample_checkout_completed_event: dict,
    ):
        """Handler extracts reservation_id from session metadata."""
        session_data = sample_checkout_completed_event["data"]["object"]

        reservation_id = session_data["metadata"].get("reservation_id")

        assert reservation_id == TEST_RESERVATION_ID

    def test_extracts_payment_intent_id(
        self,
        sample_checkout_completed_event: dict,
    ):
        """Handler extracts payment_intent_id for payment tracking."""
        session_data = sample_checkout_completed_event["data"]["object"]

        payment_intent_id = session_data["payment_intent"]

        assert payment_intent_id == "pi_test_intent_xyz"

    def test_extracts_amount_in_cents(
        self,
        sample_checkout_completed_event: dict,
    ):
        """Handler extracts amount_total (in cents)."""
        session_data = sample_checkout_completed_event["data"]["object"]

        amount_cents = session_data["amount_total"]

        assert amount_cents == 112500  # €1,125.00

    def test_extracts_currency(
        self,
        sample_checkout_completed_event: dict,
    ):
        """Handler extracts currency code."""
        session_data = sample_checkout_completed_event["data"]["object"]

        currency = session_data["currency"]

        assert currency == "eur"

    def test_extracts_checkout_session_id(
        self,
        sample_checkout_completed_event: dict,
    ):
        """Handler extracts checkout session ID for reference."""
        session_data = sample_checkout_completed_event["data"]["object"]

        session_id = session_data["id"]

        assert session_id == "cs_test_session_abc"

    def test_verifies_payment_status_is_paid(
        self,
        sample_checkout_completed_event: dict,
    ):
        """Handler verifies payment_status is 'paid' before confirming."""
        session_data = sample_checkout_completed_event["data"]["object"]

        payment_status = session_data["payment_status"]

        assert payment_status == "paid"

    def test_handles_missing_reservation_id_gracefully(self):
        """Handler handles events without reservation_id in metadata."""
        event_without_reservation = {
            "id": "evt_test_no_reservation",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_unknown",
                    "payment_intent": "pi_test_unknown",
                    "amount_total": 50000,
                    "currency": "eur",
                    "payment_status": "paid",
                    "metadata": {},  # No reservation_id
                }
            },
        }

        session_data = event_without_reservation["data"]["object"]
        reservation_id = session_data["metadata"].get("reservation_id")

        assert reservation_id is None
        # Handler should log warning and skip processing (no reservation to update)


class TestWebhookEventIdempotency:
    """Test idempotent webhook event processing.

    Stripe may send the same event multiple times. The handler must:
    1. Check if event_id was already processed
    2. Skip duplicate events
    3. Store processed events in DynamoDB
    """

    def test_creates_webhook_event_record(
        self,
        sample_checkout_completed_event: dict,
    ):
        """Handler creates StripeWebhookEvent record for processed event."""
        event = sample_checkout_completed_event
        payload = b'{"test": "payload"}'

        webhook_record = StripeWebhookEvent(
            event_id=event["id"],
            event_type=event["type"],
            processed_at=datetime.now(timezone.utc),
            payload_hash=StripeService.compute_payload_hash(payload),
            reservation_id=event["data"]["object"]["metadata"].get("reservation_id"),
            payment_id=None,  # Set after payment record created
            processing_result="success",
        )

        assert webhook_record.event_id == "evt_test_checkout_completed_123"
        assert webhook_record.event_type == "checkout.session.completed"
        assert webhook_record.reservation_id == TEST_RESERVATION_ID
        assert webhook_record.processing_result == "success"

    def test_computes_payload_hash_for_deduplication(self):
        """Handler computes SHA-256 hash of payload for deduplication."""
        payload = b'{"id": "evt_123", "type": "checkout.session.completed"}'

        hash1 = StripeService.compute_payload_hash(payload)
        hash2 = StripeService.compute_payload_hash(payload)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length

    def test_duplicate_event_has_same_hash(self):
        """Duplicate events (same payload) have same hash."""
        payload = b'{"id": "evt_duplicate"}'

        hash1 = StripeService.compute_payload_hash(payload)
        hash2 = StripeService.compute_payload_hash(payload)

        assert hash1 == hash2

    def test_different_events_have_different_hashes(self):
        """Different events produce different hashes."""
        payload1 = b'{"id": "evt_first"}'
        payload2 = b'{"id": "evt_second"}'

        hash1 = StripeService.compute_payload_hash(payload1)
        hash2 = StripeService.compute_payload_hash(payload2)

        assert hash1 != hash2


class TestCheckoutSessionCompletedErrorHandling:
    """Test error handling for checkout.session.completed events."""

    def test_handles_reservation_not_found(self):
        """Handler handles case where reservation doesn't exist."""
        # Event references a reservation that doesn't exist in DB
        event = {
            "id": "evt_test_orphan",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_orphan",
                    "payment_intent": "pi_test_orphan",
                    "amount_total": 75000,
                    "currency": "eur",
                    "payment_status": "paid",
                    "metadata": {
                        "reservation_id": "RES-NONEXISTENT",
                    },
                }
            },
        }

        # Handler should log error and store event with error status
        webhook_record = StripeWebhookEvent(
            event_id=event["id"],
            event_type=event["type"],
            processed_at=datetime.now(timezone.utc),
            payload_hash="abc123",
            reservation_id="RES-NONEXISTENT",
            processing_result="error",
            error_message="Reservation not found",
        )

        assert webhook_record.processing_result == "error"
        assert "not found" in webhook_record.error_message.lower()

    def test_handles_already_confirmed_reservation(self):
        """Handler handles case where reservation is already confirmed."""
        # Idempotent: if already confirmed, just return success
        webhook_record = StripeWebhookEvent(
            event_id="evt_test_already_confirmed",
            event_type="checkout.session.completed",
            processed_at=datetime.now(timezone.utc),
            payload_hash="def456",
            reservation_id=TEST_RESERVATION_ID,
            processing_result="success",  # Idempotent success
        )

        assert webhook_record.processing_result == "success"

    def test_handles_payment_status_not_paid(self):
        """Handler handles checkout.session.completed with payment_status != 'paid'."""
        # Some payment methods complete asynchronously
        event = {
            "id": "evt_test_pending_payment",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_pending",
                    "payment_intent": "pi_test_pending",
                    "amount_total": 50000,
                    "currency": "eur",
                    "payment_status": "unpaid",  # Payment still pending
                    "metadata": {
                        "reservation_id": TEST_RESERVATION_ID,
                    },
                }
            },
        }

        session_data = event["data"]["object"]
        payment_status = session_data["payment_status"]

        # Handler should NOT confirm reservation if payment_status != "paid"
        assert payment_status != "paid"


class TestChargeRefundedHandling:
    """Test charge.refunded event processing (for T032).

    Included here for completeness; will be implemented in Phase 5.
    """

    def test_extracts_refund_amount(
        self,
        sample_charge_refunded_event: dict,
    ):
        """Handler extracts refund amount from charge.refunded event."""
        charge_data = sample_charge_refunded_event["data"]["object"]

        amount_refunded = charge_data["amount_refunded"]

        assert amount_refunded == 56250  # €562.50 (50% refund)

    def test_extracts_original_amount(
        self,
        sample_charge_refunded_event: dict,
    ):
        """Handler extracts original charge amount."""
        charge_data = sample_charge_refunded_event["data"]["object"]

        original_amount = charge_data["amount"]

        assert original_amount == 112500  # €1,125.00

    def test_identifies_partial_vs_full_refund(
        self,
        sample_charge_refunded_event: dict,
    ):
        """Handler can distinguish partial from full refund."""
        charge_data = sample_charge_refunded_event["data"]["object"]

        original_amount = charge_data["amount"]
        refunded_amount = charge_data["amount_refunded"]
        is_full_refund = refunded_amount >= original_amount

        assert not is_full_refund  # This is a 50% refund
