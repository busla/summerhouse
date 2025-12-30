"""Authentication tools for Strands booking agent (T036, T065).

This module provides agent tools for Cognito EMAIL_OTP passwordless authentication:
- initiate_cognito_login: Start EMAIL_OTP passwordless flow
- verify_cognito_otp: Complete OTP verification and bind guest
- get_authenticated_guest: Get authenticated guest profile (OAuth2 3LO flow)

Tools are stateless - auth state (session_token, otp_sent_at, attempts) must be
passed as parameters between tool calls.
"""

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

import jwt
from botocore.exceptions import ClientError
from strands import tool

logger = logging.getLogger(__name__)
logger.info("[AUTH MODULE] Loading auth tools module...")

from bedrock_agentcore.identity import requires_access_token

from src.models.auth import CognitoAuthChallenge, CognitoAuthState
from src.models.errors import ErrorCode

# Singleton for auth service (avoids boto3 re-instantiation overhead per CLAUDE.md)
_auth_service_instance: "AuthService | None" = None


def _get_auth_service() -> "AuthService":
    """Get shared AuthService instance (singleton for performance)."""
    global _auth_service_instance
    if _auth_service_instance is None:
        from src.services.auth_service import AuthService

        user_pool_id = os.environ.get("COGNITO_USER_POOL_ID", "")
        client_id = os.environ.get("COGNITO_CLIENT_ID", "")
        _auth_service_instance = AuthService(user_pool_id, client_id)
    return _auth_service_instance


def _reset_auth_service() -> None:
    """Reset singleton for testing."""
    global _auth_service_instance
    _auth_service_instance = None


def _is_valid_email(email: str) -> bool:
    """Basic email format validation."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


@tool
def initiate_cognito_login(email: str) -> dict[str, Any]:
    """Initiate passwordless login with Cognito EMAIL_OTP challenge.

    Triggers Cognito to send a 6-digit OTP code to the user's email.
    Returns session_token needed for verify_cognito_otp.

    Args:
        email: User's email address

    Returns:
        dict with:
        - success: True if OTP sent successfully
        - session_token: Token to pass to verify_cognito_otp
        - challenge: Always "EMAIL_OTP"
        - email: The email address
        - otp_sent_at: ISO timestamp when OTP was sent

        On error:
        - success: False
        - error_code: Error code (e.g., EMAIL_DELIVERY_FAILED)
        - message: Human-readable error message
    """
    logger.info(f"[AUTH] initiate_cognito_login called with email: {email}")

    # Validate email format
    if not _is_valid_email(email):
        logger.warning(f"[AUTH] Invalid email format: {email}")
        return {
            "success": False,
            "error_code": "INVALID_EMAIL",
            "message": "Invalid email format",
        }

    try:
        logger.info("[AUTH] Getting auth service...")
        auth_service = _get_auth_service()
        logger.info(f"[AUTH] Auth service ready. User pool: {auth_service.user_pool_id}, Client: {auth_service.client_id}")
        logger.info(f"[AUTH] Initiating passwordless auth for: {email}")
        auth_state = auth_service.initiate_passwordless_auth(email)
        logger.info(f"[AUTH] Success! Session token received, challenge: {auth_state.challenge.value}")

        return {
            "success": True,
            "session_token": auth_state.session,
            "challenge": auth_state.challenge.value,
            "email": email,
            "otp_sent_at": auth_state.otp_sent_at.isoformat() if auth_state.otp_sent_at else None,
        }

    except ClientError as e:
        # Cognito API errors (user not found, delivery failure, rate limit, etc.)
        error_code = e.response.get("Error", {}).get("Code", "")
        error_msg = e.response.get("Error", {}).get("Message", "Unknown error")
        logger.error(f"[AUTH] Cognito ClientError: {error_code} - {error_msg}")
        return {
            "success": False,
            "error_code": ErrorCode.EMAIL_DELIVERY_FAILED.value,
            "message": f"Cognito error: {error_code} - {error_msg}",
        }

    except Exception as e:
        # Catch boto3 initialization errors (NoRegionError, NoCredentialsError, etc.)
        logger.error(f"[AUTH] Exception: {type(e).__name__}: {str(e)}")
        return {
            "success": False,
            "error_code": "AUTH_SERVICE_ERROR",
            "message": f"Auth service error: {type(e).__name__}: {str(e)}",
        }


@tool
def verify_cognito_otp(
    email: str,
    otp_code: str,
    session_token: str,
    otp_sent_at: str,
    attempts: int = 0,
) -> dict[str, Any]:
    """Verify OTP code and authenticate user.

    Validates the OTP code against Cognito. On success, creates or retrieves
    the guest profile and binds the Cognito sub.

    Args:
        email: User's email address
        otp_code: 6-digit OTP code entered by user
        session_token: Session token from initiate_cognito_login
        otp_sent_at: ISO timestamp when OTP was sent (for expiry check)
        attempts: Number of previous failed attempts (default 0)

    Returns:
        dict with:
        - success: True if OTP verified
        - guest_id: Guest profile ID
        - cognito_sub: Cognito user identifier
        - email: The email address

        On error:
        - success: False
        - error_code: INVALID_OTP, OTP_EXPIRED, or MAX_ATTEMPTS_EXCEEDED
        - message: Human-readable error message
    """
    # Parse otp_sent_at timestamp
    try:
        otp_sent_datetime = datetime.fromisoformat(otp_sent_at)
    except (ValueError, TypeError):
        otp_sent_datetime = datetime.now(timezone.utc)

    # Build auth state from parameters (tools are stateless)
    auth_state = CognitoAuthState(
        session=session_token,
        challenge=CognitoAuthChallenge.EMAIL_OTP,
        username=email,
        attempts=attempts,
        otp_sent_at=otp_sent_datetime,
    )

    auth_service = _get_auth_service()
    result, updated_state = auth_service.verify_otp_with_state(auth_state, otp_code)

    if not result.success:
        return {
            "success": False,
            "error_code": result.error_code,
            "message": result.message,
            "attempts": updated_state.attempts,
        }

    # OTP verified - get or create guest
    try:
        guest = auth_service.get_or_create_guest(email, result.cognito_sub or "")

        return {
            "success": True,
            "guest_id": guest.guest_id,
            "cognito_sub": guest.cognito_sub,
            "email": email,
        }

    except Exception as e:
        return {
            "success": False,
            "error_code": "GUEST_CREATION_FAILED",
            "message": str(e),
        }


# ---------------------------------------------------------------------------
# T065: OAuth2 3LO Flow with @requires_access_token decorator
# ---------------------------------------------------------------------------


def stream_auth_url_to_client(auth_url: str) -> None:
    """Callback function for @requires_access_token decorator.

    Called when the user needs to authenticate via OAuth2.
    The auth_url is streamed to the guest via the agent chat interface.

    The URL will be rendered as a clickable hyperlink within the chat
    message bubble, allowing the guest to authenticate via Cognito.

    Args:
        auth_url: Full authorization URL for Cognito OAuth2 login
    """
    # The Strands agent framework handles streaming this to the chat.
    # The decorator calls this function, and Strands will render the URL
    # as a clickable link in the conversation.
    # No implementation needed here - the decorator uses the callback
    # to know where to send the auth URL.
    pass


# OAuth2 callback URL is configured via environment variable
# This is the URL AgentCore will redirect to after OAuth2 completes
OAUTH2_CALLBACK_URL = os.getenv("OAUTH2_CALLBACK_URL", "")

# Identity provider name configured in AgentCore
IDENTITY_PROVIDER_NAME = os.getenv(
    "AGENTCORE_IDENTITY_PROVIDER_NAME", "CognitoIdentityProvider"
)


@tool
@requires_access_token(
    provider_name=IDENTITY_PROVIDER_NAME,
    scopes=["openid", "email"],
    auth_flow="USER_FEDERATION",
    on_auth_url=stream_auth_url_to_client,
    callback_url=OAUTH2_CALLBACK_URL,
)
def get_authenticated_guest(*, access_token: str) -> dict[str, Any]:
    """Get the authenticated guest's profile using OAuth2 3LO flow.

    If the guest is not authenticated, the @requires_access_token decorator
    automatically triggers the OAuth2 flow:
    1. Generates authorization URL with PKCE
    2. Calls stream_auth_url_to_client to display link to guest
    3. Guest completes Cognito login
    4. OAuth2 callback processes the response
    5. Decorator injects access_token into this function

    The access_token parameter is automatically injected by the decorator
    after successful OAuth2 authentication.

    Returns:
        dict with:
        - success: True if guest profile retrieved
        - guest_id: Guest ID
        - email: Guest email address
        - name: Guest name (if set)
        - email_verified: Email verification status

        On error:
        - success: False
        - error_code: Error code (AUTH_REQUIRED, UNAUTHORIZED, etc.)
        - message: Human-readable error message
    """
    from src.services.dynamodb import get_dynamodb_service

    # Decode access token to get Cognito sub claim
    # Token signature is already verified by AgentCore - just extract claims
    try:
        claims = jwt.decode(access_token, options={"verify_signature": False})
        cognito_sub = claims.get("sub")
        token_email = claims.get("email")
    except jwt.DecodeError:
        return {
            "success": False,
            "error_code": ErrorCode.AUTH_REQUIRED.value,
            "message": "Invalid access token",
        }

    if not cognito_sub:
        return {
            "success": False,
            "error_code": ErrorCode.AUTH_REQUIRED.value,
            "message": "Token missing sub claim",
        }

    # Look up guest by cognito_sub
    db = get_dynamodb_service()
    guest = db.get_guest_by_cognito_sub(cognito_sub)

    if not guest:
        # Try to find by email and bind cognito_sub
        if token_email:
            existing_guest = db.get_guest_by_email(token_email)
            if existing_guest:
                db.update_guest_cognito_sub(existing_guest.guest_id, cognito_sub)
                guest = existing_guest
                guest.cognito_sub = cognito_sub

    if not guest:
        return {
            "success": False,
            "error_code": ErrorCode.UNAUTHORIZED.value,
            "message": "Guest profile not found. Please complete registration first.",
        }

    return {
        "success": True,
        "guest_id": guest.guest_id,
        "email": guest.email,
        "name": guest.name,
        "email_verified": guest.email_verified,
    }
