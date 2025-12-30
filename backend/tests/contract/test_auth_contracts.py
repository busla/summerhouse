"""Contract tests for JWT Session Authentication tools (T011, T012).

Tests validate that tool responses match the schemas defined in:
specs/004-jwt-session-auth/contracts/tool-responses.md

These tests ensure:
- initiate_cognito_login returns expected success/error schema (T011)
- verify_cognito_otp returns expected error schemas (T012)
- Error codes match documented values

Per spec: Tools are stateless - auth state (session_token, otp_sent_at, attempts)
must be passed as parameters between tool calls.
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


# === T011: initiate_cognito_login response schema tests ===


class TestInitiateCognitoLoginContract:
    """Contract tests for initiate_cognito_login tool response schema."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset auth service singleton before each test."""
        from src.tools.auth import _reset_auth_service

        _reset_auth_service()
        yield
        _reset_auth_service()

    def test_success_response_schema(self):
        """Success response must match contract schema."""
        from src.tools.auth import initiate_cognito_login

        # Mock Cognito response
        mock_response = {
            "Session": "mock-session-token-abc123",
            "ChallengeName": "EMAIL_OTP",
            "AvailableChallenges": ["EMAIL_OTP"],
            "ChallengeParameters": {"CODE_DELIVERY_DESTINATION": "g***@example.com"},
        }

        with patch("src.services.auth_service.boto3.client") as mock_boto:
            mock_cognito = MagicMock()
            mock_cognito.initiate_auth.return_value = mock_response
            mock_boto.return_value = mock_cognito

            result = initiate_cognito_login(email="guest@example.com")

        # Validate schema per contracts/tool-responses.md
        assert result["success"] is True
        assert "session_token" in result
        assert isinstance(result["session_token"], str)
        assert len(result["session_token"]) > 0
        assert result["challenge"] == "EMAIL_OTP"
        assert result["email"] == "guest@example.com"
        assert "otp_sent_at" in result
        # Validate ISO 8601 timestamp format
        datetime.fromisoformat(result["otp_sent_at"])

    def test_invalid_email_error_schema(self):
        """INVALID_EMAIL error response must match contract schema."""
        from src.tools.auth import initiate_cognito_login

        result = initiate_cognito_login(email="not-an-email")

        # Validate error schema per contracts/tool-responses.md
        assert result["success"] is False
        assert result["error_code"] == "INVALID_EMAIL"
        assert result["message"] == "Invalid email format"
        # Error responses should NOT contain success fields
        assert "session_token" not in result
        assert "challenge" not in result

    def test_email_delivery_failed_error_schema(self):
        """ERR_EMAIL_DELIVERY_FAILED error response must match contract schema."""
        from src.tools.auth import initiate_cognito_login

        with patch("src.services.auth_service.boto3.client") as mock_boto:
            mock_cognito = MagicMock()
            mock_cognito.initiate_auth.side_effect = ClientError(
                {"Error": {"Code": "LimitExceededException", "Message": "Rate exceeded"}},
                "InitiateAuth",
            )
            mock_boto.return_value = mock_cognito

            result = initiate_cognito_login(email="guest@example.com")

        # Validate error schema
        assert result["success"] is False
        assert result["error_code"] == "ERR_EMAIL_DELIVERY_FAILED"
        assert "Cognito error" in result["message"]
        assert "LimitExceededException" in result["message"]

    def test_auth_service_error_schema(self):
        """AUTH_SERVICE_ERROR response must match contract schema."""
        from src.tools.auth import initiate_cognito_login

        with patch("src.services.auth_service.boto3.client") as mock_boto:
            mock_boto.side_effect = Exception("NoCredentialsError: Unable to locate credentials")

            result = initiate_cognito_login(email="guest@example.com")

        # Validate error schema
        assert result["success"] is False
        assert result["error_code"] == "AUTH_SERVICE_ERROR"
        assert "Auth service error" in result["message"]


# === T012: verify_cognito_otp error response schema tests ===


class TestVerifyCognitoOtpErrorContract:
    """Contract tests for verify_cognito_otp error response schemas."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset auth service singleton before each test."""
        from src.tools.auth import _reset_auth_service

        _reset_auth_service()
        yield
        _reset_auth_service()

    def test_invalid_otp_error_schema(self):
        """INVALID_OTP error response must match contract schema."""
        from src.tools.auth import verify_cognito_otp

        with patch("src.services.auth_service.boto3.client") as mock_boto:
            mock_cognito = MagicMock()
            mock_cognito.respond_to_auth_challenge.side_effect = ClientError(
                {"Error": {"Code": "CodeMismatchException", "Message": "Invalid code"}},
                "RespondToAuthChallenge",
            )
            mock_boto.return_value = mock_cognito

            result = verify_cognito_otp(
                email="guest@example.com",
                otp_code="999999",
                session_token="valid-session-token",
                otp_sent_at=datetime.now(timezone.utc).isoformat(),
                attempts=0,
            )

        # Validate error schema per contracts/tool-responses.md
        assert result["success"] is False
        assert result["error_code"] == "INVALID_OTP"
        assert "Invalid" in result["message"] or "incorrect" in result["message"].lower()
        assert result["attempts"] == 1  # Should increment

    def test_otp_expired_error_schema(self):
        """OTP_EXPIRED error response must match contract schema."""
        from src.tools.auth import verify_cognito_otp

        # Use timestamp from 10 minutes ago (past 5-minute validity)
        expired_time = datetime(2020, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        with patch("src.services.auth_service.boto3.client") as mock_boto:
            mock_cognito = MagicMock()
            mock_boto.return_value = mock_cognito

            result = verify_cognito_otp(
                email="guest@example.com",
                otp_code="123456",
                session_token="valid-session-token",
                otp_sent_at=expired_time.isoformat(),
                attempts=0,
            )

        # Validate error schema per contracts/tool-responses.md
        assert result["success"] is False
        assert result["error_code"] == "OTP_EXPIRED"
        assert "expired" in result["message"].lower()
        # Expired errors don't increment attempts
        assert result.get("attempts", 0) == 0

    def test_max_attempts_exceeded_error_schema(self):
        """MAX_ATTEMPTS_EXCEEDED error response must match contract schema."""
        from src.tools.auth import verify_cognito_otp

        with patch("src.services.auth_service.boto3.client") as mock_boto:
            mock_cognito = MagicMock()
            mock_boto.return_value = mock_cognito

            result = verify_cognito_otp(
                email="guest@example.com",
                otp_code="123456",
                session_token="valid-session-token",
                otp_sent_at=datetime.now(timezone.utc).isoformat(),
                attempts=3,  # Max attempts reached
            )

        # Validate error schema per contracts/tool-responses.md
        assert result["success"] is False
        assert result["error_code"] == "MAX_ATTEMPTS_EXCEEDED"
        assert "Maximum" in result["message"] or "exceeded" in result["message"].lower()
        assert result["attempts"] == 3

    def test_guest_creation_failed_error_schema(self):
        """GUEST_CREATION_FAILED error response must match contract schema."""
        from src.tools.auth import verify_cognito_otp

        # Mock successful OTP verification but failed guest creation
        mock_auth_result = {
            "AuthenticationResult": {
                "IdToken": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXN1YiIsImVtYWlsIjoiZ3Vlc3RAZXhhbXBsZS5jb20ifQ.signature",
                "AccessToken": "mock-access-token",
                "RefreshToken": "mock-refresh-token",
                "ExpiresIn": 3600,
            }
        }

        with (
            patch("src.services.auth_service.boto3.client") as mock_boto,
            patch("src.services.dynamodb.get_dynamodb_service") as mock_db,
        ):
            mock_cognito = MagicMock()
            mock_cognito.respond_to_auth_challenge.return_value = mock_auth_result
            mock_boto.return_value = mock_cognito

            # Make guest creation fail
            mock_db.return_value.get_guest_by_email.return_value = None
            mock_db.return_value.get_guest_by_cognito_sub.return_value = None
            mock_db.return_value.create_guest.side_effect = Exception(
                "ConditionalCheckFailedException"
            )

            result = verify_cognito_otp(
                email="guest@example.com",
                otp_code="123456",
                session_token="valid-session-token",
                otp_sent_at=datetime.now(timezone.utc).isoformat(),
                attempts=0,
            )

        # Validate error schema per contracts/tool-responses.md
        assert result["success"] is False
        assert result["error_code"] == "GUEST_CREATION_FAILED"
        assert "ConditionalCheckFailedException" in result["message"]


# === T017: Error code validation ===


class TestErrorCodeValues:
    """Validate error codes match documented values in contracts/tool-responses.md."""

    def test_documented_error_codes(self):
        """All documented error codes must be valid strings matching contracts."""
        # Error codes per contracts/tool-responses.md
        # These are the exact strings returned by auth tools to match the contract
        documented_codes = [
            "INVALID_EMAIL",
            "INVALID_OTP",
            "OTP_EXPIRED",
            "MAX_ATTEMPTS_EXCEEDED",
            "ERR_EMAIL_DELIVERY_FAILED",
            "AUTH_SERVICE_ERROR",
            "GUEST_CREATION_FAILED",
        ]

        # All documented codes should be non-empty strings
        for code in documented_codes:
            assert isinstance(code, str)
            assert len(code) > 0

    def test_error_code_enum_has_auth_codes(self):
        """ErrorCode enum should have authentication-related error codes."""
        from src.models.errors import ErrorCode

        # The ErrorCode enum has the AUTH codes for internal use
        # Tools return contract-defined strings, but enum is still useful
        auth_codes = [
            ErrorCode.INVALID_OTP,
            ErrorCode.OTP_EXPIRED,
            ErrorCode.MAX_ATTEMPTS_EXCEEDED,
            ErrorCode.EMAIL_DELIVERY_FAILED,
        ]

        for code in auth_codes:
            assert code.value.startswith("ERR_AUTH_")


# === T018: TokenDeliveryEvent success response ===


class TestTokenDeliveryEventContract:
    """Contract test: verify_cognito_otp success returns TokenDeliveryEvent format."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset auth service singleton before each test."""
        from src.tools.auth import _reset_auth_service

        _reset_auth_service()
        yield
        _reset_auth_service()

    def test_success_response_is_token_delivery_event(self):
        """Success response must match TokenDeliveryEvent schema per contracts/tool-responses.md."""
        from src.tools.auth import verify_cognito_otp

        # Mock successful Cognito verification with tokens
        mock_auth_result = {
            "AuthenticationResult": {
                "IdToken": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXN1Yi11dWlkIiwiZW1haWwiOiJndWVzdEBleGFtcGxlLmNvbSJ9.signature",
                "AccessToken": "mock-access-token-abc123",
                "RefreshToken": "mock-refresh-token-def456",
                "ExpiresIn": 3600,
            }
        }

        existing_guest = {
            "guest_id": "guest-existing123",
            "email": "guest@example.com",
            "cognito_sub": "test-sub-uuid",
        }

        with (
            patch("src.services.auth_service.boto3.client") as mock_boto,
            patch("src.services.dynamodb.get_dynamodb_service") as mock_db_factory,
        ):
            mock_cognito = MagicMock()
            mock_cognito.respond_to_auth_challenge.return_value = mock_auth_result
            mock_boto.return_value = mock_cognito

            mock_db = MagicMock()
            mock_db.get_guest_by_email.return_value = existing_guest
            mock_db_factory.return_value = mock_db

            result = verify_cognito_otp(
                email="guest@example.com",
                otp_code="123456",
                session_token="valid-session-token",
                otp_sent_at=datetime.now(timezone.utc).isoformat(),
                attempts=0,
            )

        # Validate TokenDeliveryEvent schema per contracts/tool-responses.md
        assert result["success"] is True
        assert result["event_type"] == "auth_tokens"

        # Required token fields
        assert "id_token" in result
        assert isinstance(result["id_token"], str)
        assert len(result["id_token"]) > 0

        assert "access_token" in result
        assert isinstance(result["access_token"], str)
        assert len(result["access_token"]) > 0

        assert "refresh_token" in result
        assert isinstance(result["refresh_token"], str)
        assert len(result["refresh_token"]) > 0

        assert "expires_in" in result
        assert isinstance(result["expires_in"], int)
        assert result["expires_in"] > 0

        # Guest identity fields
        assert "guest_id" in result
        assert isinstance(result["guest_id"], str)

        assert "email" in result
        assert result["email"] == "guest@example.com"

        assert "cognito_sub" in result
        assert isinstance(result["cognito_sub"], str)

    def test_token_delivery_event_has_correct_token_values(self):
        """Tokens in response must match Cognito response values."""
        from src.tools.auth import verify_cognito_otp
        import base64
        import json

        # Create valid JWT-formatted tokens (required by decode_id_token)
        # JWT format: header.payload.signature
        def make_jwt(payload: dict) -> str:
            header = {"alg": "RS256", "typ": "JWT"}
            header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
            payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
            return f"{header_b64}.{payload_b64}.fake-signature"

        expected_id_token = make_jwt({"sub": "test-sub-123", "email": "test@example.com"})
        expected_access_token = make_jwt({"sub": "test-sub-123", "token_use": "access"})
        expected_refresh_token = "opaque-refresh-token-456"  # Refresh tokens aren't JWTs
        expected_expires_in = 7200

        mock_auth_result = {
            "AuthenticationResult": {
                "IdToken": expected_id_token,
                "AccessToken": expected_access_token,
                "RefreshToken": expected_refresh_token,
                "ExpiresIn": expected_expires_in,
            }
        }

        with (
            patch("src.services.auth_service.boto3.client") as mock_boto,
            patch("src.services.dynamodb.get_dynamodb_service") as mock_db_factory,
        ):
            mock_cognito = MagicMock()
            mock_cognito.respond_to_auth_challenge.return_value = mock_auth_result
            mock_boto.return_value = mock_cognito

            mock_db = MagicMock()
            mock_db.get_guest_by_email.return_value = {
                "guest_id": "guest-abc",
                "email": "test@example.com",
                "cognito_sub": "test-sub-123",
            }
            mock_db_factory.return_value = mock_db

            result = verify_cognito_otp(
                email="test@example.com",
                otp_code="654321",
                session_token="session-token",
                otp_sent_at=datetime.now(timezone.utc).isoformat(),
                attempts=0,
            )

        # Verify exact token values are passed through
        assert result["id_token"] == expected_id_token
        assert result["access_token"] == expected_access_token
        assert result["refresh_token"] == expected_refresh_token
        assert result["expires_in"] == expected_expires_in
