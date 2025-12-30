"""Integration tests for JWT Session Authentication flow (T013, T029, T034, T035).

Tests the complete end-to-end authentication flow:
- T013: Full OTP flow (initiate → verify) with mocked Cognito
- T029: Backend receives and validates JWT from payload
- T034: New email triggers user creation
- T035: Guest record created in DynamoDB on first auth

These tests use mocked Cognito but real auth service logic to validate
the complete authentication flow works correctly.
"""

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# === T013: Full OTP Flow Integration Test ===


class TestOTPFlowIntegration:
    """Integration test for complete OTP authentication flow."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset auth service singleton and mock DynamoDB before each test."""
        from src.tools.auth import _reset_auth_service

        _reset_auth_service()
        yield
        _reset_auth_service()

    @pytest.fixture
    def mock_cognito_success(self):
        """Mock Cognito for successful OTP flow."""
        mock_initiate_response = {
            "Session": "mock-session-token-xyz789",
            "ChallengeName": "EMAIL_OTP",
            "AvailableChallenges": ["EMAIL_OTP"],
            "ChallengeParameters": {
                "CODE_DELIVERY_DESTINATION": "g***@example.com",
            },
        }

        mock_verify_response = {
            "AuthenticationResult": {
                "IdToken": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMWIyYzNkNC1lNWY2LTc4OTAtYWJjZC1lZjEyMzQ1Njc4OTAiLCJlbWFpbCI6Imd1ZXN0QGV4YW1wbGUuY29tIiwiZW1haWxfdmVyaWZpZWQiOnRydWV9.signature",
                "AccessToken": "mock-access-token-abc123",
                "RefreshToken": "mock-refresh-token-def456",
                "ExpiresIn": 3600,
            }
        }

        return mock_initiate_response, mock_verify_response

    @pytest.fixture
    def mock_dynamodb_guest(self):
        """Mock DynamoDB for guest operations."""
        mock_db = MagicMock()
        mock_db.get_guest_by_email.return_value = None  # New user
        mock_db.get_guest_by_cognito_sub.return_value = None  # T038: No existing by sub either
        mock_db.create_guest.return_value = None
        return mock_db

    def test_complete_otp_flow_success(self, mock_cognito_success, mock_dynamodb_guest):
        """Test complete flow: initiate → verify → guest created."""
        from src.tools.auth import initiate_cognito_login, verify_cognito_otp

        mock_initiate, mock_verify = mock_cognito_success

        with (
            patch("src.services.auth_service.boto3.client") as mock_boto,
            patch("src.services.dynamodb.get_dynamodb_service") as mock_db_factory,
        ):
            mock_cognito = MagicMock()
            mock_cognito.initiate_auth.return_value = mock_initiate
            mock_cognito.respond_to_auth_challenge.return_value = mock_verify
            mock_boto.return_value = mock_cognito
            mock_db_factory.return_value = mock_dynamodb_guest

            # Step 1: Initiate login
            initiate_result = initiate_cognito_login(email="guest@example.com")

            assert initiate_result["success"] is True
            assert initiate_result["challenge"] == "EMAIL_OTP"
            session_token = initiate_result["session_token"]
            otp_sent_at = initiate_result["otp_sent_at"]

            # Step 2: Verify OTP (simulating user entering correct code)
            verify_result = verify_cognito_otp(
                email="guest@example.com",
                otp_code="123456",
                session_token=session_token,
                otp_sent_at=otp_sent_at,
                attempts=0,
            )

            # Validate success
            assert verify_result["success"] is True
            assert "guest_id" in verify_result
            assert "cognito_sub" in verify_result
            assert verify_result["email"] == "guest@example.com"

            # Verify guest was created in DynamoDB
            mock_dynamodb_guest.create_guest.assert_called_once()
            created_guest = mock_dynamodb_guest.create_guest.call_args[0][0]
            assert created_guest["email"] == "guest@example.com"
            assert "cognito_sub" in created_guest

    def test_otp_flow_retry_on_invalid_code(self, mock_cognito_success):
        """Test retry flow: invalid OTP → retry with correct code."""
        from src.tools.auth import initiate_cognito_login, verify_cognito_otp
        from botocore.exceptions import ClientError

        mock_initiate, mock_verify = mock_cognito_success

        with (
            patch("src.services.auth_service.boto3.client") as mock_boto,
            patch("src.services.dynamodb.get_dynamodb_service") as mock_db_factory,
        ):
            mock_cognito = MagicMock()
            mock_cognito.initiate_auth.return_value = mock_initiate

            # First call fails, second succeeds
            mock_cognito.respond_to_auth_challenge.side_effect = [
                ClientError(
                    {"Error": {"Code": "CodeMismatchException", "Message": "Invalid code"}},
                    "RespondToAuthChallenge",
                ),
                mock_verify,
            ]
            mock_boto.return_value = mock_cognito

            mock_db = MagicMock()
            mock_db.get_guest_by_email.return_value = None
            mock_db.get_guest_by_cognito_sub.return_value = None  # T038: No existing by sub
            mock_db.create_guest.return_value = None
            mock_db_factory.return_value = mock_db

            # Step 1: Initiate login
            initiate_result = initiate_cognito_login(email="guest@example.com")
            session_token = initiate_result["session_token"]
            otp_sent_at = initiate_result["otp_sent_at"]

            # Step 2: First attempt with wrong code
            wrong_result = verify_cognito_otp(
                email="guest@example.com",
                otp_code="000000",  # Wrong code
                session_token=session_token,
                otp_sent_at=otp_sent_at,
                attempts=0,
            )

            assert wrong_result["success"] is False
            assert wrong_result["error_code"] == "INVALID_OTP"  # Contract-defined code
            assert wrong_result["attempts"] == 1

            # Step 3: Retry with correct code
            correct_result = verify_cognito_otp(
                email="guest@example.com",
                otp_code="123456",  # Correct code
                session_token=session_token,
                otp_sent_at=otp_sent_at,
                attempts=1,  # Increment attempts
            )

            assert correct_result["success"] is True
            assert "guest_id" in correct_result

    def test_otp_flow_max_attempts_reached(self, mock_cognito_success):
        """Test flow blocked after max attempts."""
        from src.tools.auth import initiate_cognito_login, verify_cognito_otp

        mock_initiate, _ = mock_cognito_success

        with patch("src.services.auth_service.boto3.client") as mock_boto:
            mock_cognito = MagicMock()
            mock_cognito.initiate_auth.return_value = mock_initiate
            mock_boto.return_value = mock_cognito

            # Step 1: Initiate login
            initiate_result = initiate_cognito_login(email="guest@example.com")
            session_token = initiate_result["session_token"]
            otp_sent_at = initiate_result["otp_sent_at"]

            # Step 2: Attempt with max attempts already reached
            result = verify_cognito_otp(
                email="guest@example.com",
                otp_code="123456",
                session_token=session_token,
                otp_sent_at=otp_sent_at,
                attempts=3,  # Max reached
            )

            # Should fail without even calling Cognito
            assert result["success"] is False
            assert result["error_code"] == "MAX_ATTEMPTS_EXCEEDED"  # Contract-defined code
            mock_cognito.respond_to_auth_challenge.assert_not_called()


# === T034/T035: New User Registration Flow ===


class TestNewUserRegistration:
    """Integration tests for new user registration via OTP flow."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset auth service singleton before each test."""
        from src.tools.auth import _reset_auth_service

        _reset_auth_service()
        yield
        _reset_auth_service()

    def test_new_user_triggers_cognito_creation(self):
        """T034: New email triggers user creation in Cognito."""
        from src.tools.auth import initiate_cognito_login

        # First call returns PASSWORD_SRP (user doesn't exist)
        # After admin_create_user, second call returns EMAIL_OTP only
        first_response = {
            "Session": "temp-session",
            "ChallengeName": "EMAIL_OTP",
            "AvailableChallenges": ["EMAIL_OTP", "PASSWORD_SRP", "PASSWORD"],
        }
        second_response = {
            "Session": "real-session-token",
            "ChallengeName": "EMAIL_OTP",
            "AvailableChallenges": ["EMAIL_OTP"],
        }

        with patch("src.services.auth_service.boto3.client") as mock_boto:
            mock_cognito = MagicMock()
            mock_cognito.initiate_auth.side_effect = [first_response, second_response]
            mock_cognito.admin_create_user.return_value = {}
            mock_boto.return_value = mock_cognito

            result = initiate_cognito_login(email="newuser@example.com")

            assert result["success"] is True
            # Verify admin_create_user was called
            mock_cognito.admin_create_user.assert_called_once()
            create_call = mock_cognito.admin_create_user.call_args
            assert any(
                attr["Value"] == "newuser@example.com"
                for attr in create_call.kwargs.get("UserAttributes", [])
            )

    def test_guest_record_created_on_first_auth(self):
        """T035: Guest record created in DynamoDB on first auth."""
        from src.tools.auth import verify_cognito_otp

        mock_verify_response = {
            "AuthenticationResult": {
                "IdToken": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJuZXctdXNlci1zdWIiLCJlbWFpbCI6Im5ld3VzZXJAZXhhbXBsZS5jb20ifQ.sig",
                "AccessToken": "access-token",
                "RefreshToken": "refresh-token",
                "ExpiresIn": 3600,
            }
        }

        with (
            patch("src.services.auth_service.boto3.client") as mock_boto,
            patch("src.services.dynamodb.get_dynamodb_service") as mock_db_factory,
        ):
            mock_cognito = MagicMock()
            mock_cognito.respond_to_auth_challenge.return_value = mock_verify_response
            mock_boto.return_value = mock_cognito

            mock_db = MagicMock()
            mock_db.get_guest_by_email.return_value = None  # No existing guest
            mock_db.get_guest_by_cognito_sub.return_value = None  # T038: No existing by sub
            mock_db.create_guest.return_value = None
            mock_db_factory.return_value = mock_db

            result = verify_cognito_otp(
                email="newuser@example.com",
                otp_code="123456",
                session_token="valid-session",
                otp_sent_at=datetime.now(timezone.utc).isoformat(),
                attempts=0,
            )

            assert result["success"] is True

            # Verify guest was created
            mock_db.create_guest.assert_called_once()
            created_data = mock_db.create_guest.call_args[0][0]

            # Validate guest record structure
            assert created_data["email"] == "newuser@example.com"
            assert "guest_id" in created_data
            assert created_data["guest_id"].startswith("guest-")
            assert "cognito_sub" in created_data
            assert created_data["email_verified"] is True

    def test_edge_case_email_changed_lookup_by_cognito_sub(self):
        """T038: Cognito user exists with different email - lookup by cognito_sub."""
        from src.tools.auth import verify_cognito_otp

        mock_verify_response = {
            "AuthenticationResult": {
                "IdToken": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJleGlzdGluZy1zdWItY2hhbmdlZC1lbWFpbCIsImVtYWlsIjoibmV3LWVtYWlsQGV4YW1wbGUuY29tIn0.sig",
                "AccessToken": "access-token",
                "RefreshToken": "refresh-token",
                "ExpiresIn": 3600,
            }
        }

        # Guest exists with different email but same cognito_sub
        existing_guest_by_sub = {
            "guest_id": "guest-oldemail123",
            "email": "old-email@example.com",
            "cognito_sub": "existing-sub-changed-email",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        with (
            patch("src.services.auth_service.boto3.client") as mock_boto,
            patch("src.services.dynamodb.get_dynamodb_service") as mock_db_factory,
        ):
            mock_cognito = MagicMock()
            mock_cognito.respond_to_auth_challenge.return_value = mock_verify_response
            mock_boto.return_value = mock_cognito

            mock_db = MagicMock()
            mock_db.get_guest_by_email.return_value = None  # No guest with new email
            mock_db.get_guest_by_cognito_sub.return_value = existing_guest_by_sub  # Found by sub
            mock_db.update_item.return_value = {}
            mock_db_factory.return_value = mock_db

            result = verify_cognito_otp(
                email="new-email@example.com",  # User changed email in Cognito
                otp_code="123456",
                session_token="valid-session",
                otp_sent_at=datetime.now(timezone.utc).isoformat(),
                attempts=0,
            )

            assert result["success"] is True
            assert result["guest_id"] == "guest-oldemail123"  # Existing guest found
            assert result["email"] == "new-email@example.com"  # Updated to new email

            # Should NOT create a new guest
            mock_db.create_guest.assert_not_called()

            # Should update the email on the existing guest
            mock_db.update_item.assert_called_once()
            update_call = mock_db.update_item.call_args
            assert update_call.kwargs["key"] == {"guest_id": "guest-oldemail123"}
            assert ":email" in update_call.kwargs["expression_attribute_values"]
            assert (
                update_call.kwargs["expression_attribute_values"][":email"]
                == "new-email@example.com"
            )

    def test_returning_user_retrieves_existing_guest(self):
        """Returning user gets existing guest record, not new one."""
        from src.tools.auth import verify_cognito_otp

        mock_verify_response = {
            "AuthenticationResult": {
                "IdToken": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJleGlzdGluZy1zdWIiLCJlbWFpbCI6InJldHVybmluZ0BleGFtcGxlLmNvbSJ9.sig",
                "AccessToken": "access-token",
                "RefreshToken": "refresh-token",
                "ExpiresIn": 3600,
            }
        }

        existing_guest = {
            "guest_id": "guest-existing123",
            "email": "returning@example.com",
            "cognito_sub": "existing-sub",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        with (
            patch("src.services.auth_service.boto3.client") as mock_boto,
            patch("src.services.dynamodb.get_dynamodb_service") as mock_db_factory,
        ):
            mock_cognito = MagicMock()
            mock_cognito.respond_to_auth_challenge.return_value = mock_verify_response
            mock_boto.return_value = mock_cognito

            mock_db = MagicMock()
            mock_db.get_guest_by_email.return_value = existing_guest
            mock_db_factory.return_value = mock_db

            result = verify_cognito_otp(
                email="returning@example.com",
                otp_code="123456",
                session_token="valid-session",
                otp_sent_at=datetime.now(timezone.utc).isoformat(),
                attempts=0,
            )

            assert result["success"] is True
            assert result["guest_id"] == "guest-existing123"

            # Should NOT create a new guest
            mock_db.create_guest.assert_not_called()


# === T029: JWT Validation from Payload ===


class TestJWTFromPayload:
    """Tests for receiving JWT via payload (not headers)."""

    def _create_test_jwt(self, payload: dict[str, Any]) -> str:
        """Helper to create a test JWT with given payload."""
        import base64
        import json

        header = {"alg": "RS256", "typ": "JWT"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        return f"{header_b64}.{payload_b64}.fake-signature"

    def test_jwt_can_be_decoded_from_payload(self):
        """Backend can decode JWT received in payload."""
        from src.services.auth_service import AuthService

        payload = {"sub": "test-sub-uuid", "email": "test@example.com", "exp": 9999999999}
        test_jwt = self._create_test_jwt(payload)

        # Use AuthService to decode
        auth_service = AuthService("test-pool", "test-client")
        decoded = auth_service.decode_id_token(test_jwt)

        assert decoded["sub"] == "test-sub-uuid"
        assert decoded["email"] == "test@example.com"

    def test_extract_cognito_sub_returns_sub_claim(self):
        """JWT utility extracts cognito_sub correctly."""
        from src.utils.jwt import extract_cognito_sub

        test_cognito_sub = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        payload = {"sub": test_cognito_sub, "email": "user@example.com", "exp": 9999999999}
        test_jwt = self._create_test_jwt(payload)

        result = extract_cognito_sub(test_jwt)

        assert result == test_cognito_sub

    def test_extract_cognito_sub_returns_none_for_invalid_jwt(self):
        """JWT utility returns None for invalid tokens."""
        from src.utils.jwt import extract_cognito_sub

        # Test various invalid inputs
        assert extract_cognito_sub(None) is None
        assert extract_cognito_sub("") is None
        assert extract_cognito_sub("not-a-jwt") is None
        assert extract_cognito_sub("only.two.parts.extra") is None
        assert extract_cognito_sub("invalid.base64.here") is None

    def test_extract_cognito_sub_returns_none_for_missing_sub(self):
        """JWT utility returns None when sub claim is missing."""
        from src.utils.jwt import extract_cognito_sub

        payload = {"email": "user@example.com", "exp": 9999999999}  # No sub claim
        test_jwt = self._create_test_jwt(payload)

        result = extract_cognito_sub(test_jwt)

        assert result is None

    def test_get_my_reservations_with_valid_jwt(self):
        """get_my_reservations tool returns user's reservations with valid JWT."""
        from src.tools.reservations import get_my_reservations
        from src.services.dynamodb import reset_dynamodb_service

        reset_dynamodb_service()

        test_cognito_sub = "test-user-cognito-sub-123"
        test_guest_id = "guest-abc123"
        payload = {"sub": test_cognito_sub, "email": "user@example.com", "exp": 9999999999}
        test_jwt = self._create_test_jwt(payload)

        mock_guest = {
            "guest_id": test_guest_id,
            "email": "user@example.com",
            "cognito_sub": test_cognito_sub,
        }

        mock_reservations = [
            {
                "reservation_id": "RES-2025-ABC123",
                "guest_id": test_guest_id,
                "check_in": "2025-03-15",
                "check_out": "2025-03-20",
                "nights": 5,
                "num_adults": 2,
                "num_children": 1,
                "total_amount": 75000,  # €750
                "status": "confirmed",
                "payment_status": "paid",
            },
            {
                "reservation_id": "RES-2025-DEF456",
                "guest_id": test_guest_id,
                "check_in": "2025-07-01",
                "check_out": "2025-07-08",
                "nights": 7,
                "num_adults": 2,
                "num_children": 0,
                "total_amount": 98000,  # €980
                "status": "pending",
                "payment_status": "pending",
            },
        ]

        # Patch where get_dynamodb_service is used (imported in reservations module)
        with patch("src.tools.reservations.get_dynamodb_service") as mock_db_factory:
            mock_db = MagicMock()
            mock_db.get_guest_by_cognito_sub.return_value = mock_guest
            mock_db.get_reservations_by_guest_id.return_value = mock_reservations
            mock_db_factory.return_value = mock_db

            result = get_my_reservations(auth_token=test_jwt)

            assert result["status"] == "success"
            assert result["count"] == 2
            assert len(result["reservations"]) == 2

            # Verify first reservation
            res1 = result["reservations"][0]
            assert res1["reservation_id"] == "RES-2025-ABC123"
            assert res1["total_amount_eur"] == 750.0
            assert res1["status"] == "confirmed"

            # Verify DynamoDB calls
            mock_db.get_guest_by_cognito_sub.assert_called_once_with(test_cognito_sub)
            mock_db.get_reservations_by_guest_id.assert_called_once_with(test_guest_id)

        reset_dynamodb_service()

    def test_get_my_reservations_without_jwt_returns_error(self):
        """get_my_reservations tool returns error when no JWT provided."""
        from src.tools.reservations import get_my_reservations

        result = get_my_reservations(auth_token=None)

        assert result["success"] is False
        assert result["error_code"] == "ERR_004"  # VERIFICATION_REQUIRED
        assert "Authentication required" in result["details"]["reason"]

    def test_get_my_reservations_with_invalid_jwt_returns_error(self):
        """get_my_reservations tool returns error for invalid JWT."""
        from src.tools.reservations import get_my_reservations

        result = get_my_reservations(auth_token="invalid.jwt.token")

        assert result["success"] is False
        assert result["error_code"] == "ERR_004"  # VERIFICATION_REQUIRED

    def test_get_my_reservations_new_user_no_reservations(self):
        """get_my_reservations returns empty list for authenticated user with no reservations."""
        from src.tools.reservations import get_my_reservations
        from src.services.dynamodb import reset_dynamodb_service

        reset_dynamodb_service()

        test_cognito_sub = "new-user-cognito-sub"
        payload = {"sub": test_cognito_sub, "email": "newuser@example.com", "exp": 9999999999}
        test_jwt = self._create_test_jwt(payload)

        # Patch where get_dynamodb_service is used (imported in reservations module)
        with patch("src.tools.reservations.get_dynamodb_service") as mock_db_factory:
            mock_db = MagicMock()
            mock_db.get_guest_by_cognito_sub.return_value = None  # No guest record
            mock_db_factory.return_value = mock_db

            result = get_my_reservations(auth_token=test_jwt)

            assert result["status"] == "success"
            assert result["count"] == 0
            assert result["reservations"] == []
            assert "don't have any reservations" in result["message"]

        reset_dynamodb_service()
