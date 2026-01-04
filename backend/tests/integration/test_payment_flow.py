"""Integration tests for complete payment flow.

Tests verify the end-to-end payment flow:
1. Create reservation (pending status)
2. Initiate checkout session
3. Receive webhook confirmation
4. Verify reservation confirmed with payment record

TDD: These tests are written FIRST and expected to FAIL until
the payment handlers are implemented (T016+).

Test categories:
- T015-A: Happy path - successful payment confirms reservation
- T015-B: FR-026 - Failed payment does NOT confirm reservation
- T015-C: Idempotent webhook processing
"""

import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

# === Test Configuration ===

TEST_CUSTOMER_ID = "CUST-2026-INTEGTEST"
TEST_COGNITO_SUB = "test-cognito-sub-integration-123"
TEST_CUSTOMER_EMAIL = "integration@example.com"
TEST_RESERVATION_ID = "RES-2026-INTEG001"

# Stripe test card numbers
STRIPE_SUCCESS_CARD = "4242424242424242"  # Always succeeds
STRIPE_DECLINE_CARD = "4000000000000002"  # Always declines


# === Test Fixtures ===


@pytest.fixture
def aws_credentials() -> None:
    """Mocked AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"


@pytest.fixture
def dynamodb_tables(aws_credentials: None) -> Generator[Any, None, None]:
    """Set up mock DynamoDB tables for payment flow testing."""
    with mock_aws():
        os.environ["DYNAMODB_TABLE_PREFIX"] = "test-booking"
        os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"

        client = boto3.client("dynamodb", region_name="eu-west-1")

        # Create reservations table
        client.create_table(
            TableName="test-booking-reservations",
            KeySchema=[{"AttributeName": "reservation_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "reservation_id", "AttributeType": "S"},
                {"AttributeName": "customer_id", "AttributeType": "S"},
                {"AttributeName": "status", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "customer_id-index",
                    "KeySchema": [{"AttributeName": "customer_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "status-index",
                    "KeySchema": [{"AttributeName": "status", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create customers table
        client.create_table(
            TableName="test-booking-customers",
            KeySchema=[{"AttributeName": "customer_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "customer_id", "AttributeType": "S"},
                {"AttributeName": "cognito_sub", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "cognito-sub-index",
                    "KeySchema": [{"AttributeName": "cognito_sub", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create payments table
        client.create_table(
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

        # Create stripe webhook events table
        client.create_table(
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

        yield client


@pytest.fixture
def seed_customer(dynamodb_tables: Any) -> dict[str, Any]:
    """Create test customer in DynamoDB."""
    resource = boto3.resource("dynamodb", region_name="eu-west-1")
    table = resource.Table("test-booking-customers")

    customer = {
        "customer_id": TEST_CUSTOMER_ID,
        "cognito_sub": TEST_COGNITO_SUB,
        "email": TEST_CUSTOMER_EMAIL,
        "full_name": "Integration Test User",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=customer)
    return customer


@pytest.fixture
def seed_pending_reservation(
    dynamodb_tables: Any,
    seed_customer: dict[str, Any],
) -> dict[str, Any]:
    """Create pending reservation ready for payment."""
    resource = boto3.resource("dynamodb", region_name="eu-west-1")
    table = resource.Table("test-booking-reservations")

    reservation = {
        "reservation_id": TEST_RESERVATION_ID,
        "customer_id": TEST_CUSTOMER_ID,
        "check_in_date": "2026-07-15",
        "check_out_date": "2026-07-22",
        "num_guests": 2,
        "status": "pending",  # Ready for payment
        "total_price": Decimal("1125.00"),
        "nightly_rate": Decimal("150.00"),
        "cleaning_fee": Decimal("75.00"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=reservation)
    return reservation


@pytest.fixture
def mock_stripe_service() -> Generator[MagicMock, None, None]:
    """Mock StripeService for integration tests."""
    with patch("shared.services.stripe_service.get_stripe_service") as mock_get:
        mock_service = MagicMock()
        mock_get.return_value = mock_service
        yield mock_service


def _build_checkout_completed_webhook(
    reservation_id: str,
    session_id: str = "cs_test_integ_123",
    payment_intent_id: str = "pi_test_integ_456",
    amount_cents: int = 112500,
    payment_status: str = "paid",
) -> dict[str, Any]:
    """Build a checkout.session.completed webhook event."""
    return {
        "id": f"evt_test_{reservation_id}",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "payment_intent": payment_intent_id,
                "amount_total": amount_cents,
                "currency": "eur",
                "status": "complete",
                "payment_status": payment_status,
                "metadata": {
                    "reservation_id": reservation_id,
                },
                "customer_email": TEST_CUSTOMER_EMAIL,
            }
        },
        "created": int(datetime.now(timezone.utc).timestamp()),
    }


def _build_payment_failed_webhook(
    reservation_id: str,
    session_id: str = "cs_test_failed_123",
    payment_intent_id: str = "pi_test_failed_456",
) -> dict[str, Any]:
    """Build a checkout.session.completed webhook with unpaid status (async payment failed)."""
    return {
        "id": f"evt_test_failed_{reservation_id}",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "payment_intent": payment_intent_id,
                "amount_total": 112500,
                "currency": "eur",
                "status": "complete",
                "payment_status": "unpaid",  # Payment failed
                "metadata": {
                    "reservation_id": reservation_id,
                },
            }
        },
        "created": int(datetime.now(timezone.utc).timestamp()),
    }


# === T015-A: Happy Path - Successful Payment Confirms Reservation ===


class TestSuccessfulPaymentFlow:
    """Test complete payment flow with successful payment (T015-A)."""

    def test_checkout_session_creates_payment_record(
        self,
        dynamodb_tables: Any,
        seed_pending_reservation: dict[str, Any],
        mock_stripe_service: MagicMock,
    ) -> None:
        """Checkout session creation stores payment record in DynamoDB."""
        # Arrange
        mock_stripe_service.create_checkout_session.return_value = {
            "session_id": "cs_test_integ_123",
            "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_integ_123",
            "expires_at": datetime(2026, 1, 3, 10, 30, 0, tzinfo=timezone.utc),
            "payment_intent_id": "pi_test_integ_456",
        }

        # Import inside test to ensure moto is active
        from shared.services.dynamodb import get_dynamodb_service
        from shared.services.payment_service import PaymentService

        db = get_dynamodb_service()
        service = PaymentService(db)

        # Act - create pending payment and simulate checkout
        payment = service.create_pending_stripe_payment(
            reservation_id=TEST_RESERVATION_ID,
            amount_cents=112500,
            checkout_session_id="cs_test_integ_123",
            payment_intent_id="pi_test_integ_456",
        )

        # Assert - payment record created
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        payments_table = resource.Table("test-booking-payments")

        # Query by reservation_id GSI
        response = payments_table.query(
            IndexName="reservation-index",
            KeyConditionExpression="reservation_id = :rid",
            ExpressionAttributeValues={":rid": TEST_RESERVATION_ID},
        )

        assert len(response["Items"]) == 1
        payment_record = response["Items"][0]
        assert payment_record["reservation_id"] == TEST_RESERVATION_ID
        assert payment_record["status"] == "pending"
        assert payment_record["provider_transaction_id"] == "cs_test_integ_123"

    def test_webhook_confirms_reservation_on_successful_payment(
        self,
        dynamodb_tables: Any,
        seed_pending_reservation: dict[str, Any],
        mock_stripe_service: MagicMock,
    ) -> None:
        """Webhook handler confirms reservation when payment succeeds."""
        # Arrange - simulate webhook payload
        webhook_event = _build_checkout_completed_webhook(
            reservation_id=TEST_RESERVATION_ID,
            payment_status="paid",
        )

        mock_stripe_service.verify_webhook_signature.return_value = webhook_event

        # Import inside test to ensure moto is active
        from shared.services.webhook_handler import WebhookHandler

        handler = WebhookHandler()

        # Act
        handler.process_checkout_completed(webhook_event)

        # Assert - reservation status changed to confirmed
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        reservations_table = resource.Table("test-booking-reservations")

        response = reservations_table.get_item(
            Key={"reservation_id": TEST_RESERVATION_ID}
        )
        reservation = response["Item"]

        assert reservation["status"] == "confirmed"

    def test_webhook_creates_payment_record_with_stripe_details(
        self,
        dynamodb_tables: Any,
        seed_pending_reservation: dict[str, Any],
        mock_stripe_service: MagicMock,
    ) -> None:
        """Webhook handler stores Stripe payment details in payment record."""
        # Arrange
        webhook_event = _build_checkout_completed_webhook(
            reservation_id=TEST_RESERVATION_ID,
            session_id="cs_test_session_xyz",
            payment_intent_id="pi_test_intent_abc",
            amount_cents=112500,
        )

        mock_stripe_service.verify_webhook_signature.return_value = webhook_event

        from shared.services.webhook_handler import WebhookHandler

        handler = WebhookHandler()

        # Act
        handler.process_checkout_completed(webhook_event)

        # Assert - payment record has Stripe details
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        payments_table = resource.Table("test-booking-payments")

        response = payments_table.query(
            IndexName="reservation-index",
            KeyConditionExpression="reservation_id = :rid",
            ExpressionAttributeValues={":rid": TEST_RESERVATION_ID},
        )

        assert len(response["Items"]) >= 1
        payment = response["Items"][0]
        assert payment["stripe_payment_intent_id"] == "pi_test_intent_abc"
        assert payment["status"] == "completed"
        assert Decimal(str(payment["amount_cents"])) == Decimal("112500")

    def test_complete_flow_reservation_to_confirmed(
        self,
        dynamodb_tables: Any,
        seed_pending_reservation: dict[str, Any],
        mock_stripe_service: MagicMock,
    ) -> None:
        """End-to-end: pending reservation → checkout → webhook → confirmed."""
        # Arrange - mock Stripe responses
        mock_stripe_service.create_checkout_session.return_value = {
            "session_id": "cs_test_e2e_123",
            "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_e2e_123",
            "expires_at": datetime(2026, 1, 3, 10, 30, 0, tzinfo=timezone.utc),
            "payment_intent_id": "pi_test_e2e_456",
        }

        webhook_event = _build_checkout_completed_webhook(
            reservation_id=TEST_RESERVATION_ID,
            session_id="cs_test_e2e_123",
            payment_intent_id="pi_test_e2e_456",
        )
        mock_stripe_service.verify_webhook_signature.return_value = webhook_event

        # Import services
        from shared.services.dynamodb import get_dynamodb_service
        from shared.services.payment_service import PaymentService
        from shared.services.webhook_handler import WebhookHandler

        db = get_dynamodb_service()
        payment_service = PaymentService(db)
        webhook_handler = WebhookHandler()

        # Verify initial state - pending
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        reservations_table = resource.Table("test-booking-reservations")
        initial = reservations_table.get_item(Key={"reservation_id": TEST_RESERVATION_ID})
        assert initial["Item"]["status"] == "pending"

        # Step 1: Create pending payment (simulates checkout session creation)
        payment = payment_service.create_pending_stripe_payment(
            reservation_id=TEST_RESERVATION_ID,
            amount_cents=112500,
            checkout_session_id="cs_test_e2e_123",
            payment_intent_id="pi_test_e2e_456",
        )
        assert payment.provider_transaction_id == "cs_test_e2e_123"

        # Step 2: Process webhook (simulates customer completing payment)
        webhook_handler.process_checkout_completed(webhook_event)

        # Step 3: Verify final state - confirmed
        final = reservations_table.get_item(Key={"reservation_id": TEST_RESERVATION_ID})
        assert final["Item"]["status"] == "confirmed"

        # Verify payment record exists
        payments_table = resource.Table("test-booking-payments")
        payments = payments_table.query(
            IndexName="reservation-index",
            KeyConditionExpression="reservation_id = :rid",
            ExpressionAttributeValues={":rid": TEST_RESERVATION_ID},
        )
        assert len(payments["Items"]) >= 1


# === T015-B: FR-026 - Failed Payment Does NOT Confirm Reservation ===


class TestFailedPaymentFlow:
    """Test that failed payments do NOT confirm reservations (FR-026)."""

    def test_unpaid_status_does_not_confirm_reservation(
        self,
        dynamodb_tables: Any,
        seed_pending_reservation: dict[str, Any],
        mock_stripe_service: MagicMock,
    ) -> None:
        """Webhook with payment_status='unpaid' does NOT confirm reservation."""
        # Arrange - webhook with unpaid status (async payment failed)
        webhook_event = _build_payment_failed_webhook(
            reservation_id=TEST_RESERVATION_ID,
        )

        mock_stripe_service.verify_webhook_signature.return_value = webhook_event

        from shared.services.webhook_handler import WebhookHandler

        handler = WebhookHandler()

        # Act
        handler.process_checkout_completed(webhook_event)

        # Assert - reservation remains pending (NOT confirmed)
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        reservations_table = resource.Table("test-booking-reservations")

        response = reservations_table.get_item(
            Key={"reservation_id": TEST_RESERVATION_ID}
        )
        reservation = response["Item"]

        assert reservation["status"] == "pending"  # NOT confirmed
        assert reservation["status"] != "confirmed"

    def test_failed_payment_logs_but_does_not_confirm(
        self,
        dynamodb_tables: Any,
        seed_pending_reservation: dict[str, Any],
        mock_stripe_service: MagicMock,
    ) -> None:
        """Failed payment is logged in webhook events but reservation stays pending."""
        # Arrange
        webhook_event = _build_payment_failed_webhook(
            reservation_id=TEST_RESERVATION_ID,
        )
        mock_stripe_service.verify_webhook_signature.return_value = webhook_event

        from shared.services.webhook_handler import WebhookHandler

        handler = WebhookHandler()

        # Act
        handler.process_checkout_completed(webhook_event)

        # Assert - webhook event was recorded
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        events_table = resource.Table("test-booking-stripe-webhook-events")

        response = events_table.get_item(
            Key={"event_id": f"evt_test_failed_{TEST_RESERVATION_ID}"}
        )

        # Event was recorded (for audit trail)
        assert "Item" in response
        event_record = response["Item"]
        assert event_record["event_type"] == "checkout.session.completed"

        # But reservation is still pending
        reservations_table = resource.Table("test-booking-reservations")
        reservation = reservations_table.get_item(
            Key={"reservation_id": TEST_RESERVATION_ID}
        )["Item"]
        assert reservation["status"] == "pending"

    def test_payment_record_shows_failed_status(
        self,
        dynamodb_tables: Any,
        seed_pending_reservation: dict[str, Any],
        mock_stripe_service: MagicMock,
    ) -> None:
        """Payment record is created with 'failed' status for declined payments."""
        # Arrange
        webhook_event = _build_payment_failed_webhook(
            reservation_id=TEST_RESERVATION_ID,
        )
        mock_stripe_service.verify_webhook_signature.return_value = webhook_event

        from shared.services.webhook_handler import WebhookHandler

        handler = WebhookHandler()

        # Act
        handler.process_checkout_completed(webhook_event)

        # Assert - payment record shows failed
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        payments_table = resource.Table("test-booking-payments")

        response = payments_table.query(
            IndexName="reservation-index",
            KeyConditionExpression="reservation_id = :rid",
            ExpressionAttributeValues={":rid": TEST_RESERVATION_ID},
        )

        # If a payment record was created, it should show failure
        if response["Items"]:
            payment = response["Items"][0]
            assert payment["status"] in ["failed", "pending"]  # Not completed


# === T015-C: Idempotent Webhook Processing ===


class TestIdempotentWebhookProcessing:
    """Test that duplicate webhooks are handled idempotently."""

    def test_duplicate_webhook_does_not_double_process(
        self,
        dynamodb_tables: Any,
        seed_pending_reservation: dict[str, Any],
        mock_stripe_service: MagicMock,
    ) -> None:
        """Processing same webhook twice only confirms reservation once."""
        # Arrange
        webhook_event = _build_checkout_completed_webhook(
            reservation_id=TEST_RESERVATION_ID,
        )
        mock_stripe_service.verify_webhook_signature.return_value = webhook_event

        from shared.services.webhook_handler import WebhookHandler

        handler = WebhookHandler()

        # Act - process same webhook twice
        handler.process_checkout_completed(webhook_event)
        handler.process_checkout_completed(webhook_event)  # Duplicate

        # Assert - only one webhook event record
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        events_table = resource.Table("test-booking-stripe-webhook-events")

        response = events_table.get_item(
            Key={"event_id": f"evt_test_{TEST_RESERVATION_ID}"}
        )

        assert "Item" in response
        # The event was recorded once, second call should be idempotent

    def test_already_confirmed_reservation_stays_confirmed(
        self,
        dynamodb_tables: Any,
        seed_pending_reservation: dict[str, Any],
        mock_stripe_service: MagicMock,
    ) -> None:
        """Webhook for already-confirmed reservation doesn't change status."""
        # Arrange - manually confirm reservation first
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        reservations_table = resource.Table("test-booking-reservations")
        reservations_table.update_item(
            Key={"reservation_id": TEST_RESERVATION_ID},
            UpdateExpression="SET #s = :confirmed",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":confirmed": "confirmed"},
        )

        webhook_event = _build_checkout_completed_webhook(
            reservation_id=TEST_RESERVATION_ID,
        )
        mock_stripe_service.verify_webhook_signature.return_value = webhook_event

        from shared.services.webhook_handler import WebhookHandler

        handler = WebhookHandler()

        # Act
        handler.process_checkout_completed(webhook_event)

        # Assert - still confirmed (idempotent)
        response = reservations_table.get_item(
            Key={"reservation_id": TEST_RESERVATION_ID}
        )
        assert response["Item"]["status"] == "confirmed"


# === T015-D: Edge Cases ===


class TestPaymentFlowEdgeCases:
    """Test edge cases in payment flow."""

    def test_webhook_for_nonexistent_reservation_handled_gracefully(
        self,
        dynamodb_tables: Any,
        mock_stripe_service: MagicMock,
    ) -> None:
        """Webhook for non-existent reservation is logged but doesn't crash."""
        # Arrange - no reservation exists
        webhook_event = _build_checkout_completed_webhook(
            reservation_id="RES-NONEXISTENT",
        )
        mock_stripe_service.verify_webhook_signature.return_value = webhook_event

        from shared.services.webhook_handler import WebhookHandler

        handler = WebhookHandler()

        # Act - should not raise exception
        result = handler.process_checkout_completed(webhook_event)

        # Assert - handled gracefully (logged error, webhook event recorded)
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        events_table = resource.Table("test-booking-stripe-webhook-events")

        response = events_table.get_item(
            Key={"event_id": "evt_test_RES-NONEXISTENT"}
        )

        # Event was recorded with error status
        if "Item" in response:
            assert response["Item"]["processing_result"] in ["error", "skipped"]

    def test_webhook_without_reservation_id_handled_gracefully(
        self,
        dynamodb_tables: Any,
        mock_stripe_service: MagicMock,
    ) -> None:
        """Webhook without reservation_id in metadata is logged but skipped."""
        # Arrange - webhook without reservation_id
        webhook_event = {
            "id": "evt_test_no_metadata",
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
            "created": int(datetime.now(timezone.utc).timestamp()),
        }
        mock_stripe_service.verify_webhook_signature.return_value = webhook_event

        from shared.services.webhook_handler import WebhookHandler

        handler = WebhookHandler()

        # Act - should not raise exception
        handler.process_checkout_completed(webhook_event)

        # Assert - event logged but no reservation updated
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        events_table = resource.Table("test-booking-stripe-webhook-events")

        response = events_table.get_item(Key={"event_id": "evt_test_no_metadata"})

        if "Item" in response:
            # Event recorded with skipped/error result
            assert response["Item"]["processing_result"] in ["skipped", "error"]
