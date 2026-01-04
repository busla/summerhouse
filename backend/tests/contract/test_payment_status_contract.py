"""Contract tests for GET /payments/{reservation_id} endpoint.

Tests verify the endpoint matches the contract specification (FR-028):
- Returns current payment status for a reservation
- Includes Stripe transaction ID if available
- Returns most recent completed payment when multiple exist

TDD: These tests are written FIRST and expected to FAIL until
the endpoint is implemented (T026+).

Test categories:
- T024-A: Not found handling (404)
- T024-B: Success response (200)
- T024-C: Response schema validation
- T024-D: Multiple payments handling
"""

import os
from datetime import datetime, timezone
from typing import Any, Generator

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from starlette.status import HTTP_200_OK, HTTP_404_NOT_FOUND

from api.main import app


# === Test Configuration ===

TEST_CUSTOMER_ID = "CUST-2026-TESTPAYMENT"
TEST_RESERVATION_ID = "RES-2026-PAYMENTSTATUS"
TEST_PAYMENT_ID = "PAY-2026-ABC123"


# === Test Fixtures ===


@pytest.fixture
def client() -> TestClient:
    """Create test client for API."""
    return TestClient(app)


@pytest.fixture
def mock_dynamodb_tables() -> Generator[None, None, None]:
    """Set up mock DynamoDB tables for testing."""
    with mock_aws():
        # Set up environment
        os.environ["DYNAMODB_TABLE_PREFIX"] = "test-booking"
        os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"

        db_client = boto3.client("dynamodb", region_name="eu-west-1")

        # Create reservations table
        db_client.create_table(
            TableName="test-booking-reservations",
            KeySchema=[{"AttributeName": "reservation_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "reservation_id", "AttributeType": "S"},
                {"AttributeName": "customer_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "customer_id-index",
                    "KeySchema": [{"AttributeName": "customer_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create customers table
        db_client.create_table(
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

        # Create payments table with reservation-index GSI
        # Note: index name is "reservation-index" (not "reservation_id-index")
        # to match PaymentService.get_payments_for_reservation()
        db_client.create_table(
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
def sample_reservation_in_db(mock_dynamodb_tables: None) -> dict[str, Any]:
    """Create sample reservation in mock DynamoDB."""
    resource = boto3.resource("dynamodb", region_name="eu-west-1")
    table = resource.Table("test-booking-reservations")

    reservation = {
        "reservation_id": TEST_RESERVATION_ID,
        "customer_id": TEST_CUSTOMER_ID,
        "check_in": "2026-07-15",
        "check_out": "2026-07-22",
        "num_adults": 2,
        "num_children": 0,
        "nights": 7,
        "status": "confirmed",
        "payment_status": "paid",
        "total_amount": 112500,
        "nightly_rate": 15000,
        "cleaning_fee": 7500,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=reservation)
    return reservation


@pytest.fixture
def sample_payment_in_db(
    mock_dynamodb_tables: None,
    sample_reservation_in_db: dict[str, Any],
) -> dict[str, Any]:
    """Create sample completed payment in mock DynamoDB."""
    resource = boto3.resource("dynamodb", region_name="eu-west-1")
    table = resource.Table("test-booking-payments")

    payment = {
        "payment_id": TEST_PAYMENT_ID,
        "reservation_id": TEST_RESERVATION_ID,
        "amount": 112500,
        "currency": "EUR",
        "status": "completed",
        "payment_method": "card",
        "provider": "stripe",
        "provider_transaction_id": "pi_3ABC123DEF456",
        "stripe_checkout_session_id": "cs_test_abc123def456",
        "stripe_payment_intent_id": "pi_3ABC123DEF456",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=payment)
    return payment


@pytest.fixture
def multiple_payments_in_db(
    mock_dynamodb_tables: None,
    sample_reservation_in_db: dict[str, Any],
) -> list[dict[str, Any]]:
    """Create multiple payments (one failed, one completed) for same reservation."""
    resource = boto3.resource("dynamodb", region_name="eu-west-1")
    table = resource.Table("test-booking-payments")

    # Failed payment (first attempt)
    failed_payment = {
        "payment_id": "PAY-2026-FAILED",
        "reservation_id": TEST_RESERVATION_ID,
        "amount": 112500,
        "currency": "EUR",
        "status": "failed",
        "payment_method": "card",
        "provider": "stripe",
        "error_message": "Card declined",
        "created_at": "2026-07-01T10:00:00+00:00",
    }
    table.put_item(Item=failed_payment)

    # Completed payment (second attempt)
    completed_payment = {
        "payment_id": "PAY-2026-SUCCESS",
        "reservation_id": TEST_RESERVATION_ID,
        "amount": 112500,
        "currency": "EUR",
        "status": "completed",
        "payment_method": "card",
        "provider": "stripe",
        "provider_transaction_id": "pi_success123",
        "stripe_checkout_session_id": "cs_test_success",
        "stripe_payment_intent_id": "pi_success123",
        "created_at": "2026-07-01T11:00:00+00:00",
        "completed_at": "2026-07-01T11:01:00+00:00",
    }
    table.put_item(Item=completed_payment)

    return [failed_payment, completed_payment]


# === T024-A: Not Found Tests ===


class TestPaymentStatusNotFound:
    """Tests for 404 responses when payment not found."""

    def test_returns_404_when_no_payment_for_reservation(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
    ) -> None:
        """GET /payments/{reservation_id} returns 404 when no payment exists."""
        response = client.get("/payments/RES-NONEXISTENT-123")

        assert response.status_code == HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data

    def test_returns_404_for_reservation_with_no_payments(
        self,
        client: TestClient,
        sample_reservation_in_db: dict[str, Any],
    ) -> None:
        """GET /payments/{reservation_id} returns 404 when reservation exists but no payment."""
        # Reservation exists but has no payment records
        response = client.get(f"/payments/{TEST_RESERVATION_ID}")

        assert response.status_code == HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data
        assert TEST_RESERVATION_ID in data["detail"]


# === T024-B: Success Tests ===


class TestPaymentStatusSuccess:
    """Tests for successful payment status retrieval."""

    def test_returns_200_with_payment_data(
        self,
        client: TestClient,
        sample_payment_in_db: dict[str, Any],
    ) -> None:
        """GET /payments/{reservation_id} returns 200 with payment data."""
        response = client.get(f"/payments/{TEST_RESERVATION_ID}")

        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["payment_id"] == TEST_PAYMENT_ID
        assert data["reservation_id"] == TEST_RESERVATION_ID
        assert data["status"] == "completed"

    def test_returns_stripe_transaction_id(
        self,
        client: TestClient,
        sample_payment_in_db: dict[str, Any],
    ) -> None:
        """GET /payments/{reservation_id} includes Stripe transaction ID (FR-028)."""
        response = client.get(f"/payments/{TEST_RESERVATION_ID}")

        assert response.status_code == HTTP_200_OK
        data = response.json()
        # Should include provider transaction ID
        assert data["provider_transaction_id"] == "pi_3ABC123DEF456"
        # Should include Stripe-specific fields
        assert data["stripe_checkout_session_id"] == "cs_test_abc123def456"
        assert data["stripe_payment_intent_id"] == "pi_3ABC123DEF456"


# === T024-C: Response Schema Tests ===


class TestPaymentStatusResponseSchema:
    """Tests for response schema compliance."""

    def test_response_has_required_fields(
        self,
        client: TestClient,
        sample_payment_in_db: dict[str, Any],
    ) -> None:
        """GET /payments/{reservation_id} returns all required Payment fields."""
        response = client.get(f"/payments/{TEST_RESERVATION_ID}")

        assert response.status_code == HTTP_200_OK
        data = response.json()

        # Required fields per Payment model
        required_fields = [
            "payment_id",
            "reservation_id",
            "amount",
            "currency",
            "status",
            "payment_method",
            "provider",
            "created_at",
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_amount_is_in_cents(
        self,
        client: TestClient,
        sample_payment_in_db: dict[str, Any],
    ) -> None:
        """GET /payments/{reservation_id} returns amount in EUR cents."""
        response = client.get(f"/payments/{TEST_RESERVATION_ID}")

        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["amount"] == 112500  # EUR cents
        assert data["currency"] == "EUR"

    def test_optional_fields_included_when_available(
        self,
        client: TestClient,
        sample_payment_in_db: dict[str, Any],
    ) -> None:
        """GET /payments/{reservation_id} includes optional fields when present."""
        response = client.get(f"/payments/{TEST_RESERVATION_ID}")

        assert response.status_code == HTTP_200_OK
        data = response.json()

        # These optional fields should be present for a completed Stripe payment
        optional_fields_when_completed = [
            "completed_at",
            "stripe_checkout_session_id",
            "stripe_payment_intent_id",
            "provider_transaction_id",
        ]

        for field in optional_fields_when_completed:
            assert field in data, f"Optional field should be present: {field}"


# === T024-D: Multiple Payments Tests ===


class TestPaymentStatusMultiplePayments:
    """Tests for handling multiple payments for same reservation."""

    def test_returns_completed_payment_over_failed(
        self,
        client: TestClient,
        multiple_payments_in_db: list[dict[str, Any]],
    ) -> None:
        """GET /payments/{reservation_id} returns completed payment when both exist."""
        response = client.get(f"/payments/{TEST_RESERVATION_ID}")

        assert response.status_code == HTTP_200_OK
        data = response.json()
        # Should return the completed payment, not the failed one
        assert data["status"] == "completed"
        assert data["payment_id"] == "PAY-2026-SUCCESS"

    def test_returns_most_recent_if_no_completed(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
        sample_reservation_in_db: dict[str, Any],
    ) -> None:
        """GET /payments/{reservation_id} returns most recent payment if none completed."""
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        table = resource.Table("test-booking-payments")

        # Create two pending payments
        for i, ts in enumerate(["2026-07-01T10:00:00+00:00", "2026-07-01T11:00:00+00:00"]):
            table.put_item(
                Item={
                    "payment_id": f"PAY-PENDING-{i}",
                    "reservation_id": TEST_RESERVATION_ID,
                    "amount": 112500,
                    "currency": "EUR",
                    "status": "pending",
                    "payment_method": "card",
                    "provider": "stripe",
                    "created_at": ts,
                }
            )

        response = client.get(f"/payments/{TEST_RESERVATION_ID}")

        assert response.status_code == HTTP_200_OK
        data = response.json()
        # Should return a payment even if none completed
        assert data["status"] == "pending"


# === T028: Payment History Tests ===


class TestPaymentHistory:
    """Tests for GET /payments/{reservation_id}/history endpoint (T028)."""

    def test_returns_200_for_empty_history(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
    ) -> None:
        """GET /payments/{reservation_id}/history returns 200 even with no payments."""
        response = client.get("/payments/RES-NONEXISTENT/history")

        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["reservation_id"] == "RES-NONEXISTENT"
        assert data["payments"] == []
        assert data["attempt_count"] == 0
        assert data["has_completed_payment"] is False
        assert data["current_status"] == "pending"
        assert data["total_paid"] == 0
        assert data["total_refunded"] == 0

    def test_returns_single_payment_in_list(
        self,
        client: TestClient,
        sample_payment_in_db: dict[str, Any],
    ) -> None:
        """GET /payments/{reservation_id}/history returns payment in list."""
        response = client.get(f"/payments/{TEST_RESERVATION_ID}/history")

        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["reservation_id"] == TEST_RESERVATION_ID
        assert len(data["payments"]) == 1
        assert data["payments"][0]["payment_id"] == TEST_PAYMENT_ID
        assert data["attempt_count"] == 1

    def test_returns_multiple_payments(
        self,
        client: TestClient,
        multiple_payments_in_db: list[dict[str, Any]],
    ) -> None:
        """GET /payments/{reservation_id}/history returns all payments."""
        response = client.get(f"/payments/{TEST_RESERVATION_ID}/history")

        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["attempt_count"] == 2
        assert len(data["payments"]) == 2

    def test_calculates_total_paid(
        self,
        client: TestClient,
        sample_payment_in_db: dict[str, Any],
    ) -> None:
        """GET /payments/{reservation_id}/history calculates total_paid from completed."""
        response = client.get(f"/payments/{TEST_RESERVATION_ID}/history")

        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["total_paid"] == 112500  # From the completed payment
        assert data["has_completed_payment"] is True
        assert data["current_status"] == "completed"

    def test_shows_failed_status_when_all_failed(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
        sample_reservation_in_db: dict[str, Any],
    ) -> None:
        """GET /payments/{reservation_id}/history shows failed when all payments failed."""
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        table = resource.Table("test-booking-payments")

        # Create only failed payment
        table.put_item(
            Item={
                "payment_id": "PAY-FAILED-ONLY",
                "reservation_id": TEST_RESERVATION_ID,
                "amount": 112500,
                "currency": "EUR",
                "status": "failed",
                "payment_method": "card",
                "provider": "stripe",
                "error_message": "Card declined",
                "created_at": "2026-07-01T10:00:00+00:00",
            }
        )

        response = client.get(f"/payments/{TEST_RESERVATION_ID}/history")

        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["current_status"] == "failed"
        assert data["has_completed_payment"] is False
        assert data["total_paid"] == 0

    def test_includes_refund_totals(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
        sample_reservation_in_db: dict[str, Any],
    ) -> None:
        """GET /payments/{reservation_id}/history includes refund totals."""
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        table = resource.Table("test-booking-payments")

        # Create refunded payment
        table.put_item(
            Item={
                "payment_id": "PAY-REFUNDED",
                "reservation_id": TEST_RESERVATION_ID,
                "amount": 112500,
                "currency": "EUR",
                "status": "refunded",
                "payment_method": "card",
                "provider": "stripe",
                "refund_amount": 56250,  # Partial refund
                "created_at": "2026-07-01T10:00:00+00:00",
                "completed_at": "2026-07-01T10:05:00+00:00",
                "refunded_at": "2026-07-02T14:30:00+00:00",
            }
        )

        response = client.get(f"/payments/{TEST_RESERVATION_ID}/history")

        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["current_status"] == "refunded"
        assert data["total_refunded"] == 56250
