"""Authentication service for Cognito USER_AUTH flow with EMAIL_OTP.

Implements passwordless authentication using Cognito's native EMAIL_OTP challenge.
This service handles:
- Initiating passwordless auth (triggers OTP email)
- Verifying OTP codes
- Guest lookup/creation after successful auth
- JWT token decoding

Per TDD gate T034: Implementation to pass T032 tests.
"""

import base64
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.models.auth import AuthResult, CognitoAuthChallenge, CognitoAuthState
from src.models.errors import BookingError, ErrorCode
from src.models.guest import Guest

# OTP validity period in minutes
OTP_VALIDITY_MINUTES = 5

# Maximum OTP verification attempts
MAX_OTP_ATTEMPTS = 3


class AuthService:
    """Service for Cognito passwordless authentication.

    Uses USER_AUTH flow with EMAIL_OTP challenge for passwordless login.
    Manages the complete auth lifecycle from OTP initiation to guest binding.
    """

    def __init__(self, user_pool_id: str, client_id: str) -> None:
        """Initialize auth service with Cognito configuration.

        Args:
            user_pool_id: Cognito User Pool ID (e.g., 'eu-west-1_ABC123')
            client_id: Cognito App Client ID
        """
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self._cognito_client = boto3.client("cognito-idp")

    def initiate_passwordless_auth(self, email: str) -> CognitoAuthState:
        """Initiate passwordless authentication with EMAIL_OTP.

        Calls Cognito initiate_auth with USER_AUTH flow and EMAIL_OTP preference.
        Cognito sends the OTP to the user's email address.

        If the user doesn't exist in the User Pool, they are automatically created
        via admin_create_user before initiating the auth flow.

        Note: Cognito's prevent_user_existence_errors setting (enabled by default)
        masks whether a user exists. For non-existent users, Cognito still returns
        EMAIL_OTP challenge BUT includes PASSWORD_SRP/PASSWORD in AvailableChallenges
        and uses a generic masked destination (n***@e***). For real passwordless users,
        AvailableChallenges contains only EMAIL_OTP.

        Args:
            email: User's email address (created in User Pool if not exists)

        Returns:
            CognitoAuthState containing session token and challenge info

        Raises:
            ClientError: If Cognito call fails (delivery failure, etc.)
        """
        response = self._initiate_auth_with_email_otp(email)

        # Detect non-existent/ineligible users by checking AvailableChallenges.
        # Real passwordless users only have EMAIL_OTP available.
        # Non-existent users (masked by prevent_user_existence_errors) have
        # PASSWORD_SRP/PASSWORD in AvailableChallenges even with EMAIL_OTP.
        available_challenges = response.get("AvailableChallenges", [])
        has_password_options = any(
            c in available_challenges for c in ("PASSWORD_SRP", "PASSWORD")
        )

        if has_password_options:
            # User doesn't exist or isn't set up for passwordless auth
            # Create the user and retry
            self._create_cognito_user(email)
            response = self._initiate_auth_with_email_otp(email)

            # Verify only EMAIL_OTP is available (confirms user was created properly)
            available_challenges = response.get("AvailableChallenges", [])
            challenge_name = response.get("ChallengeName", "")
            if challenge_name != "EMAIL_OTP" or "PASSWORD_SRP" in available_challenges:
                raise ClientError(
                    {"Error": {"Code": "EMAIL_OTP_NOT_AVAILABLE", "Message": "User created but EMAIL_OTP not available"}},
                    "InitiateAuth",
                )

        return CognitoAuthState(
            session=response["Session"],
            challenge=CognitoAuthChallenge.EMAIL_OTP,
            username=email,
            attempts=0,
            otp_sent_at=datetime.now(timezone.utc),
        )

    def _initiate_auth_with_email_otp(self, email: str) -> dict:
        """Call Cognito initiate_auth with EMAIL_OTP preference.

        Args:
            email: User's email address

        Returns:
            Cognito initiate_auth response dict
        """
        return self._cognito_client.initiate_auth(
            AuthFlow="USER_AUTH",
            ClientId=self.client_id,
            AuthParameters={
                "USERNAME": email,
                "PREFERRED_CHALLENGE": "EMAIL_OTP",
            },
        )

    def _create_cognito_user(self, email: str) -> None:
        """Create a new user in Cognito User Pool.

        Uses admin_create_user for server-side user creation. The Pre Sign Up
        Lambda trigger auto-confirms the user.

        Args:
            email: User's email address (used as username)

        Raises:
            ClientError: If user creation fails
        """
        try:
            self._cognito_client.admin_create_user(
                UserPoolId=self.user_pool_id,
                Username=email,
                UserAttributes=[
                    {"Name": "email", "Value": email},
                    {"Name": "email_verified", "Value": "true"},
                ],
                # Don't send welcome email - we'll send OTP via EMAIL_OTP challenge
                MessageAction="SUPPRESS",
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            # If user already exists (race condition), that's fine
            if error_code != "UsernameExistsException":
                raise

    def verify_otp(self, auth_state: CognitoAuthState, otp: str) -> AuthResult:
        """Verify OTP code and return authentication result.

        Validates OTP hasn't expired and attempts haven't exceeded max,
        then calls Cognito to verify the code.

        Args:
            auth_state: Current auth state from initiate_passwordless_auth
            otp: 6-digit OTP code entered by user

        Returns:
            AuthResult with success=True and cognito_sub on success,
            or success=False with error_code on failure
        """
        result, _ = self.verify_otp_with_state(auth_state, otp)
        return result

    def verify_otp_with_state(
        self, auth_state: CognitoAuthState, otp: str
    ) -> tuple[AuthResult, CognitoAuthState]:
        """Verify OTP and return both result and updated state.

        This variant returns the updated auth state, which is useful for
        tracking attempt counts across multiple verification attempts.

        Args:
            auth_state: Current auth state from initiate_passwordless_auth
            otp: 6-digit OTP code entered by user

        Returns:
            Tuple of (AuthResult, updated CognitoAuthState)
        """
        # Check if max attempts exceeded
        if auth_state.attempts >= MAX_OTP_ATTEMPTS:
            return (
                AuthResult(
                    success=False,
                    error_code=ErrorCode.MAX_ATTEMPTS_EXCEEDED.value,
                    message="Maximum verification attempts exceeded",
                ),
                auth_state,
            )

        # Check if OTP has expired
        if auth_state.otp_sent_at:
            expiry_time = auth_state.otp_sent_at + timedelta(minutes=OTP_VALIDITY_MINUTES)
            if datetime.now(timezone.utc) > expiry_time:
                return (
                    AuthResult(
                        success=False,
                        error_code=ErrorCode.OTP_EXPIRED.value,
                        message="OTP code has expired",
                    ),
                    auth_state,
                )

        # Attempt Cognito verification
        try:
            response = self._cognito_client.respond_to_auth_challenge(
                ClientId=self.client_id,
                ChallengeName="EMAIL_OTP",
                Session=auth_state.session,
                ChallengeResponses={
                    "USERNAME": auth_state.username,
                    "EMAIL_OTP_CODE": otp,
                },
            )

            # Extract cognito_sub from ID token
            id_token = response["AuthenticationResult"]["IdToken"]
            token_claims = self.decode_id_token(id_token)
            cognito_sub = token_claims.get("sub")

            return (
                AuthResult(
                    success=True,
                    cognito_sub=cognito_sub,
                    message="Authentication successful",
                ),
                auth_state,
            )

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")

            # Increment attempts on code mismatch
            updated_state = CognitoAuthState(
                session=auth_state.session,
                challenge=auth_state.challenge,
                username=auth_state.username,
                attempts=auth_state.attempts + 1,
                otp_sent_at=auth_state.otp_sent_at,
            )

            if error_code == "CodeMismatchException":
                return (
                    AuthResult(
                        success=False,
                        error_code=ErrorCode.INVALID_OTP.value,
                        message="Invalid OTP code",
                    ),
                    updated_state,
                )

            # Re-raise other errors
            raise

    def get_or_create_guest(self, email: str, cognito_sub: str) -> Guest:
        """Get existing guest or create new one after authentication.

        Lookup flow:
        1. Query by email (GSI)
        2. If found:
           - If cognito_sub matches or is empty, return/update guest
           - If cognito_sub differs, raise USER_MISMATCH error
        3. If not found, create new guest

        Args:
            email: Verified email address
            cognito_sub: Cognito user sub from ID token

        Returns:
            Guest model (existing or newly created)

        Raises:
            BookingError: If existing guest has different cognito_sub
        """
        from src.services.dynamodb import get_dynamodb_service

        db = get_dynamodb_service()

        # Try to find existing guest by email
        existing_guest = db.get_guest_by_email(email)

        if existing_guest:
            # Check cognito_sub match
            stored_sub = existing_guest.get("cognito_sub")

            if stored_sub and stored_sub != cognito_sub:
                raise BookingError(
                    code=ErrorCode.USER_MISMATCH,
                    details={"email": email},
                )

            # Bind cognito_sub if not already set
            if not stored_sub:
                db.update_guest_cognito_sub(existing_guest["guest_id"], cognito_sub)

            # Build Guest model from existing data
            # Handle legacy records that may be missing timestamps
            # Also parse ISO strings from DynamoDB to datetime objects
            now = datetime.now(timezone.utc)
            created_at = existing_guest.get("created_at", now)
            updated_at = existing_guest.get("updated_at", now)

            # DynamoDB stores datetimes as ISO strings - parse if needed
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)
            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at)

            return Guest(
                guest_id=existing_guest["guest_id"],
                email=existing_guest["email"],
                name=existing_guest.get("full_name") or existing_guest.get("name"),
                cognito_sub=cognito_sub,
                email_verified=True,
                created_at=created_at,
                updated_at=updated_at,
            )

        # Create new guest
        guest_id = f"guest-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        new_guest = Guest(
            guest_id=guest_id,
            email=email,
            cognito_sub=cognito_sub,
            email_verified=True,
            first_verified_at=now,
            created_at=now,
            updated_at=now,
        )

        db.create_guest(new_guest.model_dump(mode="json"))

        return new_guest

    def decode_id_token(self, token: str) -> dict[str, Any]:
        """Decode JWT ID token payload (without verification).

        Note: Token verification is handled by Cognito. This method
        just extracts claims from the payload for internal use.

        Args:
            token: JWT ID token from Cognito

        Returns:
            Dictionary of token claims (sub, email, etc.)
        """
        # JWT format: header.payload.signature
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")

        # Decode payload (with padding fix)
        payload_b64 = parts[1]
        # Add padding if needed
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding

        payload_json = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_json)
