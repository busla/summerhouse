"""Unit tests for authentication service (T032).

Tests the Cognito USER_AUTH flow with EMAIL_OTP challenge.
Per TDD gate T032z: tests written BEFORE implementation.

Tests cover:
- initiate_passwordless_auth returns CognitoAuthState
- verify_otp success returns AuthResult with guest
- verify_otp with invalid code returns INVALID_OTP
- verify_otp with expired code returns OTP_EXPIRED
- verify_otp with max attempts returns MAX_ATTEMPTS_EXCEEDED
- get_or_create_guest creates new guest for unknown email
- get_or_create_guest binds cognito_sub to existing guest
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from moto import mock_aws

from src.models.auth import AuthResult, CognitoAuthChallenge, CognitoAuthState
from src.models.errors import ErrorCode


class TestInitiatePasswordlessAuth:
    """Tests for initiating Cognito passwordless login."""

    def test_initiate_returns_auth_state(
        self,
        mock_cognito_idp: MagicMock,
        cognito_user_pool_config: dict[str, str],
    ) -> None:
        """Should return CognitoAuthState with EMAIL_OTP challenge."""
        # Import here to allow module to be created during implementation
        from src.services.auth_service import AuthService

        # Given: A valid email address
        email = "test@example.com"

        # When: Initiating passwordless auth
        with patch("boto3.client", return_value=mock_cognito_idp):
            service = AuthService(
                user_pool_id=cognito_user_pool_config["user_pool_id"],
                client_id=cognito_user_pool_config["client_id"],
            )
            result = service.initiate_passwordless_auth(email)

        # Then: Should return auth state with EMAIL_OTP challenge
        assert isinstance(result, CognitoAuthState)
        assert result.challenge == CognitoAuthChallenge.EMAIL_OTP
        assert result.username == email
        assert result.session is not None
        assert result.attempts == 0
        assert result.otp_sent_at is not None

    def test_initiate_calls_cognito_with_user_auth(
        self,
        mock_cognito_idp: MagicMock,
        cognito_user_pool_config: dict[str, str],
    ) -> None:
        """Should call Cognito initiate_auth with USER_AUTH flow."""
        from src.services.auth_service import AuthService

        # Given: A valid email
        email = "test@example.com"

        # When: Initiating auth
        with patch("boto3.client", return_value=mock_cognito_idp):
            service = AuthService(
                user_pool_id=cognito_user_pool_config["user_pool_id"],
                client_id=cognito_user_pool_config["client_id"],
            )
            service.initiate_passwordless_auth(email)

        # Then: Should call Cognito with correct parameters
        mock_cognito_idp.initiate_auth.assert_called_once()
        call_args = mock_cognito_idp.initiate_auth.call_args
        assert call_args.kwargs["AuthFlow"] == "USER_AUTH"
        assert call_args.kwargs["AuthParameters"]["USERNAME"] == email
        assert "PREFERRED_CHALLENGE" in call_args.kwargs["AuthParameters"]
        assert call_args.kwargs["AuthParameters"]["PREFERRED_CHALLENGE"] == "EMAIL_OTP"

    def test_initiate_handles_cognito_error(
        self,
        mock_cognito_idp: MagicMock,
        cognito_user_pool_config: dict[str, str],
    ) -> None:
        """Should raise exception when Cognito fails with non-recoverable error."""
        from botocore.exceptions import ClientError

        from src.services.auth_service import AuthService

        # Given: Cognito returns a non-recoverable error (not UserNotFoundException)
        mock_cognito_idp.initiate_auth.side_effect = ClientError(
            {"Error": {"Code": "InvalidParameterException", "Message": "Invalid param"}},
            "InitiateAuth",
        )

        # When/Then: Should raise appropriate error
        with patch("boto3.client", return_value=mock_cognito_idp):
            service = AuthService(
                user_pool_id=cognito_user_pool_config["user_pool_id"],
                client_id=cognito_user_pool_config["client_id"],
            )
            with pytest.raises(ClientError):
                service.initiate_passwordless_auth("test@example.com")

    def test_initiate_creates_user_on_user_not_found(
        self,
        mock_cognito_idp: MagicMock,
        cognito_user_pool_config: dict[str, str],
    ) -> None:
        """Should create user and retry auth when PASSWORD options indicate non-existent user.

        Cognito's prevent_user_existence_errors masks non-existent users by returning
        PASSWORD_SRP/PASSWORD in AvailableChallenges. Real passwordless users only
        have EMAIL_OTP available.
        """
        from src.services.auth_service import AuthService

        # Given: First initiate_auth returns PASSWORD options (indicates non-existent user)
        # Then admin_create_user succeeds
        # Then second initiate_auth returns only EMAIL_OTP (real passwordless user)
        mock_cognito_idp.initiate_auth.side_effect = [
            # First call: non-existent user (masked by prevent_user_existence_errors)
            {
                "ChallengeName": "EMAIL_OTP",
                "Session": "mock-session-fake",
                "ChallengeParameters": {
                    "CODE_DELIVERY_DESTINATION": "n***@e***",  # Generic mask
                },
                "AvailableChallenges": ["PASSWORD_SRP", "PASSWORD", "EMAIL_OTP"],
            },
            # Second call: real user after creation
            {
                "ChallengeName": "EMAIL_OTP",
                "Session": "mock-session-after-create",
                "ChallengeParameters": {
                    "CODE_DELIVERY_DESTINATION": "n***@e***",
                },
                "AvailableChallenges": ["EMAIL_OTP"],
            },
        ]
        mock_cognito_idp.admin_create_user.return_value = {}

        email = "newuser@example.com"

        # When: Initiating auth for non-existent user
        with patch("boto3.client", return_value=mock_cognito_idp):
            service = AuthService(
                user_pool_id=cognito_user_pool_config["user_pool_id"],
                client_id=cognito_user_pool_config["client_id"],
            )
            result = service.initiate_passwordless_auth(email)

        # Then: Should create user and return auth state
        assert result is not None
        assert result.session == "mock-session-after-create"
        assert result.username == email

        # Verify admin_create_user was called
        mock_cognito_idp.admin_create_user.assert_called_once()
        call_args = mock_cognito_idp.admin_create_user.call_args.kwargs
        assert call_args["Username"] == email
        assert call_args["UserPoolId"] == cognito_user_pool_config["user_pool_id"]
        assert call_args["MessageAction"] == "SUPPRESS"

    def test_create_user_ignores_username_exists_race_condition(
        self,
        mock_cognito_idp: MagicMock,
        cognito_user_pool_config: dict[str, str],
    ) -> None:
        """Should handle race condition where user is created between check and create."""
        from botocore.exceptions import ClientError

        from src.services.auth_service import AuthService

        # Given: First initiate_auth returns PASSWORD options (non-existent user),
        # admin_create_user fails with UsernameExistsException (race condition),
        # then second initiate_auth succeeds (user exists from other request)
        mock_cognito_idp.initiate_auth.side_effect = [
            # First call: non-existent user (masked by prevent_user_existence_errors)
            {
                "ChallengeName": "EMAIL_OTP",
                "Session": "mock-session-fake",
                "ChallengeParameters": {
                    "CODE_DELIVERY_DESTINATION": "n***@e***",
                },
                "AvailableChallenges": ["PASSWORD_SRP", "PASSWORD", "EMAIL_OTP"],
            },
            # Second call succeeds (user now exists due to race condition)
            {
                "ChallengeName": "EMAIL_OTP",
                "Session": "mock-session-race",
                "ChallengeParameters": {
                    "CODE_DELIVERY_DESTINATION": "r***@e***",
                },
                "AvailableChallenges": ["EMAIL_OTP"],
            },
        ]
        mock_cognito_idp.admin_create_user.side_effect = ClientError(
            {"Error": {"Code": "UsernameExistsException", "Message": "User exists"}},
            "AdminCreateUser",
        )

        email = "race@example.com"

        # When: Initiating auth during race condition
        with patch("boto3.client", return_value=mock_cognito_idp):
            service = AuthService(
                user_pool_id=cognito_user_pool_config["user_pool_id"],
                client_id=cognito_user_pool_config["client_id"],
            )
            result = service.initiate_passwordless_auth(email)

        # Then: Should succeed despite UsernameExistsException
        assert result is not None
        assert result.session == "mock-session-race"


class TestVerifyOtp:
    """Tests for OTP verification."""

    def test_verify_otp_success(
        self,
        mock_cognito_idp: MagicMock,
        cognito_user_pool_config: dict[str, str],
    ) -> None:
        """Should return successful AuthResult with tokens on valid OTP."""
        from src.services.auth_service import AuthService

        # Given: A valid auth state and correct OTP
        auth_state = CognitoAuthState(
            session="mock-session-token",
            challenge=CognitoAuthChallenge.EMAIL_OTP,
            username="test@example.com",
            attempts=0,
            otp_sent_at=datetime.now(timezone.utc),
        )

        # When: Verifying with correct OTP
        with patch("boto3.client", return_value=mock_cognito_idp):
            service = AuthService(
                user_pool_id=cognito_user_pool_config["user_pool_id"],
                client_id=cognito_user_pool_config["client_id"],
            )
            result = service.verify_otp(auth_state, "123456")

        # Then: Should return success with cognito_sub
        assert isinstance(result, AuthResult)
        assert result.success is True
        assert result.cognito_sub is not None
        assert result.error_code is None

    def test_verify_otp_invalid_code(
        self,
        mock_cognito_idp: MagicMock,
        cognito_user_pool_config: dict[str, str],
    ) -> None:
        """Should return INVALID_OTP error on wrong code."""
        from botocore.exceptions import ClientError

        from src.services.auth_service import AuthService

        # Given: Invalid OTP triggers Cognito error
        mock_cognito_idp.respond_to_auth_challenge.side_effect = ClientError(
            {"Error": {"Code": "CodeMismatchException", "Message": "Invalid code"}},
            "RespondToAuthChallenge",
        )

        auth_state = CognitoAuthState(
            session="mock-session-token",
            challenge=CognitoAuthChallenge.EMAIL_OTP,
            username="test@example.com",
            attempts=0,
            otp_sent_at=datetime.now(timezone.utc),
        )

        # When: Verifying with wrong OTP
        with patch("boto3.client", return_value=mock_cognito_idp):
            service = AuthService(
                user_pool_id=cognito_user_pool_config["user_pool_id"],
                client_id=cognito_user_pool_config["client_id"],
            )
            result = service.verify_otp(auth_state, "000000")

        # Then: Should return INVALID_OTP error
        assert isinstance(result, AuthResult)
        assert result.success is False
        assert result.error_code == ErrorCode.INVALID_OTP.value

    def test_verify_otp_expired(
        self,
        mock_cognito_idp: MagicMock,
        cognito_user_pool_config: dict[str, str],
    ) -> None:
        """Should return OTP_EXPIRED error when code has expired."""
        from src.services.auth_service import AuthService

        # Given: Auth state with expired OTP (6 minutes ago)
        auth_state = CognitoAuthState(
            session="mock-session-token",
            challenge=CognitoAuthChallenge.EMAIL_OTP,
            username="test@example.com",
            attempts=0,
            otp_sent_at=datetime.now(timezone.utc) - timedelta(minutes=6),
        )

        # When: Verifying expired OTP
        with patch("boto3.client", return_value=mock_cognito_idp):
            service = AuthService(
                user_pool_id=cognito_user_pool_config["user_pool_id"],
                client_id=cognito_user_pool_config["client_id"],
            )
            result = service.verify_otp(auth_state, "123456")

        # Then: Should return OTP_EXPIRED error
        assert isinstance(result, AuthResult)
        assert result.success is False
        assert result.error_code == ErrorCode.OTP_EXPIRED.value

    def test_verify_otp_max_attempts_exceeded(
        self,
        mock_cognito_idp: MagicMock,
        cognito_user_pool_config: dict[str, str],
    ) -> None:
        """Should return MAX_ATTEMPTS_EXCEEDED after 3 failed attempts."""
        from src.services.auth_service import AuthService

        # Given: Auth state at max attempts
        auth_state = CognitoAuthState(
            session="mock-session-token",
            challenge=CognitoAuthChallenge.EMAIL_OTP,
            username="test@example.com",
            attempts=3,  # Already at max
            otp_sent_at=datetime.now(timezone.utc),
        )

        # When: Attempting to verify again
        with patch("boto3.client", return_value=mock_cognito_idp):
            service = AuthService(
                user_pool_id=cognito_user_pool_config["user_pool_id"],
                client_id=cognito_user_pool_config["client_id"],
            )
            result = service.verify_otp(auth_state, "123456")

        # Then: Should return MAX_ATTEMPTS_EXCEEDED
        assert isinstance(result, AuthResult)
        assert result.success is False
        assert result.error_code == ErrorCode.MAX_ATTEMPTS_EXCEEDED.value

    def test_verify_otp_increments_attempts(
        self,
        mock_cognito_idp: MagicMock,
        cognito_user_pool_config: dict[str, str],
    ) -> None:
        """Should increment attempt counter on failed verification."""
        from botocore.exceptions import ClientError

        from src.services.auth_service import AuthService

        # Given: Invalid OTP triggers Cognito error
        mock_cognito_idp.respond_to_auth_challenge.side_effect = ClientError(
            {"Error": {"Code": "CodeMismatchException", "Message": "Invalid code"}},
            "RespondToAuthChallenge",
        )

        auth_state = CognitoAuthState(
            session="mock-session-token",
            challenge=CognitoAuthChallenge.EMAIL_OTP,
            username="test@example.com",
            attempts=1,
            otp_sent_at=datetime.now(timezone.utc),
        )

        # When: Verifying with wrong OTP
        with patch("boto3.client", return_value=mock_cognito_idp):
            service = AuthService(
                user_pool_id=cognito_user_pool_config["user_pool_id"],
                client_id=cognito_user_pool_config["client_id"],
            )
            result, updated_state = service.verify_otp_with_state(auth_state, "000000")

        # Then: Attempt counter should be incremented
        assert updated_state.attempts == 2


class TestGetOrCreateGuest:
    """Tests for guest lookup/creation after authentication."""

    @mock_aws
    def test_get_or_create_guest_creates_new(
        self,
        dynamodb_client: Any,
        create_tables: None,
    ) -> None:
        """Should create new guest when email doesn't exist."""
        from src.services.auth_service import AuthService

        # Given: A new email with no existing guest
        email = "newuser@example.com"
        cognito_sub = "cognito-sub-123-new"

        # When: Getting or creating guest
        service = AuthService(
            user_pool_id="eu-west-1_TestPool",
            client_id="test-client-id",
        )
        guest = service.get_or_create_guest(email, cognito_sub)

        # Then: Should create a new guest
        assert guest is not None
        assert guest.email == email
        assert guest.cognito_sub == cognito_sub
        assert guest.guest_id is not None
        assert guest.email_verified is True  # Verified via Cognito

    @mock_aws
    def test_get_or_create_guest_returns_existing(
        self,
        dynamodb_client: Any,
        create_tables: None,
        sample_guest: dict[str, Any],
    ) -> None:
        """Should return existing guest when email exists."""
        from src.services.auth_service import AuthService

        # Given: An existing guest in the database
        dynamodb_client.put_item(
            TableName="test-booking-guests",
            Item={
                "guest_id": {"S": sample_guest["guest_id"]},
                "email": {"S": sample_guest["email"]},
                "full_name": {"S": sample_guest["full_name"]},
                "email_verified": {"BOOL": True},
            },
        )

        # When: Getting or creating with same email
        service = AuthService(
            user_pool_id="eu-west-1_TestPool",
            client_id="test-client-id",
        )
        guest = service.get_or_create_guest(
            sample_guest["email"],
            "cognito-sub-456",
        )

        # Then: Should return existing guest (same ID)
        assert guest.guest_id == sample_guest["guest_id"]
        assert guest.email == sample_guest["email"]

    @mock_aws
    def test_get_or_create_guest_binds_cognito_sub(
        self,
        dynamodb_client: Any,
        create_tables: None,
        sample_guest: dict[str, Any],
    ) -> None:
        """Should bind cognito_sub to existing guest without one."""
        from src.services.auth_service import AuthService

        # Given: Existing guest WITHOUT cognito_sub
        dynamodb_client.put_item(
            TableName="test-booking-guests",
            Item={
                "guest_id": {"S": sample_guest["guest_id"]},
                "email": {"S": sample_guest["email"]},
                "full_name": {"S": sample_guest["full_name"]},
                "email_verified": {"BOOL": True},
                # No cognito_sub field
            },
        )

        cognito_sub = "cognito-sub-789"

        # When: Getting or creating with cognito_sub
        service = AuthService(
            user_pool_id="eu-west-1_TestPool",
            client_id="test-client-id",
        )
        guest = service.get_or_create_guest(sample_guest["email"], cognito_sub)

        # Then: Should update guest with cognito_sub
        assert guest.cognito_sub == cognito_sub

        # Verify persisted to database
        response = dynamodb_client.get_item(
            TableName="test-booking-guests",
            Key={"guest_id": {"S": sample_guest["guest_id"]}},
        )
        assert response["Item"]["cognito_sub"]["S"] == cognito_sub

    @mock_aws
    def test_get_or_create_guest_validates_cognito_sub_match(
        self,
        dynamodb_client: Any,
        create_tables: None,
        sample_guest: dict[str, Any],
    ) -> None:
        """Should raise error if cognito_sub doesn't match existing."""
        from src.models.errors import BookingError, ErrorCode
        from src.services.auth_service import AuthService

        # Given: Existing guest WITH a different cognito_sub
        dynamodb_client.put_item(
            TableName="test-booking-guests",
            Item={
                "guest_id": {"S": sample_guest["guest_id"]},
                "email": {"S": sample_guest["email"]},
                "cognito_sub": {"S": "existing-cognito-sub"},
                "email_verified": {"BOOL": True},
            },
        )

        # When/Then: Should raise USER_MISMATCH error
        service = AuthService(
            user_pool_id="eu-west-1_TestPool",
            client_id="test-client-id",
        )
        with pytest.raises(BookingError) as exc_info:
            service.get_or_create_guest(
                sample_guest["email"],
                "different-cognito-sub",  # Different from stored
            )

        assert exc_info.value.code == ErrorCode.USER_MISMATCH


class TestDecodeIdToken:
    """Tests for JWT token decoding."""

    def test_decode_id_token_extracts_sub(self) -> None:
        """Should extract cognito sub from ID token."""
        from src.services.auth_service import AuthService

        # Given: A mock JWT ID token (base64 encoded JSON)
        # Real tokens have 3 parts, we mock the payload part
        import base64
        import json

        payload = {"sub": "cognito-sub-from-token", "email": "test@example.com"}
        encoded_payload = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).decode().rstrip("=")
        mock_token = f"header.{encoded_payload}.signature"

        # When: Decoding the token
        service = AuthService(
            user_pool_id="eu-west-1_TestPool",
            client_id="test-client-id",
        )
        result = service.decode_id_token(mock_token)

        # Then: Should extract the sub claim
        assert result["sub"] == "cognito-sub-from-token"
        assert result["email"] == "test@example.com"
