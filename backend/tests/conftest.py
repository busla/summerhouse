"""Pytest configuration and fixtures for Quesada Apartment Booking backend tests.

This module provides reusable fixtures for testing:
- DynamoDB mocking with moto
- Sample data fixtures (guests, reservations, pricing)
- Agent configuration fixtures
"""

import os
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

# === Environment Setup ===

# Set environment variables for testing before imports
# Only set fake credentials if no real AWS credentials are configured
# This allows integration tests to use real AWS credentials via AWS_PROFILE
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-1")
os.environ.setdefault("DYNAMODB_TABLE_PREFIX", "test-booking")

# Use Haiku model for tests by default (faster and cheaper than Opus)
# Can be overridden by setting BEDROCK_MODEL_ID explicitly
os.environ.setdefault(
    "BEDROCK_MODEL_ID", "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
)

# Only set fake credentials for moto if no real credentials are present
# AWS_PROFILE indicates the user wants to use real AWS credentials
if not os.environ.get("AWS_PROFILE") and not os.environ.get("AWS_ACCESS_KEY_ID"):
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")


# === DynamoDB Fixtures ===


@pytest.fixture(autouse=True)
def reset_dynamodb_singleton() -> Generator[None, None, None]:
    """Reset DynamoDB singleton before and after each test.

    This ensures tests using mock_aws get a fresh service instance
    inside the mock context rather than reusing a singleton from
    a previous test or non-mocked context.
    """
    from src.services.dynamodb import reset_dynamodb_service

    reset_dynamodb_service()
    yield
    reset_dynamodb_service()


@pytest.fixture(autouse=True)
def reset_auth_service_singleton() -> Generator[None, None, None]:
    """Reset auth service singleton before and after each test.

    This ensures tests using mock_cognito_idp get a fresh service instance
    inside the mock context rather than reusing a singleton from
    a previous test or non-mocked context.
    """
    from src.tools.auth import _reset_auth_service

    _reset_auth_service()
    yield
    _reset_auth_service()


@pytest.fixture
def aws_credentials() -> None:
    """Mocked AWS Credentials for moto.

    Only sets fake credentials if AWS_PROFILE is not set,
    allowing integration tests to use real credentials.
    """
    # Don't override real credentials from AWS_PROFILE
    if not os.environ.get("AWS_PROFILE"):
        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["AWS_SECURITY_TOKEN"] = "testing"
        os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"


@pytest.fixture
def dynamodb_client(aws_credentials: None) -> Generator[Any, None, None]:
    """Create a mocked DynamoDB client."""
    with mock_aws():
        client = boto3.client("dynamodb", region_name="eu-west-1")
        yield client


@pytest.fixture
def dynamodb_resource(aws_credentials: None) -> Generator[Any, None, None]:
    """Create a mocked DynamoDB resource."""
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        yield resource


@pytest.fixture
def create_tables(dynamodb_client: Any) -> None:
    """Create all required DynamoDB tables for testing."""
    tables = [
        {
            "TableName": "test-booking-reservations",
            "KeySchema": [{"AttributeName": "reservation_id", "KeyType": "HASH"}],
            "AttributeDefinitions": [
                {"AttributeName": "reservation_id", "AttributeType": "S"},
                {"AttributeName": "guest_id", "AttributeType": "S"},
                {"AttributeName": "check_in_date", "AttributeType": "S"},
            ],
            "GlobalSecondaryIndexes": [
                {
                    "IndexName": "guest_id-index",
                    "KeySchema": [{"AttributeName": "guest_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "check_in_date-index",
                    "KeySchema": [{"AttributeName": "check_in_date", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
        {
            "TableName": "test-booking-guests",
            "KeySchema": [{"AttributeName": "guest_id", "KeyType": "HASH"}],
            "AttributeDefinitions": [
                {"AttributeName": "guest_id", "AttributeType": "S"},
                {"AttributeName": "email", "AttributeType": "S"},
                {"AttributeName": "cognito_sub", "AttributeType": "S"},
            ],
            "GlobalSecondaryIndexes": [
                {
                    "IndexName": "email-index",
                    "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "cognito_sub-index",
                    "KeySchema": [{"AttributeName": "cognito_sub", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
        {
            "TableName": "test-booking-availability",
            "KeySchema": [
                {"AttributeName": "date", "KeyType": "HASH"},
            ],
            "AttributeDefinitions": [
                {"AttributeName": "date", "AttributeType": "S"},
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
        {
            "TableName": "test-booking-pricing",
            "KeySchema": [
                {"AttributeName": "season", "KeyType": "HASH"},
            ],
            "AttributeDefinitions": [
                {"AttributeName": "season", "AttributeType": "S"},
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
        {
            "TableName": "test-booking-payments",
            "KeySchema": [{"AttributeName": "payment_id", "KeyType": "HASH"}],
            "AttributeDefinitions": [
                {"AttributeName": "payment_id", "AttributeType": "S"},
                {"AttributeName": "reservation_id", "AttributeType": "S"},
            ],
            "GlobalSecondaryIndexes": [
                {
                    "IndexName": "reservation_id-index",
                    "KeySchema": [{"AttributeName": "reservation_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
        {
            "TableName": "test-booking-verification-codes",
            "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
            "AttributeDefinitions": [
                {"AttributeName": "email", "AttributeType": "S"},
            ],
            "BillingMode": "PAY_PER_REQUEST",
            "TimeToLiveSpecification": {
                "AttributeName": "expires_at",
                "Enabled": True,
            },
        },
    ]

    for table_config in tables:
        # TimeToLiveSpecification needs to be set after table creation
        ttl_spec = table_config.pop("TimeToLiveSpecification", None)
        dynamodb_client.create_table(**table_config)

        if ttl_spec:
            dynamodb_client.update_time_to_live(
                TableName=table_config["TableName"],
                TimeToLiveSpecification=ttl_spec,
            )


# === Sample Data Fixtures ===


@pytest.fixture
def sample_guest() -> dict[str, Any]:
    """Sample guest data for testing."""
    return {
        "guest_id": "guest-123-abc",
        "email": "test@example.com",
        "full_name": "John Doe",
        "phone": "+34612345678",
        "preferred_language": "en",
        "email_verified": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "reservation_count": 0,
    }


@pytest.fixture
def sample_reservation() -> dict[str, Any]:
    """Sample reservation data for testing."""
    return {
        "reservation_id": "res-456-def",
        "guest_id": "guest-123-abc",
        "check_in_date": "2025-07-15",
        "check_out_date": "2025-07-22",
        "num_guests": 2,
        "status": "confirmed",
        "total_price": Decimal("890.00"),
        "nightly_rate": Decimal("100.00"),
        "cleaning_fee": Decimal("60.00"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "confirmation_number": "SH-2025-ABC123",
        "special_requests": "Late check-in requested",
    }


@pytest.fixture
def sample_pricing() -> dict[str, Any]:
    """Sample pricing data for testing."""
    return {
        "seasons": {
            "low": {
                "nightly_rate": Decimal("80.00"),
                "min_stay": 3,
                "months": [1, 2, 3, 11, 12],
            },
            "mid": {
                "nightly_rate": Decimal("100.00"),
                "min_stay": 4,
                "months": [4, 5, 6, 9, 10],
            },
            "high": {
                "nightly_rate": Decimal("130.00"),
                "min_stay": 5,
                "months": [7],
            },
            "peak": {
                "nightly_rate": Decimal("150.00"),
                "min_stay": 7,
                "months": [8],
            },
        },
        "cleaning_fee": Decimal("60.00"),
        "currency": "EUR",
    }


@pytest.fixture
def sample_availability() -> list[dict[str, Any]]:
    """Sample availability data for testing (July 2025)."""
    base_date = date(2025, 7, 1)
    availability = []

    for day in range(1, 32):
        current_date = base_date.replace(day=day) if day <= 31 else None
        if current_date is None:
            break

        # Make some dates booked for testing
        status = "booked" if day in [10, 11, 12, 13, 14] else "available"

        availability.append(
            {
                "date": current_date.isoformat(),
                "status": status,
                "min_stay": 5,  # July is high season
            }
        )

    return availability


# === Agent Fixtures ===


@pytest.fixture
def mock_bedrock_client() -> Generator[MagicMock, None, None]:
    """Mock Bedrock client for agent testing."""
    with patch("boto3.client") as mock_client:
        mock_bedrock = MagicMock()
        mock_client.return_value = mock_bedrock

        # Mock invoke_model response
        mock_bedrock.invoke_model.return_value = {
            "body": MagicMock(
                read=MagicMock(
                    return_value=b'{"completion": "Hello! How can I help you today?"}'
                )
            )
        }

        yield mock_bedrock


@pytest.fixture
def mock_ses_client() -> Generator[MagicMock, None, None]:
    """Mock SES client for email testing."""
    with patch("boto3.client") as mock_client:
        mock_ses = MagicMock()
        mock_client.return_value = mock_ses

        # Mock send_email response
        mock_ses.send_email.return_value = {"MessageId": "mock-message-id"}

        yield mock_ses


@pytest.fixture
def mock_cognito_idp() -> Generator[MagicMock, None, None]:
    """Mock Cognito IDP client for passwordless auth testing.

    Provides realistic responses for USER_AUTH flow with EMAIL_OTP challenge.
    """
    import base64
    import json

    mock_client = MagicMock()

    # Mock initiate_auth response (triggers EMAIL_OTP challenge)
    # Default response simulates an EXISTING passwordless user:
    # - AvailableChallenges contains only EMAIL_OTP (no PASSWORD options)
    # - For non-existent users, Cognito returns PASSWORD_SRP/PASSWORD in AvailableChallenges
    #   (masked by prevent_user_existence_errors setting)
    mock_client.initiate_auth.return_value = {
        "ChallengeName": "EMAIL_OTP",
        "Session": "mock-session-token-abc123",
        "ChallengeParameters": {
            "CODE_DELIVERY_DELIVERY_MEDIUM": "EMAIL",
            "CODE_DELIVERY_DESTINATION": "t***@example.com",
        },
        "AvailableChallenges": ["EMAIL_OTP"],  # Only EMAIL_OTP for real passwordless users
    }

    # Create a valid mock JWT ID token (header.payload.signature)
    # The payload contains the cognito sub and email claims
    id_token_payload = {
        "sub": "mock-cognito-sub-12345",
        "email": "test@example.com",
        "email_verified": True,
        "iss": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_TestPool",
        "aud": "test-client-id-123",
    }
    encoded_header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').decode().rstrip("=")
    encoded_payload = base64.urlsafe_b64encode(
        json.dumps(id_token_payload).encode()
    ).decode().rstrip("=")
    mock_id_token = f"{encoded_header}.{encoded_payload}.mock-signature"

    # Mock respond_to_auth_challenge success response
    mock_client.respond_to_auth_challenge.return_value = {
        "AuthenticationResult": {
            "AccessToken": "mock-access-token",
            "IdToken": mock_id_token,
            "RefreshToken": "mock-refresh-token",
            "ExpiresIn": 3600,
            "TokenType": "Bearer",
        },
    }

    yield mock_client


@pytest.fixture
def cognito_user_pool_config() -> dict[str, str]:
    """Configuration for Cognito user pool in tests."""
    return {
        "user_pool_id": "eu-west-1_TestPool",
        "client_id": "test-client-id-123",
    }


# === Helper Fixtures ===


@pytest.fixture
def freeze_time() -> Generator[datetime, None, None]:
    """Fixture to provide a fixed datetime for testing."""
    fixed_time = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    yield fixed_time
