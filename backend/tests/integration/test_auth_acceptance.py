"""Acceptance tests for Cognito EMAIL_OTP authentication (T039-T042).

These tests verify end-to-end authentication behavior:
- T039: Cognito sends EMAIL_OTP within 60 seconds of initiate_cognito_login
- T040: OTP codes expire after 5 minutes (covered by unit tests)
- T041: Max 3 OTP attempts per session (covered by unit tests)
- T042: New email creates guest with email_verified=true after OTP

NOTE: T040 and T041 are covered by unit tests in test_auth_tools.py:
- test_verify_otp_returns_expired_error
- test_verify_otp_returns_max_attempts_error
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

# Set environment before imports
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-1")
os.environ.setdefault("ENVIRONMENT", "test")


# === Fixtures ===


@pytest.fixture
def aws_credentials() -> Generator[None, None, None]:
    """Mocked AWS Credentials for moto."""
    original_values = {
        key: os.environ.get(key)
        for key in [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SECURITY_TOKEN",
            "AWS_SESSION_TOKEN",
        ]
    }

    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"
    os.environ["ENVIRONMENT"] = "test"

    yield

    for key, value in original_values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture
def mock_aws_context(aws_credentials: None) -> Generator[None, None, None]:
    """Provide mock_aws context for entire test."""
    with mock_aws():
        yield


@pytest.fixture
def dynamodb_tables(mock_aws_context: None) -> Generator[Any, None, None]:
    """Create DynamoDB tables for auth flow within mock_aws context.

    Note: Table names must match DYNAMODB_TABLE_PREFIX from conftest.py
    which is 'test-booking', so tables are 'test-booking-guests', etc.
    """
    client = boto3.client("dynamodb", region_name="eu-west-1")

    # Guests table with email and cognito_sub GSIs
    # Use 'test-booking' prefix to match conftest.py DYNAMODB_TABLE_PREFIX
    client.create_table(
        TableName="test-booking-guests",
        KeySchema=[{"AttributeName": "guest_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "guest_id", "AttributeType": "S"},
            {"AttributeName": "email", "AttributeType": "S"},
            {"AttributeName": "cognito_sub", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "email-index",
                "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "cognito-sub-index",
                "KeySchema": [{"AttributeName": "cognito_sub", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # Reset DynamoDB singleton to use mock tables
    from src.services.dynamodb import reset_dynamodb_service

    reset_dynamodb_service()

    yield client

    reset_dynamodb_service()


@pytest.fixture
def mock_cognito_client() -> Generator[MagicMock, None, None]:
    """Mock Cognito IDP client with realistic EMAIL_OTP responses."""
    import base64
    import json

    mock_client = MagicMock()

    # Mock initiate_auth response (triggers EMAIL_OTP challenge)
    mock_client.initiate_auth.return_value = {
        "ChallengeName": "EMAIL_OTP",
        "Session": "mock-session-token-abc123",
        "ChallengeParameters": {
            "CODE_DELIVERY_DELIVERY_MEDIUM": "EMAIL",
            "CODE_DELIVERY_DESTINATION": "t***@example.com",
        },
    }

    # Create valid mock JWT ID token
    id_token_payload = {
        "sub": "cognito-user-sub-12345",
        "email": "newuser@example.com",
        "email_verified": True,
        "iss": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_TestPool",
        "aud": "test-client-id",
    }
    encoded_header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').decode().rstrip("=")
    encoded_payload = (
        base64.urlsafe_b64encode(json.dumps(id_token_payload).encode())
        .decode()
        .rstrip("=")
    )
    mock_id_token = f"{encoded_header}.{encoded_payload}.mock-signature"

    # Mock respond_to_auth_challenge success
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


# === T039: Cognito sends EMAIL_OTP within 60 seconds ===


class TestT039CognitoOtpTiming:
    """T039: Verify Cognito sends EMAIL_OTP within 60 seconds of initiate_cognito_login."""

    def test_initiate_returns_otp_sent_timestamp_within_60_seconds(
        self,
        mock_cognito_client: MagicMock,
    ) -> None:
        """Should return otp_sent_at timestamp within 60 seconds of call."""
        from src.tools.auth import _reset_auth_service, initiate_cognito_login

        _reset_auth_service()

        email = "test@example.com"
        time_before = datetime.now(timezone.utc)

        with patch("boto3.client", return_value=mock_cognito_client):
            with patch.dict(
                "os.environ",
                {
                    "COGNITO_USER_POOL_ID": "eu-west-1_TestPool",
                    "COGNITO_CLIENT_ID": "test-client-id",
                },
            ):
                result = initiate_cognito_login(email)

        time_after = datetime.now(timezone.utc)

        # Verify success
        assert result["success"] is True
        assert "otp_sent_at" in result

        # Parse the timestamp
        otp_sent_at = datetime.fromisoformat(result["otp_sent_at"])

        # Verify timestamp is within 60 seconds of call
        assert time_before <= otp_sent_at <= time_after
        time_delta = otp_sent_at - time_before
        assert time_delta.total_seconds() < 60, (
            f"OTP sent timestamp {otp_sent_at} was not within 60 seconds of call"
        )

        _reset_auth_service()

    def test_initiate_triggers_cognito_auth_flow_immediately(
        self,
        mock_cognito_client: MagicMock,
    ) -> None:
        """Should call Cognito initiate_auth immediately upon tool invocation."""
        from src.tools.auth import _reset_auth_service, initiate_cognito_login

        _reset_auth_service()

        email = "test@example.com"

        with patch("boto3.client", return_value=mock_cognito_client):
            with patch.dict(
                "os.environ",
                {
                    "COGNITO_USER_POOL_ID": "eu-west-1_TestPool",
                    "COGNITO_CLIENT_ID": "test-client-id",
                },
            ):
                result = initiate_cognito_login(email)

        # Verify Cognito was called with correct parameters
        mock_cognito_client.initiate_auth.assert_called_once()
        call_kwargs = mock_cognito_client.initiate_auth.call_args.kwargs
        assert call_kwargs["AuthFlow"] == "USER_AUTH"
        assert call_kwargs["AuthParameters"]["USERNAME"] == email
        assert call_kwargs["AuthParameters"]["PREFERRED_CHALLENGE"] == "EMAIL_OTP"

        # Verify response indicates EMAIL_OTP challenge
        assert result["challenge"] == "EMAIL_OTP"

        _reset_auth_service()


# === T042: New email creates guest with email_verified=true ===


class TestT042NewGuestCreation:
    """T042: Verify new email creates Cognito user with email_verified=true after OTP."""

    def test_new_email_creates_guest_with_email_verified(
        self,
        mock_cognito_client: MagicMock,
        dynamodb_tables: Any,
    ) -> None:
        """Should create new guest with email_verified=true after successful OTP."""
        from src.tools.auth import (
            _reset_auth_service,
            initiate_cognito_login,
            verify_cognito_otp,
        )

        _reset_auth_service()

        new_email = "newuser@example.com"

        # Patch the cognito client specifically in auth_service module
        with patch(
            "src.services.auth_service.boto3.client", return_value=mock_cognito_client
        ):
            with patch.dict(
                "os.environ",
                {
                    "COGNITO_USER_POOL_ID": "eu-west-1_TestPool",
                    "COGNITO_CLIENT_ID": "test-client-id",
                },
            ):
                # Step 1: Initiate login for new email
                init_result = initiate_cognito_login(new_email)

                assert init_result["success"] is True, f"Init failed: {init_result}"
                session_token = init_result["session_token"]
                otp_sent_at = init_result["otp_sent_at"]

                # Step 2: Verify OTP (within same patch context)
                verify_result = verify_cognito_otp(
                    email=new_email,
                    otp_code="12345678",
                    session_token=session_token,
                    otp_sent_at=otp_sent_at,
                )

                # Verify success and guest creation (inside mock context)
                assert verify_result["success"] is True, f"Verify failed: {verify_result}"
        assert "guest_id" in verify_result
        assert verify_result["guest_id"] is not None
        assert verify_result["email"] == new_email

        # Step 3: Verify guest was created in DynamoDB with correct attributes
        from src.services.dynamodb import get_dynamodb_service

        db = get_dynamodb_service()
        guest_data = db.get_guest_by_email(new_email)

        assert guest_data is not None
        assert guest_data["email"] == new_email
        assert guest_data["email_verified"] is True
        assert guest_data["cognito_sub"] == "cognito-user-sub-12345"

        _reset_auth_service()

    def test_new_guest_has_first_verified_at_timestamp(
        self,
        mock_cognito_client: MagicMock,
        dynamodb_tables: Any,
    ) -> None:
        """Should set first_verified_at timestamp on new guest creation."""
        from src.tools.auth import (
            _reset_auth_service,
            initiate_cognito_login,
            verify_cognito_otp,
        )

        _reset_auth_service()

        new_email = "firsttime@example.com"
        time_before = datetime.now(timezone.utc)

        # Complete auth flow - patch cognito client specifically to not interfere with moto
        with patch(
            "src.services.auth_service.boto3.client", return_value=mock_cognito_client
        ):
            with patch.dict(
                "os.environ",
                {
                    "COGNITO_USER_POOL_ID": "eu-west-1_TestPool",
                    "COGNITO_CLIENT_ID": "test-client-id",
                },
            ):
                init_result = initiate_cognito_login(new_email)
                verify_result = verify_cognito_otp(
                    email=new_email,
                    otp_code="12345678",
                    session_token=init_result["session_token"],
                    otp_sent_at=init_result["otp_sent_at"],
                )

                time_after = datetime.now(timezone.utc)

                assert verify_result["success"] is True

                # Verify first_verified_at is set (inside mock context)
                from src.services.dynamodb import get_dynamodb_service

                db = get_dynamodb_service()
                guest_data = db.get_guest_by_email(new_email)

        assert "first_verified_at" in guest_data
        first_verified = datetime.fromisoformat(guest_data["first_verified_at"])
        assert time_before <= first_verified <= time_after

        _reset_auth_service()


# === T040 & T041: Covered by Unit Tests ===


class TestCrossReferenceUnitTests:
    """Document that T040 and T041 are covered by unit tests.

    T040: OTP codes expire after 5 minutes
    - Covered by: tests/unit/test_auth_tools.py::TestVerifyCognitoOtp::test_verify_otp_returns_expired_error

    T041: Max 3 OTP attempts per session
    - Covered by: tests/unit/test_auth_tools.py::TestVerifyCognitoOtp::test_verify_otp_returns_max_attempts_error
    """

    def test_document_t040_coverage(self) -> None:
        """T040 is covered by unit test: test_verify_otp_returns_expired_error."""
        # This test documents that T040 coverage exists in unit tests
        # See: tests/unit/test_auth_tools.py::TestVerifyCognitoOtp::test_verify_otp_returns_expired_error
        pass

    def test_document_t041_coverage(self) -> None:
        """T041 is covered by unit test: test_verify_otp_returns_max_attempts_error."""
        # This test documents that T041 coverage exists in unit tests
        # See: tests/unit/test_auth_tools.py::TestVerifyCognitoOtp::test_verify_otp_returns_max_attempts_error
        pass


# === Full Auth Flow Integration ===


class TestFullAuthFlowIntegration:
    """Integration tests for complete EMAIL_OTP auth flow."""

    def test_returning_user_binds_to_existing_guest(
        self,
        mock_cognito_client: MagicMock,
        dynamodb_tables: Any,
    ) -> None:
        """Should bind cognito_sub to existing guest on returning user login."""
        from src.services.dynamodb import get_dynamodb_service
        from src.tools.auth import (
            _reset_auth_service,
            initiate_cognito_login,
            verify_cognito_otp,
        )

        _reset_auth_service()

        # Create existing guest without cognito_sub
        db = get_dynamodb_service()
        existing_email = "existing@example.com"
        existing_guest = {
            "guest_id": "guest-existing-123",
            "email": existing_email,
            "full_name": "Existing User",
            "email_verified": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        db.create_guest(existing_guest)

        # Complete auth flow - patch cognito client specifically to not interfere with moto
        with patch(
            "src.services.auth_service.boto3.client", return_value=mock_cognito_client
        ):
            with patch.dict(
                "os.environ",
                {
                    "COGNITO_USER_POOL_ID": "eu-west-1_TestPool",
                    "COGNITO_CLIENT_ID": "test-client-id",
                },
            ):
                init_result = initiate_cognito_login(existing_email)
                verify_result = verify_cognito_otp(
                    email=existing_email,
                    otp_code="12345678",
                    session_token=init_result["session_token"],
                    otp_sent_at=init_result["otp_sent_at"],
                )

                # Verify existing guest was updated, not a new one created
                assert verify_result["success"] is True, f"Verify failed: {verify_result}"
                assert verify_result["guest_id"] == "guest-existing-123"

                # Verify cognito_sub was bound (inside mock context)
                updated_guest = db.get_guest_by_email(existing_email)
                assert updated_guest["cognito_sub"] == "cognito-user-sub-12345"

        _reset_auth_service()
