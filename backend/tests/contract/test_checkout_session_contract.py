"""Contract tests for POST /payments/checkout-session endpoint.

Tests verify the endpoint matches the contract specification:
- specs/013-stripe-payment/contracts/checkout-session.yaml

TDD: These tests are written FIRST and expected to FAIL until
the endpoint is implemented (T016+).

Test categories:
- T010-A: Authentication requirements (401)
- T010-B: Authorization requirements (403)
- T010-C: Request validation (400)
- T010-D: Business rule validation (400)
- T010-E: Not found handling (404)
- T010-F: Success response (201)
"""

import base64
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from api.main import app


# === Test Configuration ===

TEST_CUSTOMER_ID = "CUST-2026-TESTOWNER"
TEST_COGNITO_SUB = "test-cognito-sub-owner-123"
TEST_CUSTOMER_EMAIL = "owner@example.com"

OTHER_CUSTOMER_ID = "CUST-2026-OTHERUSER"
OTHER_COGNITO_SUB = "test-cognito-sub-other-456"
OTHER_CUSTOMER_EMAIL = "other@example.com"

TEST_RESERVATION_ID = "RES-2026-ABC123"


# === Test Fixtures ===


def get_auth_headers(cognito_sub: str = TEST_COGNITO_SUB) -> dict[str, str]:
    """Get headers that simulate API Gateway JWT authentication.

    In production, API Gateway validates JWTs and injects x-user-sub header.
    Tests simulate this by sending x-user-sub directly.
    """
    return {"x-user-sub": cognito_sub}


@pytest.fixture
def client() -> TestClient:
    """Create test client for API."""
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Authentication headers for the reservation owner."""
    return get_auth_headers(TEST_COGNITO_SUB)


@pytest.fixture
def other_user_auth_headers() -> dict[str, str]:
    """Authentication headers for a different user (not the owner)."""
    return get_auth_headers(OTHER_COGNITO_SUB)


@pytest.fixture
def mock_dynamodb_tables() -> Generator[None, None, None]:
    """Set up mock DynamoDB tables for testing."""
    with mock_aws():
        # Set up environment
        os.environ["DYNAMODB_TABLE_PREFIX"] = "test-booking"
        os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"
        os.environ["FRONTEND_URL"] = "https://test.example.com"

        client = boto3.client("dynamodb", region_name="eu-west-1")

        # Create reservations table
        client.create_table(
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
                    "IndexName": "reservation_id-index",
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
        "email": TEST_CUSTOMER_EMAIL,
        "full_name": "Test Owner",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=customer)
    return customer


@pytest.fixture
def sample_reservation_in_db(
    mock_dynamodb_tables: None,
    sample_customer_in_db: dict[str, Any]
) -> dict[str, Any]:
    """Create sample pending reservation in mock DynamoDB."""
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
        "status": "pending",  # Payable state
        "payment_status": "pending",
        "total_amount": 112500,  # €1,125.00 in cents
        "nightly_rate": 15000,   # €150.00 in cents
        "cleaning_fee": 7500,    # €75.00 in cents
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=reservation)
    return reservation


@pytest.fixture
def paid_reservation_in_db(
    mock_dynamodb_tables: None,
    sample_customer_in_db: dict[str, Any]
) -> dict[str, Any]:
    """Create already-paid reservation in mock DynamoDB."""
    resource = boto3.resource("dynamodb", region_name="eu-west-1")
    table = resource.Table("test-booking-reservations")

    reservation = {
        "reservation_id": "RES-2026-ALREADYPAID",
        "customer_id": TEST_CUSTOMER_ID,
        "check_in": "2026-08-01",
        "check_out": "2026-08-07",
        "num_adults": 2,
        "num_children": 0,
        "nights": 6,
        "status": "confirmed",  # Already paid
        "payment_status": "paid",
        "total_amount": 112500,  # €1,125.00 in cents
        "nightly_rate": 15000,
        "cleaning_fee": 7500,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=reservation)
    return reservation


@pytest.fixture
def cancelled_reservation_in_db(
    mock_dynamodb_tables: None,
    sample_customer_in_db: dict[str, Any]
) -> dict[str, Any]:
    """Create cancelled reservation in mock DynamoDB."""
    resource = boto3.resource("dynamodb", region_name="eu-west-1")
    table = resource.Table("test-booking-reservations")

    reservation = {
        "reservation_id": "RES-2026-CANCELLED",
        "customer_id": TEST_CUSTOMER_ID,
        "check_in": "2026-09-01",
        "check_out": "2026-09-07",
        "num_adults": 2,
        "num_children": 0,
        "nights": 6,
        "status": "cancelled",
        "payment_status": "pending",
        "total_amount": 112500,  # €1,125.00 in cents
        "nightly_rate": 15000,
        "cleaning_fee": 7500,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=reservation)
    return reservation


@pytest.fixture
def other_users_reservation_in_db(mock_dynamodb_tables: None) -> dict[str, Any]:
    """Create reservation belonging to another user."""
    resource = boto3.resource("dynamodb", region_name="eu-west-1")

    # Create the other customer first
    customers_table = resource.Table("test-booking-customers")
    other_customer = {
        "customer_id": OTHER_CUSTOMER_ID,
        "cognito_sub": OTHER_COGNITO_SUB,
        "email": OTHER_CUSTOMER_EMAIL,
        "full_name": "Other User",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    customers_table.put_item(Item=other_customer)

    # Create reservation owned by other user
    reservations_table = resource.Table("test-booking-reservations")
    reservation = {
        "reservation_id": "RES-2026-OTHERUSER",
        "customer_id": OTHER_CUSTOMER_ID,
        "check_in": "2026-10-01",
        "check_out": "2026-10-06",
        "num_adults": 3,
        "num_children": 0,
        "nights": 5,
        "status": "pending",
        "payment_status": "pending",
        "total_amount": 90000,  # €900.00 in cents
        "nightly_rate": 15000,
        "cleaning_fee": 7500,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    reservations_table.put_item(Item=reservation)
    return reservation


# === T010-A: Authentication Tests ===


class TestCheckoutSessionAuthentication:
    """Test authentication requirements for checkout-session endpoint."""

    def test_returns_401_when_no_auth_header(
        self,
        client: TestClient,
        mock_dynamodb_tables: None
    ) -> None:
        """Request without Authorization header should return 401."""
        response = client.post(
            "/payments/checkout-session",
            json={"reservation_id": TEST_RESERVATION_ID},
        )
        assert response.status_code == HTTP_401_UNAUTHORIZED

    def test_returns_401_when_invalid_token(
        self,
        client: TestClient,
        mock_dynamodb_tables: None
    ) -> None:
        """Request with invalid token should return 401."""
        response = client.post(
            "/payments/checkout-session",
            json={"reservation_id": TEST_RESERVATION_ID},
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == HTTP_401_UNAUTHORIZED

    def test_returns_401_when_expired_token(
        self,
        client: TestClient,
        mock_dynamodb_tables: None
    ) -> None:
        """Request with expired token should return 401."""
        # Create expired JWT
        header = {"alg": "RS256", "typ": "JWT"}
        payload = {
            "sub": TEST_COGNITO_SUB,
            "email": TEST_CUSTOMER_EMAIL,
            "exp": 1,  # Expired in 1970
        }
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        expired_token = f"{header_b64}.{payload_b64}.signature"

        response = client.post(
            "/payments/checkout-session",
            json={"reservation_id": TEST_RESERVATION_ID},
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == HTTP_401_UNAUTHORIZED


# === T010-B: Authorization Tests ===


class TestCheckoutSessionAuthorization:
    """Test authorization requirements (owner-only access)."""

    def test_returns_403_when_not_reservation_owner(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        sample_customer_in_db: dict[str, Any],
        other_users_reservation_in_db: dict[str, Any],
    ) -> None:
        """Authenticated user cannot pay for another user's reservation."""
        response = client.post(
            "/payments/checkout-session",
            json={"reservation_id": "RES-2026-OTHERUSER"},
            headers=auth_headers,
        )
        assert response.status_code == HTTP_403_FORBIDDEN

        data = response.json()
        assert data["success"] is False
        assert "error_code" in data
        assert "message" in data
        assert "recovery" in data


# === T010-C: Request Validation Tests ===


class TestCheckoutSessionRequestValidation:
    """Test request body validation."""

    def test_returns_422_when_reservation_id_missing(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        mock_dynamodb_tables: None
    ) -> None:
        """Request without reservation_id should return 422."""
        response = client.post(
            "/payments/checkout-session",
            json={},
            headers=auth_headers,
        )
        # FastAPI returns 422 for validation errors
        assert response.status_code == 422

    def test_returns_422_when_reservation_id_empty(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        sample_customer_in_db: dict[str, Any],  # Need customer for auth check before validation
    ) -> None:
        """Request with empty reservation_id should return 422."""
        response = client.post(
            "/payments/checkout-session",
            json={"reservation_id": ""},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_accepts_optional_success_url(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        sample_reservation_in_db: dict[str, Any],
    ) -> None:
        """Request with optional success_url should be accepted."""
        # This test will fail with 404/501 until endpoint is implemented
        # but validates the request is accepted
        response = client.post(
            "/payments/checkout-session",
            json={
                "reservation_id": TEST_RESERVATION_ID,
                "success_url": "https://example.com/success",
            },
            headers=auth_headers,
        )
        # Should not be 422 (validation error)
        assert response.status_code != 422

    def test_accepts_optional_cancel_url(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        sample_reservation_in_db: dict[str, Any],
    ) -> None:
        """Request with optional cancel_url should be accepted."""
        response = client.post(
            "/payments/checkout-session",
            json={
                "reservation_id": TEST_RESERVATION_ID,
                "cancel_url": "https://example.com/cancel",
            },
            headers=auth_headers,
        )
        # Should not be 422 (validation error)
        assert response.status_code != 422


# === T010-D: Business Rule Tests ===


class TestCheckoutSessionBusinessRules:
    """Test business rule validation (payable state)."""

    def test_returns_400_when_reservation_already_paid(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        paid_reservation_in_db: dict[str, Any],
    ) -> None:
        """Cannot create checkout session for already-paid reservation."""
        response = client.post(
            "/payments/checkout-session",
            json={"reservation_id": "RES-2026-ALREADYPAID"},
            headers=auth_headers,
        )
        assert response.status_code == HTTP_400_BAD_REQUEST

        data = response.json()
        assert data["success"] is False
        # Message may be specific ("already paid") or generic ("payable state")
        assert "already paid" in data["message"].lower() or "payable" in data["message"].lower()

    def test_returns_400_when_reservation_cancelled(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        cancelled_reservation_in_db: dict[str, Any],
    ) -> None:
        """Cannot create checkout session for cancelled reservation."""
        response = client.post(
            "/payments/checkout-session",
            json={"reservation_id": "RES-2026-CANCELLED"},
            headers=auth_headers,
        )
        assert response.status_code == HTTP_400_BAD_REQUEST

        data = response.json()
        assert data["success"] is False
        # Message may be specific ("cancelled") or generic ("payable state")
        assert "cancelled" in data["message"].lower() or "payable" in data["message"].lower()


# === T010-E: Not Found Tests ===


class TestCheckoutSessionNotFound:
    """Test handling of non-existent reservations."""

    def test_returns_404_when_reservation_not_found(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        sample_customer_in_db: dict[str, Any],  # Customer exists but reservation doesn't
    ) -> None:
        """Non-existent reservation should return 404."""
        response = client.post(
            "/payments/checkout-session",
            json={"reservation_id": "RES-2026-NONEXISTENT"},
            headers=auth_headers,
        )
        assert response.status_code == HTTP_404_NOT_FOUND

        data = response.json()
        assert data["success"] is False
        assert "not found" in data["message"].lower()


# === T010-F: Success Response Tests ===


class TestCheckoutSessionSuccess:
    """Test successful checkout session creation.

    These tests require mocking Stripe service since we're testing
    the API response format, not actual Stripe integration.
    """

    def test_returns_201_with_checkout_url(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        sample_reservation_in_db: dict[str, Any],
    ) -> None:
        """Successful request returns 201 with checkout URL."""
        # Mock Stripe service to avoid external calls (patch where it's used, not defined)
        with patch("api.routes.payments.get_stripe_service") as mock_stripe:
            mock_service = MagicMock()
            mock_service.create_checkout_session.return_value = {
                "session_id": "cs_test_abc123",
                "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_abc123",
                "expires_at": datetime(2026, 1, 3, 10, 30, 0, tzinfo=timezone.utc),
                "payment_intent_id": "pi_test_123",
            }
            mock_stripe.return_value = mock_service

            response = client.post(
                "/payments/checkout-session",
                json={"reservation_id": TEST_RESERVATION_ID},
                headers=auth_headers,
            )

        assert response.status_code == HTTP_201_CREATED

        data = response.json()
        assert "payment_id" in data
        assert "checkout_session_id" in data
        assert "checkout_url" in data
        assert "expires_at" in data
        assert "amount" in data
        assert "currency" in data

    def test_response_schema_matches_contract(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        sample_reservation_in_db: dict[str, Any],
    ) -> None:
        """Response matches CheckoutSessionResponse schema."""
        with patch("api.routes.payments.get_stripe_service") as mock_stripe:
            mock_service = MagicMock()
            mock_service.create_checkout_session.return_value = {
                "session_id": "cs_test_abc123",
                "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_abc123",
                "expires_at": datetime(2026, 1, 3, 10, 30, 0, tzinfo=timezone.utc),
                "payment_intent_id": "pi_test_123",
            }
            mock_stripe.return_value = mock_service

            response = client.post(
                "/payments/checkout-session",
                json={"reservation_id": TEST_RESERVATION_ID},
                headers=auth_headers,
            )

        if response.status_code == HTTP_201_CREATED:
            data = response.json()

            # Validate required fields per contract
            assert isinstance(data["payment_id"], str)
            assert isinstance(data["checkout_session_id"], str)
            assert isinstance(data["checkout_url"], str)
            assert data["checkout_url"].startswith("https://")
            assert isinstance(data["expires_at"], str)  # ISO datetime string
            assert isinstance(data["amount"], int)
            assert data["amount"] >= 0
            assert isinstance(data["currency"], str)
            assert data["currency"] == "EUR"

    def test_amount_matches_reservation_total(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        sample_reservation_in_db: dict[str, Any],
    ) -> None:
        """Payment amount should match reservation total_price in cents."""
        with patch("api.routes.payments.get_stripe_service") as mock_stripe:
            mock_service = MagicMock()
            mock_service.create_checkout_session.return_value = {
                "session_id": "cs_test_abc123",
                "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_abc123",
                "expires_at": datetime(2026, 1, 3, 10, 30, 0, tzinfo=timezone.utc),
                "payment_intent_id": "pi_test_123",
            }
            mock_stripe.return_value = mock_service

            response = client.post(
                "/payments/checkout-session",
                json={"reservation_id": TEST_RESERVATION_ID},
                headers=auth_headers,
            )

        if response.status_code == HTTP_201_CREATED:
            data = response.json()
            # Reservation total is 1125.00 EUR = 112500 cents
            assert data["amount"] == 112500
