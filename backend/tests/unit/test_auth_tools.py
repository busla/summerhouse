"""Unit tests for authentication tools (T037).

Tests the Strands @tool decorated functions for Cognito EMAIL_OTP flow.
Per TDD gate: tests written BEFORE implementation.

Tests cover:
- initiate_cognito_login returns success with session_token
- initiate_cognito_login returns EMAIL_DELIVERY_FAILED on exception
- verify_cognito_otp returns guest_id on success
- verify_cognito_otp returns INVALID_OTP error code
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from moto import mock_aws

from src.models.auth import CognitoAuthChallenge, CognitoAuthState


class TestInitiateCognitoLogin:
    """Tests for the initiate_cognito_login tool."""

    def test_initiate_returns_success_with_session_token(
        self,
        mock_cognito_idp: MagicMock,
    ) -> None:
        """Should return success=True with session_token and challenge info."""
        from src.tools.auth import initiate_cognito_login

        # Given: A valid email address
        email = "test@example.com"

        # When: Initiating passwordless login via tool
        with patch("boto3.client", return_value=mock_cognito_idp):
            with patch.dict(
                "os.environ",
                {
                    "COGNITO_USER_POOL_ID": "eu-west-1_TestPool",
                    "COGNITO_CLIENT_ID": "test-client-id",
                },
            ):
                result = initiate_cognito_login(email)

        # Then: Should return success with session info
        assert result["success"] is True
        assert "session_token" in result
        assert result["session_token"] is not None
        assert result["challenge"] == "EMAIL_OTP"
        assert result["email"] == email

    def test_initiate_returns_email_delivery_failed_on_exception(
        self,
        mock_cognito_idp: MagicMock,
    ) -> None:
        """Should return EMAIL_DELIVERY_FAILED error when Cognito fails."""
        from botocore.exceptions import ClientError

        from src.tools.auth import initiate_cognito_login

        # Given: Cognito raises an error (e.g., user not found or delivery failure)
        mock_cognito_idp.initiate_auth.side_effect = ClientError(
            {"Error": {"Code": "UserNotFoundException", "Message": "User not found"}},
            "InitiateAuth",
        )

        # When: Initiating auth
        with patch("boto3.client", return_value=mock_cognito_idp):
            with patch.dict(
                "os.environ",
                {
                    "COGNITO_USER_POOL_ID": "eu-west-1_TestPool",
                    "COGNITO_CLIENT_ID": "test-client-id",
                },
            ):
                result = initiate_cognito_login("nonexistent@example.com")

        # Then: Should return EMAIL_DELIVERY_FAILED error
        assert result["success"] is False
        assert result["error_code"] == "ERR_EMAIL_DELIVERY_FAILED"  # Contract-defined code

    def test_initiate_validates_email_format(self) -> None:
        """Should validate email format before calling Cognito."""
        from src.tools.auth import initiate_cognito_login

        # When: Initiating with invalid email
        with patch.dict(
            "os.environ",
            {
                "COGNITO_USER_POOL_ID": "eu-west-1_TestPool",
                "COGNITO_CLIENT_ID": "test-client-id",
            },
        ):
            result = initiate_cognito_login("invalid-email")

        # Then: Should return error
        assert result["success"] is False
        assert "error" in result or "message" in result


class TestVerifyCognitoOtp:
    """Tests for the verify_cognito_otp tool."""

    def test_verify_otp_returns_guest_id_on_success(
        self,
        mock_cognito_idp: MagicMock,
        dynamodb_client: Any,
        create_tables: None,
    ) -> None:
        """Should return success=True with guest_id on valid OTP."""
        from src.tools.auth import verify_cognito_otp

        # Given: A valid session token and OTP
        session_token = "mock-session-token-abc123"
        email = "test@example.com"
        otp_code = "123456"
        # Session was created recently
        otp_sent_at = datetime.now(timezone.utc).isoformat()

        # When: Verifying OTP via tool
        with patch("boto3.client", return_value=mock_cognito_idp):
            with patch.dict(
                "os.environ",
                {
                    "COGNITO_USER_POOL_ID": "eu-west-1_TestPool",
                    "COGNITO_CLIENT_ID": "test-client-id",
                },
            ):
                result = verify_cognito_otp(
                    email=email,
                    otp_code=otp_code,
                    session_token=session_token,
                    otp_sent_at=otp_sent_at,
                )

        # Then: Should return success with guest info
        assert result["success"] is True
        assert "guest_id" in result
        assert result["guest_id"] is not None
        assert "cognito_sub" in result

    def test_verify_otp_returns_invalid_otp_error(
        self,
        mock_cognito_idp: MagicMock,
    ) -> None:
        """Should return INVALID_OTP error on wrong code."""
        from botocore.exceptions import ClientError

        from src.tools.auth import verify_cognito_otp

        # Given: Cognito rejects the OTP code
        mock_cognito_idp.respond_to_auth_challenge.side_effect = ClientError(
            {"Error": {"Code": "CodeMismatchException", "Message": "Invalid code"}},
            "RespondToAuthChallenge",
        )

        session_token = "mock-session-token"
        email = "test@example.com"
        otp_sent_at = datetime.now(timezone.utc).isoformat()

        # When: Verifying with wrong OTP
        with patch("boto3.client", return_value=mock_cognito_idp):
            with patch.dict(
                "os.environ",
                {
                    "COGNITO_USER_POOL_ID": "eu-west-1_TestPool",
                    "COGNITO_CLIENT_ID": "test-client-id",
                },
            ):
                result = verify_cognito_otp(
                    email=email,
                    otp_code="000000",
                    session_token=session_token,
                    otp_sent_at=otp_sent_at,
                )

        # Then: Should return INVALID_OTP error
        assert result["success"] is False
        assert result["error_code"] == "INVALID_OTP"  # Contract-defined code

    def test_verify_otp_returns_expired_error(
        self,
        mock_cognito_idp: MagicMock,
    ) -> None:
        """Should return OTP_EXPIRED error when code is expired."""
        from datetime import timedelta

        from src.tools.auth import verify_cognito_otp

        # Given: OTP was sent 6 minutes ago (expired - 5 min validity)
        otp_sent_at = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()

        # When: Verifying expired OTP
        with patch("boto3.client", return_value=mock_cognito_idp):
            with patch.dict(
                "os.environ",
                {
                    "COGNITO_USER_POOL_ID": "eu-west-1_TestPool",
                    "COGNITO_CLIENT_ID": "test-client-id",
                },
            ):
                result = verify_cognito_otp(
                    email="test@example.com",
                    otp_code="123456",
                    session_token="mock-session",
                    otp_sent_at=otp_sent_at,
                )

        # Then: Should return OTP_EXPIRED error
        assert result["success"] is False
        assert result["error_code"] == "OTP_EXPIRED"  # Contract-defined code

    def test_verify_otp_returns_max_attempts_error(
        self,
        mock_cognito_idp: MagicMock,
    ) -> None:
        """Should return MAX_ATTEMPTS_EXCEEDED after 3 failed attempts."""
        from src.tools.auth import verify_cognito_otp

        # Given: Session already has 3 attempts
        otp_sent_at = datetime.now(timezone.utc).isoformat()

        # When: Verifying with max attempts already reached
        with patch("boto3.client", return_value=mock_cognito_idp):
            with patch.dict(
                "os.environ",
                {
                    "COGNITO_USER_POOL_ID": "eu-west-1_TestPool",
                    "COGNITO_CLIENT_ID": "test-client-id",
                },
            ):
                result = verify_cognito_otp(
                    email="test@example.com",
                    otp_code="123456",
                    session_token="mock-session",
                    otp_sent_at=otp_sent_at,
                    attempts=3,  # Already at max
                )

        # Then: Should return MAX_ATTEMPTS_EXCEEDED
        assert result["success"] is False
        assert result["error_code"] == "MAX_ATTEMPTS_EXCEEDED"  # Contract-defined code


class TestAuthToolsIntegration:
    """Integration tests for auth tool workflow."""

    @mock_aws
    def test_full_auth_flow_creates_new_guest(
        self,
        mock_cognito_idp: MagicMock,
        dynamodb_client: Any,
        create_tables: None,
    ) -> None:
        """Should complete full auth flow and create new guest."""
        from src.tools.auth import initiate_cognito_login, verify_cognito_otp

        email = "newuser@example.com"

        # Step 1: Initiate login
        with patch("boto3.client", return_value=mock_cognito_idp):
            with patch.dict(
                "os.environ",
                {
                    "COGNITO_USER_POOL_ID": "eu-west-1_TestPool",
                    "COGNITO_CLIENT_ID": "test-client-id",
                },
            ):
                init_result = initiate_cognito_login(email)

        assert init_result["success"] is True
        session_token = init_result["session_token"]
        otp_sent_at = init_result.get("otp_sent_at")

        # Step 2: Verify OTP (uses session from step 1)
        with patch("boto3.client", return_value=mock_cognito_idp):
            with patch.dict(
                "os.environ",
                {
                    "COGNITO_USER_POOL_ID": "eu-west-1_TestPool",
                    "COGNITO_CLIENT_ID": "test-client-id",
                },
            ):
                verify_result = verify_cognito_otp(
                    email=email,
                    otp_code="123456",
                    session_token=session_token,
                    otp_sent_at=otp_sent_at,
                )

        # Then: Should have created a guest
        assert verify_result["success"] is True
        assert verify_result["guest_id"] is not None
        assert verify_result["email"] == email
