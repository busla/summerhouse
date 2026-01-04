"""Unit tests for StripeService.

Tests verify the service logic without making actual Stripe API calls.
All Stripe interactions are mocked.

TDD: These tests verify StripeService methods in isolation.

Test categories:
- T012-A: Initialization and credential retrieval
- T012-B: create_checkout_session() method
- T012-C: verify_webhook_signature() method
- T012-D: create_refund() method
- T012-E: Error handling and edge cases
"""

import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import stripe

from shared.services.ssm_service import SSMServiceError
from shared.services.stripe_service import (
    StripeService,
    StripeServiceError,
)


# === Test Configuration ===

TEST_SECRET_KEY = "sk_test_abc123xyz"
TEST_WEBHOOK_SECRET = "whsec_test_secret123"
TEST_RESERVATION_ID = "RES-2026-ABC123"


# === Test Fixtures ===


@pytest.fixture
def mock_ssm_service():
    """Mock SSM service for credential retrieval."""
    with patch("shared.services.stripe_service.get_ssm_service") as mock_get_ssm:
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.side_effect = lambda param: {
            "/booking/dev/stripe/secret_key": TEST_SECRET_KEY,
            "/booking/dev/stripe/webhook_secret": TEST_WEBHOOK_SECRET,
        }.get(param, None)
        mock_get_ssm.return_value = mock_ssm
        yield mock_ssm


@pytest.fixture
def stripe_service(mock_ssm_service) -> StripeService:
    """Create StripeService instance with mocked SSM."""
    # Clear any cached instance
    from shared.services.stripe_service import get_stripe_service
    get_stripe_service.cache_clear()
    return StripeService(environment="dev")


@pytest.fixture
def mock_stripe_client():
    """Mock Stripe client for API calls."""
    with patch("shared.services.stripe_service.StripeClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        yield mock_client


# === T012-A: Initialization Tests ===


class TestStripeServiceInitialization:
    """Test service initialization and credential handling."""

    def test_initializes_with_environment(self, mock_ssm_service):
        """Service accepts explicit environment parameter."""
        service = StripeService(environment="prod")
        assert service._environment == "prod"

    def test_defaults_to_dev_environment(self, mock_ssm_service):
        """Service defaults to 'dev' when no environment specified."""
        with patch.dict("os.environ", {}, clear=True):
            service = StripeService()
            assert service._environment == "dev"

    def test_uses_environment_variable(self, mock_ssm_service):
        """Service uses ENVIRONMENT env var when set."""
        with patch.dict("os.environ", {"ENVIRONMENT": "staging"}):
            service = StripeService()
            assert service._environment == "staging"

    def test_client_lazy_initialized(self, stripe_service):
        """Client is not created until first use."""
        assert stripe_service._client is None

    def test_raises_error_when_ssm_fails(self, mock_ssm_service, mock_stripe_client):
        """Raises StripeServiceError when SSM retrieval fails."""
        mock_ssm_service.get_parameter.side_effect = SSMServiceError("SSM error")
        service = StripeService(environment="dev")

        with pytest.raises(StripeServiceError) as exc_info:
            service._get_client()

        assert "Failed to initialize Stripe client" in str(exc_info.value)


# === T012-B: create_checkout_session() Tests ===


class TestCreateCheckoutSession:
    """Test checkout session creation."""

    def test_creates_session_with_required_params(
        self,
        stripe_service: StripeService,
        mock_stripe_client,
    ):
        """Creates checkout session with correct parameters."""
        # Mock session response
        mock_session = MagicMock()
        mock_session.id = "cs_test_123"
        mock_session.url = "https://checkout.stripe.com/c/pay/cs_test_123"
        mock_session.expires_at = int(time.time()) + 1800
        mock_session.payment_intent = "pi_test_456"
        mock_stripe_client.checkout.sessions.create.return_value = mock_session

        result = stripe_service.create_checkout_session(
            reservation_id=TEST_RESERVATION_ID,
            amount_cents=112500,
            description="Stay: Jul 15-22, 2026",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        assert result["session_id"] == "cs_test_123"
        assert result["checkout_url"] == "https://checkout.stripe.com/c/pay/cs_test_123"
        assert result["payment_intent_id"] == "pi_test_456"
        assert isinstance(result["expires_at"], datetime)

    def test_uses_idempotency_key(
        self,
        stripe_service: StripeService,
        mock_stripe_client,
    ):
        """Uses reservation_id as idempotency key."""
        mock_session = MagicMock()
        mock_session.id = "cs_test_123"
        mock_session.url = "https://checkout.stripe.com/c/pay/cs_test_123"
        mock_session.expires_at = int(time.time()) + 1800
        mock_session.payment_intent = "pi_test_456"
        mock_stripe_client.checkout.sessions.create.return_value = mock_session

        stripe_service.create_checkout_session(
            reservation_id=TEST_RESERVATION_ID,
            amount_cents=112500,
            description="Test booking",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        # Verify idempotency key was passed
        call_kwargs = mock_stripe_client.checkout.sessions.create.call_args
        assert call_kwargs.kwargs["options"]["idempotency_key"] == f"checkout_{TEST_RESERVATION_ID}"

    def test_includes_reservation_id_in_metadata(
        self,
        stripe_service: StripeService,
        mock_stripe_client,
    ):
        """Includes reservation_id in session metadata."""
        mock_session = MagicMock()
        mock_session.id = "cs_test_123"
        mock_session.url = "https://checkout.stripe.com/c/pay/cs_test_123"
        mock_session.expires_at = int(time.time()) + 1800
        mock_session.payment_intent = "pi_test_456"
        mock_stripe_client.checkout.sessions.create.return_value = mock_session

        stripe_service.create_checkout_session(
            reservation_id=TEST_RESERVATION_ID,
            amount_cents=112500,
            description="Test booking",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        call_kwargs = mock_stripe_client.checkout.sessions.create.call_args
        params = call_kwargs.kwargs["params"]
        assert params["metadata"]["reservation_id"] == TEST_RESERVATION_ID

    def test_includes_customer_email_when_provided(
        self,
        stripe_service: StripeService,
        mock_stripe_client,
    ):
        """Includes customer_email in session when provided."""
        mock_session = MagicMock()
        mock_session.id = "cs_test_123"
        mock_session.url = "https://checkout.stripe.com/c/pay/cs_test_123"
        mock_session.expires_at = int(time.time()) + 1800
        mock_session.payment_intent = "pi_test_456"
        mock_stripe_client.checkout.sessions.create.return_value = mock_session

        stripe_service.create_checkout_session(
            reservation_id=TEST_RESERVATION_ID,
            amount_cents=112500,
            description="Test booking",
            customer_email="guest@example.com",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        call_kwargs = mock_stripe_client.checkout.sessions.create.call_args
        params = call_kwargs.kwargs["params"]
        assert params["customer_email"] == "guest@example.com"

    def test_merges_custom_metadata(
        self,
        stripe_service: StripeService,
        mock_stripe_client,
    ):
        """Merges custom metadata with reservation_id."""
        mock_session = MagicMock()
        mock_session.id = "cs_test_123"
        mock_session.url = "https://checkout.stripe.com/c/pay/cs_test_123"
        mock_session.expires_at = int(time.time()) + 1800
        mock_session.payment_intent = "pi_test_456"
        mock_stripe_client.checkout.sessions.create.return_value = mock_session

        stripe_service.create_checkout_session(
            reservation_id=TEST_RESERVATION_ID,
            amount_cents=112500,
            description="Test booking",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            metadata={"customer_id": "CUST-123", "source": "web"},
        )

        call_kwargs = mock_stripe_client.checkout.sessions.create.call_args
        params = call_kwargs.kwargs["params"]
        assert params["metadata"]["reservation_id"] == TEST_RESERVATION_ID
        assert params["metadata"]["customer_id"] == "CUST-123"
        assert params["metadata"]["source"] == "web"

    def test_uses_eur_currency(
        self,
        stripe_service: StripeService,
        mock_stripe_client,
    ):
        """Always uses EUR currency."""
        mock_session = MagicMock()
        mock_session.id = "cs_test_123"
        mock_session.url = "https://checkout.stripe.com/c/pay/cs_test_123"
        mock_session.expires_at = int(time.time()) + 1800
        mock_session.payment_intent = "pi_test_456"
        mock_stripe_client.checkout.sessions.create.return_value = mock_session

        stripe_service.create_checkout_session(
            reservation_id=TEST_RESERVATION_ID,
            amount_cents=112500,
            description="Test booking",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        call_kwargs = mock_stripe_client.checkout.sessions.create.call_args
        params = call_kwargs.kwargs["params"]
        assert params["line_items"][0]["price_data"]["currency"] == "eur"

    def test_raises_error_on_stripe_failure(
        self,
        stripe_service: StripeService,
        mock_stripe_client,
    ):
        """Raises StripeServiceError when Stripe API fails."""
        mock_stripe_client.checkout.sessions.create.side_effect = stripe.StripeError(
            "Card declined"
        )

        with pytest.raises(StripeServiceError) as exc_info:
            stripe_service.create_checkout_session(
                reservation_id=TEST_RESERVATION_ID,
                amount_cents=112500,
                description="Test booking",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

        assert "Failed to create checkout session" in str(exc_info.value)

    def test_preserves_stripe_error_code(
        self,
        stripe_service: StripeService,
        mock_stripe_client,
    ):
        """Preserves Stripe error code in exception."""
        error = stripe.StripeError("Card declined")
        error.code = "card_declined"
        mock_stripe_client.checkout.sessions.create.side_effect = error

        with pytest.raises(StripeServiceError) as exc_info:
            stripe_service.create_checkout_session(
                reservation_id=TEST_RESERVATION_ID,
                amount_cents=112500,
                description="Test booking",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

        assert exc_info.value.stripe_error_code == "card_declined"


# === T012-C: verify_webhook_signature() Tests ===


class TestVerifyWebhookSignature:
    """Test webhook signature verification."""

    def test_verifies_valid_signature(
        self,
        stripe_service: StripeService,
    ):
        """Returns parsed event for valid signature."""
        test_event = {
            "id": "evt_test_123",
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test_123"}},
        }

        with patch("stripe.Webhook.construct_event", return_value=test_event):
            result = stripe_service.verify_webhook_signature(
                payload=b'{"test": "payload"}',
                signature="t=123,v1=abc",
            )

        assert result["id"] == "evt_test_123"
        assert result["type"] == "checkout.session.completed"

    def test_raises_error_on_invalid_signature(
        self,
        stripe_service: StripeService,
    ):
        """Raises StripeServiceError for invalid signature."""
        with patch(
            "stripe.Webhook.construct_event",
            side_effect=stripe.SignatureVerificationError("Invalid signature", "sig"),
        ):
            with pytest.raises(StripeServiceError) as exc_info:
                stripe_service.verify_webhook_signature(
                    payload=b'{"test": "payload"}',
                    signature="invalid",
                )

        assert "Invalid webhook signature" in str(exc_info.value)


# === T012-D: create_refund() Tests ===


class TestCreateRefund:
    """Test refund creation."""

    def test_creates_full_refund(
        self,
        stripe_service: StripeService,
        mock_stripe_client,
    ):
        """Creates full refund when amount not specified."""
        mock_refund = MagicMock()
        mock_refund.id = "re_test_123"
        mock_refund.amount = 112500
        mock_refund.status = "succeeded"
        mock_stripe_client.refunds.create.return_value = mock_refund

        result = stripe_service.create_refund(
            payment_intent_id="pi_test_456",
        )

        assert result["refund_id"] == "re_test_123"
        assert result["amount"] == 112500
        assert result["status"] == "succeeded"

        # Verify amount not included in params (full refund)
        call_kwargs = mock_stripe_client.refunds.create.call_args
        assert "amount" not in call_kwargs.kwargs["params"]

    def test_creates_partial_refund(
        self,
        stripe_service: StripeService,
        mock_stripe_client,
    ):
        """Creates partial refund with specified amount."""
        mock_refund = MagicMock()
        mock_refund.id = "re_test_123"
        mock_refund.amount = 56250  # 50% refund
        mock_refund.status = "succeeded"
        mock_stripe_client.refunds.create.return_value = mock_refund

        result = stripe_service.create_refund(
            payment_intent_id="pi_test_456",
            amount_cents=56250,
        )

        assert result["amount"] == 56250

        call_kwargs = mock_stripe_client.refunds.create.call_args
        assert call_kwargs.kwargs["params"]["amount"] == 56250

    def test_includes_reason_in_metadata(
        self,
        stripe_service: StripeService,
        mock_stripe_client,
    ):
        """Includes reason in refund metadata."""
        mock_refund = MagicMock()
        mock_refund.id = "re_test_123"
        mock_refund.amount = 112500
        mock_refund.status = "succeeded"
        mock_stripe_client.refunds.create.return_value = mock_refund

        stripe_service.create_refund(
            payment_intent_id="pi_test_456",
            reason="Guest requested cancellation",
        )

        call_kwargs = mock_stripe_client.refunds.create.call_args
        assert call_kwargs.kwargs["params"]["metadata"]["reason"] == "Guest requested cancellation"

    def test_raises_error_on_refund_failure(
        self,
        stripe_service: StripeService,
        mock_stripe_client,
    ):
        """Raises StripeServiceError when refund fails."""
        mock_stripe_client.refunds.create.side_effect = stripe.StripeError(
            "Refund already exists"
        )

        with pytest.raises(StripeServiceError) as exc_info:
            stripe_service.create_refund(payment_intent_id="pi_test_456")

        assert "Failed to create refund" in str(exc_info.value)


# === T012-E: Utility Methods ===


class TestUtilityMethods:
    """Test utility methods."""

    def test_compute_payload_hash(self):
        """Computes consistent SHA-256 hash."""
        payload = b'{"id": "evt_123", "type": "test"}'

        hash1 = StripeService.compute_payload_hash(payload)
        hash2 = StripeService.compute_payload_hash(payload)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length

    def test_different_payloads_different_hashes(self):
        """Different payloads produce different hashes."""
        payload1 = b'{"id": "evt_123"}'
        payload2 = b'{"id": "evt_456"}'

        hash1 = StripeService.compute_payload_hash(payload1)
        hash2 = StripeService.compute_payload_hash(payload2)

        assert hash1 != hash2


# === T012-F: Singleton Pattern ===


class TestSingletonPattern:
    """Test singleton instance management."""

    def test_get_stripe_service_returns_same_instance(self, mock_ssm_service):
        """get_stripe_service() returns cached instance."""
        from shared.services.stripe_service import get_stripe_service

        # Clear cache first
        get_stripe_service.cache_clear()

        instance1 = get_stripe_service()
        instance2 = get_stripe_service()

        assert instance1 is instance2

    def test_client_reused_across_calls(
        self,
        stripe_service: StripeService,
        mock_stripe_client,
    ):
        """Stripe client is reused, not recreated."""
        mock_session = MagicMock()
        mock_session.id = "cs_test_123"
        mock_session.url = "https://checkout.stripe.com/c/pay/cs_test_123"
        mock_session.expires_at = int(time.time()) + 1800
        mock_session.payment_intent = "pi_test_456"
        mock_stripe_client.checkout.sessions.create.return_value = mock_session

        # Make two calls
        stripe_service.create_checkout_session(
            reservation_id="RES-1",
            amount_cents=100,
            description="Test 1",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )
        stripe_service.create_checkout_session(
            reservation_id="RES-2",
            amount_cents=200,
            description="Test 2",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        # Client should have been reused
        assert stripe_service._client is not None
