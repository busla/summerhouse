"""Authentication tools for Strands booking agent.

This module provides agent tools for Cognito EMAIL_OTP passwordless authentication:
- initiate_cognito_login: Start EMAIL_OTP passwordless flow
- verify_cognito_otp: Complete OTP verification and bind guest

Tools are stateless - auth state (session_token, otp_sent_at, attempts) must be
passed as parameters between tool calls.

Note: OAuth2 3LO flow (@requires_access_token) removed per spec clarification #3.
Agent-initiated EMAIL_OTP is incompatible with user-initiated OAuth2 3LO.
"""

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

from botocore.exceptions import ClientError
from strands import tool

logger = logging.getLogger(__name__)
logger.info("[AUTH MODULE] Loading auth tools module...")

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

    Triggers Cognito to send an 8-digit OTP code to the user's email.
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
            "error_code": "ERR_EMAIL_DELIVERY_FAILED",  # Contract-defined code
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
        otp_code: 8-digit OTP code entered by user
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
    # Validate OTP format (Cognito EMAIL_OTP sends 8-digit codes)
    clean_otp = otp_code.strip()
    if not clean_otp.isdigit() or len(clean_otp) != 8:
        return {
            "success": False,
            "error_code": "INVALID_OTP_FORMAT",
            "message": f"Please enter the 8-digit code from your email. You entered {len(clean_otp)} characters.",
            "attempts": attempts,
        }

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
    result, updated_state = auth_service.verify_otp_with_state(auth_state, clean_otp)

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

        # Return TokenDeliveryEvent format per contracts/tool-responses.md (T022)
        return {
            "event_type": "auth_tokens",
            "success": True,
            "id_token": result.id_token,
            "access_token": result.access_token,
            "refresh_token": result.refresh_token,
            "expires_in": result.expires_in or 3600,
            "guest_id": guest.guest_id,
            "email": email,
            "cognito_sub": guest.cognito_sub,
        }

    except Exception as e:
        return {
            "success": False,
            "error_code": "GUEST_CREATION_FAILED",
            "message": str(e),
        }


# ---------------------------------------------------------------------------
# OAuth2 3LO code removed per spec clarification #3 (T006)
# ---------------------------------------------------------------------------
# The @requires_access_token decorator and get_authenticated_guest function
# were removed because OAuth2 3LO (Three-Legged OAuth) is incompatible with
# agent-initiated EMAIL_OTP authentication.
#
# OAuth2 3LO requires user-initiated auth (frontend calls signIn()).
# EMAIL_OTP is agent-initiated (backend calls AdminInitiateAuth).
#
# For authenticated guest access, use the cognito_sub from verify_cognito_otp
# and pass the JWT via the auth_token payload field per spec clarification #2.
# ---------------------------------------------------------------------------
