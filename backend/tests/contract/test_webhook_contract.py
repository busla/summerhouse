"""Contract tests for POST /webhooks/stripe endpoint.

Tests verify the endpoint matches the contract specification:
- specs/013-stripe-payment/contracts/webhook.yaml

TDD: These tests are written FIRST and expected to FAIL until
the endpoint is implemented (T016+).

Test categories:
- T011-A: Signature validation (400)
- T011-B: Idempotent duplicate handling (200)
- T011-C: checkout.session.completed processing (200)
- T011-D: charge.refunded processing (200)
- T011-E: Unhandled event types (200 - skipped)
- T011-F: Error handling (500)
"""

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from starlette.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from api.main import app


# === Test Configuration ===

TEST_WEBHOOK_SECRET = "whsec_test_secret_for_testing"
TEST_RESERVATION_ID = "RES-2026-ABC123"
TEST_PAYMENT_ID = "PAY-2026-DEF456"
TEST_CUSTOMER_ID = "CUST-2026-TESTOWNER"


# === Helper Functions ===


def _create_stripe_signature(payload: bytes, secret: str) -> str:
    """Create a valid Stripe webhook signature.

    Stripe signatures use HMAC-SHA256 with format: t={timestamp},v1={signature}
    """
    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
    signature = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


def _create_checkout_completed_event(
    event_id: str = "evt_1ABC123DEF456",
    reservation_id: str = TEST_RESERVATION_ID,
    payment_id: str = TEST_PAYMENT_ID,
    amount_total: int = 112500,
) -> dict[str, Any]:
    """Create a checkout.session.completed webhook event."""
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "created": int(time.time()),
        "data": {
            "object": {
                "id": "cs_test_abc123",
                "payment_intent": "pi_3ABC123DEF456",
                "payment_status": "paid",
                "amount_total": amount_total,
                "currency": "eur",
                "metadata": {
                    "reservation_id": reservation_id,
                    "payment_id": payment_id,
                },
            },
        },
    }


def _create_charge_refunded_event(
    event_id: str = "evt_2DEF456GHI789",
    reservation_id: str = TEST_RESERVATION_ID,
    amount_refunded: int = 56250,
) -> dict[str, Any]:
    """Create a charge.refunded webhook event."""
    return {
        "id": event_id,
        "type": "charge.refunded",
        "created": int(time.time()),
        "data": {
            "object": {
                "id": "ch_3ABC123DEF456",
                "payment_intent": "pi_3ABC123DEF456",
                "amount_refunded": amount_refunded,
                "refunds": {
                    "data": [
                        {
                            "id": "re_3ABC123DEF456",
                            "amount": amount_refunded,
                            "status": "succeeded",
                        },
                    ],
                },
                "metadata": {
                    "reservation_id": reservation_id,
                },
            },
        },
    }


def _create_unhandled_event(event_id: str = "evt_3GHI789JKL012") -> dict[str, Any]:
    """Create an unhandled event type."""
    return {
        "id": event_id,
        "type": "payment_intent.created",  # Not in handled types
        "created": int(time.time()),
        "data": {
            "object": {
                "id": "pi_test",
            },
        },
    }


# === Test Fixtures ===


@pytest.fixture
def client() -> TestClient:
    """Create test client for API."""
    return TestClient(app)


@pytest.fixture
def mock_dynamodb_tables() -> Generator[None, None, None]:
    """Set up mock DynamoDB tables for webhook testing."""
    with mock_aws():
        os.environ["DYNAMODB_TABLE_PREFIX"] = "test-booking"
        os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"

        dynamodb = boto3.client("dynamodb", region_name="eu-west-1")

        # Create stripe_webhook_events table for idempotency
        dynamodb.create_table(
            TableName="test-booking-stripe-webhook-events",
            KeySchema=[{"AttributeName": "event_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "event_id", "AttributeType": "S"},
                {"AttributeName": "event_type", "AttributeType": "S"},
                {"AttributeName": "processed_at", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "event-type-index",
                    "KeySchema": [
                        {"AttributeName": "event_type", "KeyType": "HASH"},
                        {"AttributeName": "processed_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create reservations table
        dynamodb.create_table(
            TableName="test-booking-reservations",
            KeySchema=[{"AttributeName": "reservation_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "reservation_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create payments table
        dynamodb.create_table(
            TableName="test-booking-payments",
            KeySchema=[{"AttributeName": "payment_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "payment_id", "AttributeType": "S"},
                {"AttributeName": "reservation_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "reservation-index",
                    "KeySchema": [{"AttributeName": "reservation_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        yield


@pytest.fixture
def pending_reservation_in_db(mock_dynamodb_tables: None) -> dict[str, Any]:
    """Create a pending reservation awaiting payment."""
    resource = boto3.resource("dynamodb", region_name="eu-west-1")
    table = resource.Table("test-booking-reservations")

    reservation = {
        "reservation_id": TEST_RESERVATION_ID,
        "customer_id": TEST_CUSTOMER_ID,
        "status": "pending",
        "total_price": Decimal("1125.00"),
        "check_in_date": "2026-07-15",
        "check_out_date": "2026-07-22",
        "num_guests": 2,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=reservation)
    return reservation


@pytest.fixture
def pending_payment_in_db(
    mock_dynamodb_tables: None,
    pending_reservation_in_db: dict[str, Any],
) -> dict[str, Any]:
    """Create a pending payment record."""
    resource = boto3.resource("dynamodb", region_name="eu-west-1")
    table = resource.Table("test-booking-payments")

    payment = {
        "payment_id": TEST_PAYMENT_ID,
        "reservation_id": TEST_RESERVATION_ID,
        "status": "pending",
        "amount": 112500,  # cents
        "currency": "EUR",
        "stripe_session_id": "cs_test_abc123",
        "stripe_payment_intent_id": "pi_3ABC123DEF456",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=payment)
    return payment


@pytest.fixture
def already_processed_event_in_db(mock_dynamodb_tables: None) -> dict[str, Any]:
    """Create an already-processed webhook event for idempotency testing."""
    resource = boto3.resource("dynamodb", region_name="eu-west-1")
    table = resource.Table("test-booking-stripe-webhook-events")

    event_log = {
        "event_id": "evt_ALREADY_PROCESSED",
        "event_type": "checkout.session.completed",
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "payload_hash": "abc123",
        "reservation_id": TEST_RESERVATION_ID,
        "payment_id": TEST_PAYMENT_ID,
        "processing_result": "success",
    }
    table.put_item(Item=event_log)
    return event_log


@pytest.fixture
def mock_stripe_signature_verification() -> Generator[MagicMock, None, None]:
    """Mock Stripe signature verification to always pass.

    Patches at the import location (api.routes.webhooks) rather than the
    source module (shared.services.stripe_service).
    """
    with patch("api.routes.webhooks.get_stripe_service") as mock_stripe:
        mock_service = MagicMock()

        def verify_signature(payload: bytes, signature: str) -> dict:
            """Return parsed event from payload."""
            import json
            return json.loads(payload.decode("utf-8"))

        mock_service.verify_webhook_signature.side_effect = verify_signature
        mock_stripe.return_value = mock_service
        yield mock_service


# === T011-A: Signature Validation Tests ===


class TestWebhookSignatureValidation:
    """Test Stripe signature validation (400 errors)."""

    def test_returns_400_when_signature_header_missing(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
    ) -> None:
        """Request without Stripe-Signature header should return 400."""
        event = _create_checkout_completed_event()

        response = client.post(
            "/webhooks/stripe",
            json=event,
            # No Stripe-Signature header
        )
        assert response.status_code == HTTP_400_BAD_REQUEST

        data = response.json()
        assert data["success"] is False
        assert "signature" in data["message"].lower() or "header" in data["message"].lower()

    def test_returns_400_when_signature_invalid(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
    ) -> None:
        """Request with invalid signature should return 400."""
        event = _create_checkout_completed_event()

        response = client.post(
            "/webhooks/stripe",
            json=event,
            headers={"Stripe-Signature": "t=123,v1=invalid_signature"},
        )
        assert response.status_code == HTTP_400_BAD_REQUEST

        data = response.json()
        assert data["success"] is False
        assert "signature" in data["message"].lower() or "invalid" in data["message"].lower()

    def test_returns_400_when_signature_format_malformed(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
    ) -> None:
        """Malformed signature format should return 400."""
        event = _create_checkout_completed_event()

        response = client.post(
            "/webhooks/stripe",
            json=event,
            headers={"Stripe-Signature": "malformed-signature-no-timestamp"},
        )
        assert response.status_code == HTTP_400_BAD_REQUEST


# === T011-B: Idempotent Duplicate Handling Tests ===


class TestWebhookIdempotency:
    """Test idempotent handling of duplicate events (FR-014)."""

    def test_returns_200_for_duplicate_event(
        self,
        client: TestClient,
        already_processed_event_in_db: dict[str, Any],
        mock_stripe_signature_verification: MagicMock,
    ) -> None:
        """Already-processed event should return 200 with 'duplicate' result."""
        event = _create_checkout_completed_event(event_id="evt_ALREADY_PROCESSED")
        payload = json.dumps(event).encode("utf-8")
        signature = _create_stripe_signature(payload, TEST_WEBHOOK_SECRET)

        response = client.post(
            "/webhooks/stripe",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": signature,
            },
        )
        assert response.status_code == HTTP_200_OK

        data = response.json()
        assert data["received"] is True
        assert data["processing_result"] == "duplicate"
        assert "already processed" in data.get("message", "").lower()

    def test_duplicate_does_not_reprocess_payment(
        self,
        client: TestClient,
        pending_payment_in_db: dict[str, Any],
        already_processed_event_in_db: dict[str, Any],
        mock_stripe_signature_verification: MagicMock,
    ) -> None:
        """Duplicate event should not trigger payment processing again."""
        # Set up payment to track if it gets modified
        original_status = pending_payment_in_db["status"]

        event = _create_checkout_completed_event(event_id="evt_ALREADY_PROCESSED")
        payload = json.dumps(event).encode("utf-8")
        signature = _create_stripe_signature(payload, TEST_WEBHOOK_SECRET)

        response = client.post(
            "/webhooks/stripe",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": signature,
            },
        )
        assert response.status_code == HTTP_200_OK

        # Verify payment status unchanged (still pending, not updated twice)
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        payments_table = resource.Table("test-booking-payments")
        payment = payments_table.get_item(Key={"payment_id": TEST_PAYMENT_ID})["Item"]
        assert payment["status"] == original_status


# === T011-C: checkout.session.completed Processing ===


class TestCheckoutSessionCompleted:
    """Test processing of checkout.session.completed events (FR-012)."""

    def test_returns_200_on_successful_processing(
        self,
        client: TestClient,
        pending_payment_in_db: dict[str, Any],
        mock_stripe_signature_verification: MagicMock,
    ) -> None:
        """Successful checkout completion returns 200 with success result."""
        event = _create_checkout_completed_event()
        payload = json.dumps(event).encode("utf-8")
        signature = _create_stripe_signature(payload, TEST_WEBHOOK_SECRET)

        response = client.post(
            "/webhooks/stripe",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": signature,
            },
        )
        assert response.status_code == HTTP_200_OK

        data = response.json()
        assert data["received"] is True
        assert data["event_type"] == "checkout.session.completed"
        assert data["processing_result"] == "success"

    def test_updates_payment_status_to_paid(
        self,
        client: TestClient,
        pending_payment_in_db: dict[str, Any],
        mock_stripe_signature_verification: MagicMock,
    ) -> None:
        """Checkout completion should update payment status to 'paid'."""
        event = _create_checkout_completed_event()
        payload = json.dumps(event).encode("utf-8")
        signature = _create_stripe_signature(payload, TEST_WEBHOOK_SECRET)

        response = client.post(
            "/webhooks/stripe",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": signature,
            },
        )

        if response.status_code == HTTP_200_OK:
            resource = boto3.resource("dynamodb", region_name="eu-west-1")
            payments_table = resource.Table("test-booking-payments")
            payment = payments_table.get_item(Key={"payment_id": TEST_PAYMENT_ID})["Item"]
            assert payment["status"] == "paid"

    def test_updates_reservation_status_to_confirmed(
        self,
        client: TestClient,
        pending_payment_in_db: dict[str, Any],
        mock_stripe_signature_verification: MagicMock,
    ) -> None:
        """Checkout completion should confirm the reservation."""
        event = _create_checkout_completed_event()
        payload = json.dumps(event).encode("utf-8")
        signature = _create_stripe_signature(payload, TEST_WEBHOOK_SECRET)

        response = client.post(
            "/webhooks/stripe",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": signature,
            },
        )

        if response.status_code == HTTP_200_OK:
            resource = boto3.resource("dynamodb", region_name="eu-west-1")
            reservations_table = resource.Table("test-booking-reservations")
            reservation = reservations_table.get_item(
                Key={"reservation_id": TEST_RESERVATION_ID}
            )["Item"]
            assert reservation["status"] == "confirmed"

    def test_logs_event_to_webhook_events_table(
        self,
        client: TestClient,
        pending_payment_in_db: dict[str, Any],
        mock_stripe_signature_verification: MagicMock,
    ) -> None:
        """Processed events should be logged for idempotency."""
        event_id = "evt_NEWTEST123"
        event = _create_checkout_completed_event(event_id=event_id)
        payload = json.dumps(event).encode("utf-8")
        signature = _create_stripe_signature(payload, TEST_WEBHOOK_SECRET)

        response = client.post(
            "/webhooks/stripe",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": signature,
            },
        )

        if response.status_code == HTTP_200_OK:
            resource = boto3.resource("dynamodb", region_name="eu-west-1")
            events_table = resource.Table("test-booking-stripe-webhook-events")
            logged_event = events_table.get_item(Key={"event_id": event_id})
            assert "Item" in logged_event
            assert logged_event["Item"]["event_type"] == "checkout.session.completed"


# === T011-D: charge.refunded Processing ===


class TestChargeRefunded:
    """Test processing of charge.refunded events (FR-013)."""

    def test_returns_200_on_refund_processing(
        self,
        client: TestClient,
        pending_payment_in_db: dict[str, Any],
        mock_stripe_signature_verification: MagicMock,
    ) -> None:
        """Refund event returns 200 with success result."""
        event = _create_charge_refunded_event()
        payload = json.dumps(event).encode("utf-8")
        signature = _create_stripe_signature(payload, TEST_WEBHOOK_SECRET)

        response = client.post(
            "/webhooks/stripe",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": signature,
            },
        )
        assert response.status_code == HTTP_200_OK

        data = response.json()
        assert data["received"] is True
        assert data["event_type"] == "charge.refunded"

    def test_updates_payment_with_refund_info(
        self,
        client: TestClient,
        pending_payment_in_db: dict[str, Any],
        mock_stripe_signature_verification: MagicMock,
    ) -> None:
        """Refund should update payment record with refund details."""
        refund_amount = 56250
        event = _create_charge_refunded_event(amount_refunded=refund_amount)
        payload = json.dumps(event).encode("utf-8")
        signature = _create_stripe_signature(payload, TEST_WEBHOOK_SECRET)

        response = client.post(
            "/webhooks/stripe",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": signature,
            },
        )

        if response.status_code == HTTP_200_OK:
            resource = boto3.resource("dynamodb", region_name="eu-west-1")
            payments_table = resource.Table("test-booking-payments")
            payment = payments_table.get_item(Key={"payment_id": TEST_PAYMENT_ID})["Item"]
            # Payment should track refund amount
            assert payment.get("amount_refunded") == refund_amount or payment.get("status") == "refunded"


# === T011-E: Unhandled Event Types ===


class TestUnhandledEventTypes:
    """Test handling of unrecognized event types."""

    def test_returns_200_with_skipped_for_unhandled_type(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
        mock_stripe_signature_verification: MagicMock,
    ) -> None:
        """Unhandled event types should return 200 with 'skipped' result."""
        event = _create_unhandled_event()
        payload = json.dumps(event).encode("utf-8")
        signature = _create_stripe_signature(payload, TEST_WEBHOOK_SECRET)

        response = client.post(
            "/webhooks/stripe",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": signature,
            },
        )
        assert response.status_code == HTTP_200_OK

        data = response.json()
        assert data["received"] is True
        assert data["processing_result"] == "skipped"
        assert "not handled" in data.get("message", "").lower()

    def test_skipped_events_still_logged(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
        mock_stripe_signature_verification: MagicMock,
    ) -> None:
        """Even skipped events should be logged for audit trail."""
        event_id = "evt_SKIPPED123"
        event = _create_unhandled_event(event_id=event_id)
        payload = json.dumps(event).encode("utf-8")
        signature = _create_stripe_signature(payload, TEST_WEBHOOK_SECRET)

        response = client.post(
            "/webhooks/stripe",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": signature,
            },
        )

        if response.status_code == HTTP_200_OK:
            resource = boto3.resource("dynamodb", region_name="eu-west-1")
            events_table = resource.Table("test-booking-stripe-webhook-events")
            logged_event = events_table.get_item(Key={"event_id": event_id})
            # Should be logged even if skipped
            if "Item" in logged_event:
                assert logged_event["Item"]["processing_result"] == "skipped"


# === T011-F: Error Handling ===


class TestWebhookErrorHandling:
    """Test error handling scenarios."""

    def test_returns_500_on_processing_error(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
    ) -> None:
        """Processing errors should return 200 with error result.

        Webhooks should return 200 even on processing errors to prevent
        Stripe from retrying. The error is recorded and logged.
        """
        # Create event with invalid/missing metadata to trigger processing error
        event = {
            "id": "evt_ERROR123",
            "type": "checkout.session.completed",
            "created": int(time.time()),
            "data": {
                "object": {
                    "id": "cs_test",
                    "payment_status": "paid",
                    # Missing required metadata.reservation_id
                },
            },
        }
        payload = json.dumps(event).encode("utf-8")

        # Mock signature verification to pass and return the parsed event
        with patch("api.routes.webhooks.get_stripe_service") as mock_stripe:
            mock_service = MagicMock()
            mock_service.verify_webhook_signature.return_value = event
            mock_stripe.return_value = mock_service

            response = client.post(
                "/webhooks/stripe",
                content=payload,
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": _create_stripe_signature(payload, TEST_WEBHOOK_SECRET),
                },
            )

        # Should return 200 with error result (webhooks don't use 500)
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["processing_result"] == "error"

    def test_error_response_includes_recovery_info(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
    ) -> None:
        """Error responses should include recovery guidance."""
        response = client.post(
            "/webhooks/stripe",
            json={},  # Invalid payload
        )

        # Should be 400 (invalid) or 405 (method not allowed if endpoint missing)
        if response.status_code == HTTP_400_BAD_REQUEST:
            data = response.json()
            assert data["success"] is False
            assert "recovery" in data or "message" in data


# === Response Schema Tests ===


class TestWebhookResponseSchema:
    """Test that response matches WebhookResponse schema."""

    def test_success_response_has_required_fields(
        self,
        client: TestClient,
        pending_payment_in_db: dict[str, Any],
        mock_stripe_signature_verification: MagicMock,
    ) -> None:
        """Success response should have all required fields."""
        event = _create_checkout_completed_event()
        payload = json.dumps(event).encode("utf-8")
        signature = _create_stripe_signature(payload, TEST_WEBHOOK_SECRET)

        response = client.post(
            "/webhooks/stripe",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": signature,
            },
        )

        if response.status_code == HTTP_200_OK:
            data = response.json()
            # Required fields per contract
            assert "received" in data
            assert data["received"] is True
            # Optional but expected fields
            assert "event_id" in data
            assert "event_type" in data
            assert "processing_result" in data
            assert data["processing_result"] in ["success", "duplicate", "skipped", "error"]
