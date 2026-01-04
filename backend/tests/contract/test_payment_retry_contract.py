"""Contract tests for POST /payments/{reservation_id}/retry endpoint.

Tests verify the endpoint matches the contract specification (FR-025, FR-029):
- Creates new Stripe Checkout session for retry
- Enforces maximum 3 payment attempts per reservation
- Returns attempt_number in response
- Only allows retry for pending reservations

TDD: These tests are written FIRST and expected to FAIL until
the endpoint is updated to match the contract (T038-T043).

Test categories:
- T038-A: Not found handling (404)
- T038-B: Success response (200) with checkout session
- T038-C: Authorization checks
- T038-D: Retry limit enforcement (max 3)
- T038-E: Error handling
"""

import os
from datetime import datetime, timezone
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

TEST_CUSTOMER_ID = "CUST-2026-RETRYTEST"
TEST_RESERVATION_ID = "RES-2026-RETRYTEST"
TEST_COGNITO_SUB = "test-cognito-sub-retry"


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
        os.environ["FRONTEND_URL"] = "https://test.example.com"

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
        "email": "retry-test@example.com",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=customer)
    return customer


@pytest.fixture
def sample_pending_reservation(
    mock_dynamodb_tables: None,
    sample_customer_in_db: dict[str, Any],
) -> dict[str, Any]:
    """Create sample pending reservation with failed payment."""
    resource = boto3.resource("dynamodb", region_name="eu-west-1")

    # Create pending reservation
    res_table = resource.Table("test-booking-reservations")
    reservation = {
        "reservation_id": TEST_RESERVATION_ID,
        "customer_id": TEST_CUSTOMER_ID,
        "check_in": "2026-07-20",
        "check_out": "2026-07-27",
        "num_adults": 2,
        "num_children": 0,
        "nights": 7,
        "status": "pending",
        "payment_status": "pending",
        "total_amount": 112500,
        "nightly_rate": 15000,
        "cleaning_fee": 7500,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    res_table.put_item(Item=reservation)

    # Create one failed payment (attempt 1)
    pay_table = resource.Table("test-booking-payments")
    payment = {
        "payment_id": "PAY-RETRY-FAILED-1",
        "reservation_id": TEST_RESERVATION_ID,
        "amount": 112500,
        "currency": "EUR",
        "status": "failed",
        "payment_method": "card",
        "provider": "stripe",
        "error_message": "Card declined",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    pay_table.put_item(Item=payment)

    return reservation


def get_auth_headers(cognito_sub: str = TEST_COGNITO_SUB) -> dict[str, str]:
    """Get headers that simulate JWT authentication."""
    return {"x-user-sub": cognito_sub}


# === T038-A: Not Found Tests ===


class TestRetryNotFound:
    """Tests for 404 responses when reservation not found."""

    def test_returns_404_when_reservation_not_found(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
        sample_customer_in_db: dict[str, Any],
    ) -> None:
        """POST /payments/{reservation_id}/retry returns 404 for nonexistent reservation."""
        response = client.post(
            "/payments/RES-NONEXISTENT-123/retry",
            headers=get_auth_headers(),
            json={},
        )

        assert response.status_code == HTTP_404_NOT_FOUND


# === T038-B: Success Tests ===


class TestRetrySuccess:
    """Tests for successful retry creating new Stripe Checkout session."""

    def test_returns_200_with_checkout_session_response(
        self,
        client: TestClient,
        sample_pending_reservation: dict[str, Any],
    ) -> None:
        """POST /payments/{reservation_id}/retry returns 200 with checkout URL."""
        with patch("api.routes.payments.get_stripe_service") as mock_get_stripe:
            mock_stripe = MagicMock()
            mock_stripe.create_checkout_session.return_value = {
                "session_id": "cs_retry_test_123",
                "checkout_url": "https://checkout.stripe.com/c/pay/cs_retry_test_123",
                "expires_at": datetime(2026, 1, 3, 11, 0, 0, tzinfo=timezone.utc),
                "payment_intent_id": "pi_retry_test_123",
            }
            mock_get_stripe.return_value = mock_stripe

            response = client.post(
                f"/payments/{TEST_RESERVATION_ID}/retry",
                headers=get_auth_headers(),
                json={},
            )

        assert response.status_code == HTTP_200_OK
        data = response.json()
        # Contract specifies CheckoutSessionResponse
        assert "payment_id" in data
        assert "checkout_session_id" in data
        assert "checkout_url" in data
        assert "amount" in data
        assert data["checkout_session_id"] == "cs_retry_test_123"

    def test_response_includes_attempt_number(
        self,
        client: TestClient,
        sample_pending_reservation: dict[str, Any],
    ) -> None:
        """POST /payments/{reservation_id}/retry includes attempt_number in response."""
        with patch("api.routes.payments.get_stripe_service") as mock_get_stripe:
            mock_stripe = MagicMock()
            mock_stripe.create_checkout_session.return_value = {
                "session_id": "cs_retry_attempt",
                "checkout_url": "https://checkout.stripe.com/c/pay/cs_retry_attempt",
                "expires_at": datetime(2026, 1, 3, 11, 0, 0, tzinfo=timezone.utc),
                "payment_intent_id": "pi_retry_attempt",
            }
            mock_get_stripe.return_value = mock_stripe

            response = client.post(
                f"/payments/{TEST_RESERVATION_ID}/retry",
                headers=get_auth_headers(),
                json={},
            )

        assert response.status_code == HTTP_200_OK
        data = response.json()
        # After first failed payment, retry should be attempt 2
        assert "attempt_number" in data
        assert data["attempt_number"] == 2

    def test_uses_custom_redirect_urls_when_provided(
        self,
        client: TestClient,
        sample_pending_reservation: dict[str, Any],
    ) -> None:
        """POST /payments/{reservation_id}/retry uses provided redirect URLs."""
        with patch("api.routes.payments.get_stripe_service") as mock_get_stripe:
            mock_stripe = MagicMock()
            mock_stripe.create_checkout_session.return_value = {
                "session_id": "cs_custom_urls",
                "checkout_url": "https://checkout.stripe.com/c/pay/cs_custom_urls",
                "expires_at": datetime(2026, 1, 3, 11, 0, 0, tzinfo=timezone.utc),
            }
            mock_get_stripe.return_value = mock_stripe

            response = client.post(
                f"/payments/{TEST_RESERVATION_ID}/retry",
                headers=get_auth_headers(),
                json={
                    "success_url": "https://custom.example/success",
                    "cancel_url": "https://custom.example/cancel",
                },
            )

        assert response.status_code == HTTP_200_OK
        # Verify custom URLs were passed to Stripe
        call_kwargs = mock_stripe.create_checkout_session.call_args.kwargs
        assert call_kwargs["success_url"] == "https://custom.example/success"
        assert call_kwargs["cancel_url"] == "https://custom.example/cancel"


# === T038-C: Authorization Tests ===


class TestRetryAuthorization:
    """Tests for retry authorization."""

    def test_returns_401_or_403_without_auth(
        self,
        client: TestClient,
        sample_pending_reservation: dict[str, Any],
    ) -> None:
        """POST /payments/{reservation_id}/retry requires authentication."""
        response = client.post(
            f"/payments/{TEST_RESERVATION_ID}/retry",
            json={},
            # No auth headers
        )

        # Either 401 or 403 is acceptable for missing auth
        assert response.status_code in (HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN)

    def test_returns_403_for_non_owner(
        self,
        client: TestClient,
        sample_pending_reservation: dict[str, Any],
    ) -> None:
        """POST /payments/{reservation_id}/retry returns 403 for non-owner."""
        # Create different customer
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        table = resource.Table("test-booking-customers")
        table.put_item(
            Item={
                "customer_id": "CUST-OTHER-RETRY",
                "cognito_sub": "other-user-retry-sub",
                "email": "other-retry@example.com",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        response = client.post(
            f"/payments/{TEST_RESERVATION_ID}/retry",
            headers=get_auth_headers("other-user-retry-sub"),
            json={},
        )

        assert response.status_code == HTTP_403_FORBIDDEN


# === T038-D: Retry Limit Tests ===


class TestRetryLimitEnforcement:
    """Tests for max 3 attempts enforcement (FR-025)."""

    def test_returns_400_when_max_attempts_exceeded(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
        sample_customer_in_db: dict[str, Any],
    ) -> None:
        """POST /payments/{reservation_id}/retry returns 400 after 3 attempts."""
        resource = boto3.resource("dynamodb", region_name="eu-west-1")

        # Create pending reservation
        res_table = resource.Table("test-booking-reservations")
        res_table.put_item(
            Item={
                "reservation_id": "RES-MAX-ATTEMPTS",
                "customer_id": TEST_CUSTOMER_ID,
                "check_in": "2026-07-20",
                "check_out": "2026-07-27",
                "num_adults": 2,
                "num_children": 0,
                "nights": 7,
                "status": "pending",
                "payment_status": "pending",
                "total_amount": 112500,
                "nightly_rate": 15000,
                "cleaning_fee": 7500,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Create 3 failed payments (already at max attempts)
        pay_table = resource.Table("test-booking-payments")
        for i in range(1, 4):
            pay_table.put_item(
                Item={
                    "payment_id": f"PAY-MAX-FAIL-{i}",
                    "reservation_id": "RES-MAX-ATTEMPTS",
                    "amount": 112500,
                    "currency": "EUR",
                    "status": "failed",
                    "payment_method": "card",
                    "provider": "stripe",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        response = client.post(
            "/payments/RES-MAX-ATTEMPTS/retry",
            headers=get_auth_headers(),
            json={},
        )

        assert response.status_code == HTTP_400_BAD_REQUEST
        data = response.json()
        # Should indicate max attempts exceeded
        detail_lower = data["detail"].lower() if "detail" in data else ""
        message_lower = data.get("message", "").lower()
        error_text = detail_lower or message_lower
        assert "maximum" in error_text or "3" in error_text or "attempts" in error_text

    def test_allows_retry_when_under_limit(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
        sample_customer_in_db: dict[str, Any],
    ) -> None:
        """POST /payments/{reservation_id}/retry allows retry when under 3 attempts."""
        resource = boto3.resource("dynamodb", region_name="eu-west-1")

        # Create pending reservation
        res_table = resource.Table("test-booking-reservations")
        res_table.put_item(
            Item={
                "reservation_id": "RES-UNDER-LIMIT",
                "customer_id": TEST_CUSTOMER_ID,
                "check_in": "2026-07-20",
                "check_out": "2026-07-27",
                "num_adults": 2,
                "num_children": 0,
                "nights": 7,
                "status": "pending",
                "payment_status": "pending",
                "total_amount": 112500,
                "nightly_rate": 15000,
                "cleaning_fee": 7500,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Create 2 failed payments (under limit)
        pay_table = resource.Table("test-booking-payments")
        for i in range(1, 3):
            pay_table.put_item(
                Item={
                    "payment_id": f"PAY-UNDER-FAIL-{i}",
                    "reservation_id": "RES-UNDER-LIMIT",
                    "amount": 112500,
                    "currency": "EUR",
                    "status": "failed",
                    "payment_method": "card",
                    "provider": "stripe",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        with patch("api.routes.payments.get_stripe_service") as mock_get_stripe:
            mock_stripe = MagicMock()
            mock_stripe.create_checkout_session.return_value = {
                "session_id": "cs_under_limit",
                "checkout_url": "https://checkout.stripe.com/c/pay/cs_under_limit",
                "expires_at": datetime(2026, 1, 3, 11, 0, 0, tzinfo=timezone.utc),
            }
            mock_get_stripe.return_value = mock_stripe

            response = client.post(
                "/payments/RES-UNDER-LIMIT/retry",
                headers=get_auth_headers(),
                json={},
            )

        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["attempt_number"] == 3  # Third attempt


# === T038-E: Error Handling Tests ===


class TestRetryErrorHandling:
    """Tests for retry error handling."""

    def test_returns_400_when_reservation_already_paid(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
        sample_customer_in_db: dict[str, Any],
    ) -> None:
        """POST /payments/{reservation_id}/retry returns 400 if already paid."""
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        res_table = resource.Table("test-booking-reservations")
        res_table.put_item(
            Item={
                "reservation_id": "RES-ALREADY-PAID",
                "customer_id": TEST_CUSTOMER_ID,
                "check_in": "2026-07-20",
                "check_out": "2026-07-27",
                "num_adults": 2,
                "num_children": 0,
                "nights": 7,
                "status": "confirmed",  # Already paid
                "payment_status": "paid",
                "total_amount": 112500,
                "nightly_rate": 15000,
                "cleaning_fee": 7500,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        response = client.post(
            "/payments/RES-ALREADY-PAID/retry",
            headers=get_auth_headers(),
            json={},
        )

        assert response.status_code == HTTP_400_BAD_REQUEST

    def test_returns_400_when_reservation_cancelled(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
        sample_customer_in_db: dict[str, Any],
    ) -> None:
        """POST /payments/{reservation_id}/retry returns 400 if cancelled."""
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        res_table = resource.Table("test-booking-reservations")
        res_table.put_item(
            Item={
                "reservation_id": "RES-CANCELLED",
                "customer_id": TEST_CUSTOMER_ID,
                "check_in": "2026-07-20",
                "check_out": "2026-07-27",
                "num_adults": 2,
                "num_children": 0,
                "nights": 7,
                "status": "cancelled",  # Cancelled
                "payment_status": "pending",
                "total_amount": 112500,
                "nightly_rate": 15000,
                "cleaning_fee": 7500,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        response = client.post(
            "/payments/RES-CANCELLED/retry",
            headers=get_auth_headers(),
            json={},
        )

        assert response.status_code == HTTP_400_BAD_REQUEST

    def test_returns_400_when_no_previous_payment_exists(
        self,
        client: TestClient,
        mock_dynamodb_tables: None,
        sample_customer_in_db: dict[str, Any],
    ) -> None:
        """POST /payments/{reservation_id}/retry returns 400 if no previous payment."""
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        res_table = resource.Table("test-booking-reservations")
        res_table.put_item(
            Item={
                "reservation_id": "RES-NO-PAYMENT",
                "customer_id": TEST_CUSTOMER_ID,
                "check_in": "2026-07-20",
                "check_out": "2026-07-27",
                "num_adults": 2,
                "num_children": 0,
                "nights": 7,
                "status": "pending",
                "payment_status": "pending",
                "total_amount": 112500,
                "nightly_rate": 15000,
                "cleaning_fee": 7500,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        response = client.post(
            "/payments/RES-NO-PAYMENT/retry",
            headers=get_auth_headers(),
            json={},
        )

        assert response.status_code == HTTP_400_BAD_REQUEST
        data = response.json()
        # Should suggest using checkout-session endpoint instead
        detail = data.get("detail", "").lower()
        assert "no previous payment" in detail or "checkout-session" in detail
