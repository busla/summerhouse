"""Contract tests for POST /payments/refund/{payment_id} endpoint.

Tests verify the endpoint matches the contract specification (FR-030):
- Initiates refunds via Stripe API
- Applies refund policy based on check-in date
- Returns refund details including Stripe refund ID

TDD: These tests are written FIRST and expected to FAIL until
the endpoint is implemented (T035+).

Test categories:
- T029-A: Not found handling (404)
- T029-B: Success response (200)
- T029-C: Authorization checks
- T029-D: Policy enforcement
- T029-E: Error handling
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from starlette.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from api.main import app


# === Test Configuration ===

TEST_CUSTOMER_ID = "CUST-2026-REFUNDTEST"
TEST_RESERVATION_ID = "RES-2026-REFUNDTEST"
TEST_PAYMENT_ID = "PAY-2026-REFUNDTEST"
TEST_COGNITO_SUB = "test-cognito-sub-refund"


# === Test Fixtures ===


@pytest.fixture
def client() -> TestClient:
    """Create test client for API."""
    return TestClient(app)


@pytest.fixture
def mock_dynamodb_tables() -> Generator[None, None, None]:
    """Set up mock DynamoDB tables for testing."""
    with mock_aws():
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

        # Create payments table
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
def sample_customer_in_db(mock_dynamodb_tables: None) -> dict[str, Any]:
    """Create sample customer in mock DynamoDB."""
    resource = boto3.resource("dynamodb", region_name="eu-west-1")
    table = resource.Table("test-booking-customers")

    customer = {
        "customer_id": TEST_CUSTOMER_ID,
        "cognito_sub": TEST_COGNITO_SUB,
        "email": "refund-test@example.com",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=customer)
    return customer


def create_reservation_with_check_in(
    days_until_check_in: int,
    customer_id: str = TEST_CUSTOMER_ID,
) -> dict[str, Any]:
    """Create reservation with specific check-in date relative to today."""
    resource = boto3.resource("dynamodb", region_name="eu-west-1")
    table = resource.Table("test-booking-reservations")

    check_in = datetime.now(timezone.utc).date() + timedelta(days=days_until_check_in)
    check_out = check_in + timedelta(days=7)

    reservation = {
        "reservation_id": TEST_RESERVATION_ID,
        "customer_id": customer_id,
        "check_in": check_in.isoformat(),
        "check_out": check_out.isoformat(),
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
def sample_completed_payment(
    mock_dynamodb_tables: None,
    sample_customer_in_db: dict[str, Any],
) -> dict[str, Any]:
    """Create sample completed payment with Stripe IDs in mock DynamoDB."""
    resource = boto3.resource("dynamodb", region_name="eu-west-1")
    table = resource.Table("test-booking-payments")

    # Create reservation 20 days in the future (full refund eligible)
    create_reservation_with_check_in(days_until_check_in=20)

    payment = {
        "payment_id": TEST_PAYMENT_ID,
        "reservation_id": TEST_RESERVATION_ID,
        "amount": 112500,
        "currency": "EUR",
        "status": "completed",
        "payment_method": "card",
        "provider": "stripe",
        "provider_transaction_id": "pi_test_refund_123",
        "stripe_checkout_session_id": "cs_test_refund_session",
        "stripe_payment_intent_id": "pi_test_refund_123",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=payment)
    return payment


def get_auth_headers(cognito_sub: str = TEST_COGNITO_SUB) -> dict[str, str]:
    """Get headers that simulate JWT authentication."""
    return {"x-user-sub": cognito_sub}


# === T029-A: Not Found Tests ===


class TestRefundNotFound:
    """Tests for 404 responses when payment not found."""

    def test_returns_404_when_payment_not_found(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
        sample_customer_in_db: dict[str, Any],
    ) -> None:
        """POST /payments/refund/{payment_id} returns 404 for nonexistent payment."""
        response = client.post(
            "/payments/refund/PAY-NONEXISTENT-123",
            headers=get_auth_headers(),
            json={},
        )

        assert response.status_code == HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data


# === T029-B: Success Tests ===


class TestRefundSuccess:
    """Tests for successful refund processing."""

    def test_returns_200_with_refund_details(
        self,
        client: TestClient,
        sample_completed_payment: dict[str, Any],
    ) -> None:
        """POST /payments/refund/{payment_id} returns 200 with refund data."""
        with patch("api.routes.payments.get_stripe_service") as mock_get_stripe:
            mock_stripe = MagicMock()
            mock_stripe.create_refund.return_value = {
                "refund_id": "re_test_abc123",
                "amount": 112500,
                "status": "succeeded",
            }
            mock_get_stripe.return_value = mock_stripe

            response = client.post(
                f"/payments/refund/{TEST_PAYMENT_ID}",
                headers=get_auth_headers(),
                json={},
            )

        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["payment_id"] == TEST_PAYMENT_ID
        assert data["stripe_refund_id"] == "re_test_abc123"
        assert data["status"] == "succeeded"

    def test_full_refund_when_no_amount_specified(
        self,
        client: TestClient,
        sample_completed_payment: dict[str, Any],
    ) -> None:
        """POST /payments/refund/{payment_id} with no amount refunds full amount (policy permitting)."""
        with patch("api.routes.payments.get_stripe_service") as mock_get_stripe:
            mock_stripe = MagicMock()
            mock_stripe.create_refund.return_value = {
                "refund_id": "re_test_full",
                "amount": 112500,  # Full refund
                "status": "succeeded",
            }
            mock_get_stripe.return_value = mock_stripe

            response = client.post(
                f"/payments/refund/{TEST_PAYMENT_ID}",
                headers=get_auth_headers(),
                json={},  # No amount specified
            )

        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["amount"] == 112500

    def test_includes_refund_reason(
        self,
        client: TestClient,
        sample_completed_payment: dict[str, Any],
    ) -> None:
        """POST /payments/refund/{payment_id} passes reason to Stripe."""
        with patch("api.routes.payments.get_stripe_service") as mock_get_stripe:
            mock_stripe = MagicMock()
            mock_stripe.create_refund.return_value = {
                "refund_id": "re_test_reason",
                "amount": 112500,
                "status": "succeeded",
            }
            mock_get_stripe.return_value = mock_stripe

            response = client.post(
                f"/payments/refund/{TEST_PAYMENT_ID}",
                headers=get_auth_headers(),
                json={"reason": "Customer cancelled 20 days before check-in"},
            )

        assert response.status_code == HTTP_200_OK
        # Verify reason was passed to Stripe service
        mock_stripe.create_refund.assert_called_once()
        call_kwargs = mock_stripe.create_refund.call_args.kwargs
        assert call_kwargs["reason"] == "Customer cancelled 20 days before check-in"


# === T029-C: Authorization Tests ===


class TestRefundAuthorization:
    """Tests for refund authorization (T037)."""

    def test_returns_401_or_403_without_auth(
        self,
        client: TestClient,
        sample_completed_payment: dict[str, Any],
    ) -> None:
        """POST /payments/refund/{payment_id} requires authentication."""
        response = client.post(
            f"/payments/refund/{TEST_PAYMENT_ID}",
            json={},
            # No auth headers
        )

        # Either 401 (Unauthorized) or 403 (Forbidden) is acceptable for missing auth
        assert response.status_code in (HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN)

    def test_returns_403_for_non_owner(
        self,
        client: TestClient,
        sample_completed_payment: dict[str, Any],
    ) -> None:
        """POST /payments/refund/{payment_id} returns 403 for non-owner."""
        # Create a different customer
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        table = resource.Table("test-booking-customers")
        table.put_item(
            Item={
                "customer_id": "CUST-OTHER-USER",
                "cognito_sub": "other-user-sub",
                "email": "other@example.com",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        response = client.post(
            f"/payments/refund/{TEST_PAYMENT_ID}",
            headers=get_auth_headers("other-user-sub"),
            json={},
        )

        assert response.status_code == HTTP_403_FORBIDDEN


# === T029-D: Policy Enforcement Tests ===


class TestRefundPolicyEnforcement:
    """Tests for refund policy enforcement (FR-015, FR-016, FR-017)."""

    def test_full_refund_14_plus_days_before_check_in(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
        sample_customer_in_db: dict[str, Any],
    ) -> None:
        """14+ days before check-in gets 100% refund (FR-015)."""
        # Create reservation 15 days in future
        create_reservation_with_check_in(days_until_check_in=15)

        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        table = resource.Table("test-booking-payments")
        table.put_item(
            Item={
                "payment_id": "PAY-FULL-REFUND",
                "reservation_id": TEST_RESERVATION_ID,
                "amount": 112500,
                "currency": "EUR",
                "status": "completed",
                "payment_method": "card",
                "provider": "stripe",
                "stripe_payment_intent_id": "pi_full_refund",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        with patch("api.routes.payments.get_stripe_service") as mock_get_stripe:
            mock_stripe = MagicMock()
            mock_stripe.create_refund.return_value = {
                "refund_id": "re_full",
                "amount": 112500,
                "status": "succeeded",
            }
            mock_get_stripe.return_value = mock_stripe

            response = client.post(
                "/payments/refund/PAY-FULL-REFUND",
                headers=get_auth_headers(),
                json={},
            )

        assert response.status_code == HTTP_200_OK
        # Verify full amount was refunded
        mock_stripe.create_refund.assert_called_once()
        call_kwargs = mock_stripe.create_refund.call_args.kwargs
        assert call_kwargs["amount_cents"] == 112500  # Full refund

    def test_partial_refund_7_to_14_days_before_check_in(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
        sample_customer_in_db: dict[str, Any],
    ) -> None:
        """7-14 days before check-in gets 50% refund (FR-016)."""
        # Create reservation 10 days in future
        create_reservation_with_check_in(days_until_check_in=10)

        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        table = resource.Table("test-booking-payments")
        table.put_item(
            Item={
                "payment_id": "PAY-PARTIAL-REFUND",
                "reservation_id": TEST_RESERVATION_ID,
                "amount": 112500,
                "currency": "EUR",
                "status": "completed",
                "payment_method": "card",
                "provider": "stripe",
                "stripe_payment_intent_id": "pi_partial_refund",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        with patch("api.routes.payments.get_stripe_service") as mock_get_stripe:
            mock_stripe = MagicMock()
            mock_stripe.create_refund.return_value = {
                "refund_id": "re_partial",
                "amount": 56250,  # 50% of 112500
                "status": "succeeded",
            }
            mock_get_stripe.return_value = mock_stripe

            response = client.post(
                "/payments/refund/PAY-PARTIAL-REFUND",
                headers=get_auth_headers(),
                json={},
            )

        assert response.status_code == HTTP_200_OK
        # Verify 50% amount was refunded
        mock_stripe.create_refund.assert_called_once()
        call_kwargs = mock_stripe.create_refund.call_args.kwargs
        assert call_kwargs["amount_cents"] == 56250  # 50% refund

    def test_no_refund_under_7_days_before_check_in(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
        sample_customer_in_db: dict[str, Any],
    ) -> None:
        """Under 7 days before check-in gets no refund (FR-017)."""
        # Create reservation 5 days in future
        create_reservation_with_check_in(days_until_check_in=5)

        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        table = resource.Table("test-booking-payments")
        table.put_item(
            Item={
                "payment_id": "PAY-NO-REFUND",
                "reservation_id": TEST_RESERVATION_ID,
                "amount": 112500,
                "currency": "EUR",
                "status": "completed",
                "payment_method": "card",
                "provider": "stripe",
                "stripe_payment_intent_id": "pi_no_refund",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        response = client.post(
            "/payments/refund/PAY-NO-REFUND",
            headers=get_auth_headers(),
            json={},
        )

        # Should return 400 - no refund allowed
        assert response.status_code == HTTP_400_BAD_REQUEST
        data = response.json()
        assert "no refund" in data["detail"].lower() or "policy" in data["detail"].lower()


# === T029-E: Error Handling Tests ===


class TestRefundErrorHandling:
    """Tests for refund error handling."""

    def test_returns_400_for_unpaid_payment(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
        sample_customer_in_db: dict[str, Any],
    ) -> None:
        """POST /payments/refund/{payment_id} returns 400 for pending payment."""
        # Create reservation
        create_reservation_with_check_in(days_until_check_in=20)

        # Create pending payment (not completed)
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        table = resource.Table("test-booking-payments")
        table.put_item(
            Item={
                "payment_id": "PAY-PENDING-REFUND",
                "reservation_id": TEST_RESERVATION_ID,
                "amount": 112500,
                "currency": "EUR",
                "status": "pending",  # Not completed
                "payment_method": "card",
                "provider": "stripe",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        response = client.post(
            "/payments/refund/PAY-PENDING-REFUND",
            headers=get_auth_headers(),
            json={},
        )

        assert response.status_code == HTTP_400_BAD_REQUEST
        data = response.json()
        assert "not completed" in data["detail"].lower() or "cannot refund" in data["detail"].lower()

    def test_returns_400_for_already_refunded_payment(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
        sample_customer_in_db: dict[str, Any],
    ) -> None:
        """POST /payments/refund/{payment_id} returns 400 if already refunded."""
        # Create reservation
        create_reservation_with_check_in(days_until_check_in=20)

        # Create already refunded payment
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        table = resource.Table("test-booking-payments")
        table.put_item(
            Item={
                "payment_id": "PAY-ALREADY-REFUNDED",
                "reservation_id": TEST_RESERVATION_ID,
                "amount": 112500,
                "currency": "EUR",
                "status": "refunded",  # Already refunded
                "payment_method": "card",
                "provider": "stripe",
                "stripe_payment_intent_id": "pi_already_refunded",
                "stripe_refund_id": "re_existing",
                "refund_amount": 112500,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "refunded_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        response = client.post(
            "/payments/refund/PAY-ALREADY-REFUNDED",
            headers=get_auth_headers(),
            json={},
        )

        assert response.status_code == HTTP_400_BAD_REQUEST
        data = response.json()
        # Check for "already" and "refunded" (not necessarily adjacent due to "been")
        detail_lower = data["detail"].lower()
        assert "already" in detail_lower and "refunded" in detail_lower

    def test_returns_400_for_payment_without_stripe_intent(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
        sample_customer_in_db: dict[str, Any],
    ) -> None:
        """POST /payments/refund/{payment_id} returns 400 if no Stripe PaymentIntent."""
        # Create reservation
        create_reservation_with_check_in(days_until_check_in=20)

        # Create payment without Stripe IDs (e.g., mock payment)
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        table = resource.Table("test-booking-payments")
        table.put_item(
            Item={
                "payment_id": "PAY-NO-STRIPE",
                "reservation_id": TEST_RESERVATION_ID,
                "amount": 112500,
                "currency": "EUR",
                "status": "completed",
                "payment_method": "card",
                "provider": "mock",  # Not Stripe
                "created_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        response = client.post(
            "/payments/refund/PAY-NO-STRIPE",
            headers=get_auth_headers(),
            json={},
        )

        assert response.status_code == HTTP_400_BAD_REQUEST
        data = response.json()
        assert "stripe" in data["detail"].lower() or "payment intent" in data["detail"].lower()
