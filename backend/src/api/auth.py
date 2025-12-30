"""OAuth2 callback endpoint for AgentCore Identity integration.

This module provides the FastAPI router for:
- GET /auth/callback: Receives session_id from AgentCore redirect,
  looks up guest_email, calls CompleteResourceTokenAuth
- GET /auth/session/{session_id}: Check OAuth2 session status
- POST /auth/refresh: Refresh tokens using refresh_token (T042)

Note: The callback receives session_id from AgentCore's redirect,
NOT the raw OAuth2 authorization code. AgentCore handles code exchange
and PKCE verification internally via its two-stage callback flow.
"""

import logging
import os
from typing import Optional
from urllib.parse import urlencode

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from src.services.dynamodb import get_dynamodb_service
from src.services.identity_client import get_identity_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Frontend redirect URL (configurable via environment)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


@router.get("/callback", response_model=None)
async def oauth2_callback(
    session_id: Optional[str] = Query(None, description="Session ID from AgentCore"),
    error: Optional[str] = Query(None, description="OAuth2 error code"),
    error_description: Optional[str] = Query(None, description="OAuth2 error details"),
):
    """Handle OAuth2 callback from AgentCore.

    AgentCore redirects here after completing the code exchange with Cognito.
    We receive only the session_id (not raw code) and use it to:
    1. Look up the guest_email from our session store
    2. Call CompleteResourceTokenAuth to verify the user
    3. Redirect to frontend with success/error status

    Query params:
        session_id: Session URI from AgentCore (required unless error)
        error: OAuth2 error code if auth failed
        error_description: Human-readable error description
    """
    # Handle OAuth2 error from IdP
    if error:
        redirect_url = f"{FRONTEND_URL}/auth/callback"
        params = {"status": "error", "error": error}
        if error_description:
            params["error_description"] = error_description
        return RedirectResponse(
            url=f"{redirect_url}?{urlencode(params)}", status_code=302
        )

    # Validate session_id presence
    if not session_id:
        return JSONResponse(
            {"error": "Missing session_id parameter"},
            status_code=400,
        )

    # Look up session to get guest_email
    db = get_dynamodb_service()
    session = db.get_oauth2_session(session_id)

    if not session:
        return JSONResponse(
            {"error": "Invalid or expired session"},
            status_code=400,
        )

    # Complete OAuth2 with user verification
    identity_client = get_identity_client()
    result = identity_client.complete_oauth2(session_id, session.guest_email)

    redirect_url = f"{FRONTEND_URL}/auth/callback"

    if result.success:
        params = {"status": "success", "session_id": session_id}
    else:
        params = {
            "status": "error",
            "error": result.error_code or "unknown_error",
        }
        if result.message:
            params["error_description"] = result.message

    return RedirectResponse(url=f"{redirect_url}?{urlencode(params)}", status_code=302)


@router.get("/session/{session_id}", response_model=None)
async def get_session_status(session_id: str):
    """Get OAuth2 session status.

    Used by frontend to poll for auth completion status.

    Args:
        session_id: Session URI to check

    Returns:
        JSON with session_id and status (pending, completed, failed, expired)
    """
    db = get_dynamodb_service()
    session = db.get_oauth2_session(session_id)

    if not session:
        return JSONResponse(
            {"error": "Session not found", "detail": f"Session {session_id} not found"},
            status_code=404,
        )

    return JSONResponse(
        {
            "session_id": session.session_id,
            "status": session.status.value,
        },
        status_code=200,
    )


# === Token Refresh (T042) ===


class RefreshTokenRequest(BaseModel):
    """Request body for token refresh."""

    refresh_token: str


# Cognito client configuration
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID", "")


@router.post("/refresh", response_model=None)
async def refresh_token(request: RefreshTokenRequest):
    """Refresh access and ID tokens using a refresh token.

    T042: Uses Cognito's REFRESH_TOKEN_AUTH flow to exchange an opaque
    refresh_token for new access and ID tokens.

    Args:
        request: RefreshTokenRequest with refresh_token

    Returns:
        JSON with new access_token, id_token, and expires_in on success.
        Error response with 401 on invalid/expired refresh token.
    """
    if not COGNITO_CLIENT_ID:
        logger.error("COGNITO_CLIENT_ID not configured")
        return JSONResponse(
            {"error": "server_configuration_error", "message": "Auth not configured"},
            status_code=500,
        )

    try:
        cognito_client = boto3.client("cognito-idp")

        # Use REFRESH_TOKEN_AUTH flow (Cognito native refresh)
        response = cognito_client.initiate_auth(
            ClientId=COGNITO_CLIENT_ID,
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters={
                "REFRESH_TOKEN": request.refresh_token,
            },
        )

        auth_result = response.get("AuthenticationResult", {})

        # Note: Cognito does NOT return a new refresh_token on refresh
        # The original refresh_token remains valid until it expires (30 days default)
        logger.info("Token refresh successful")

        return JSONResponse(
            {
                "access_token": auth_result["AccessToken"],
                "id_token": auth_result["IdToken"],
                "expires_in": auth_result.get("ExpiresIn", 3600),
            },
            status_code=200,
        )

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_message = e.response.get("Error", {}).get("Message", "")

        logger.warning(
            "Token refresh failed",
            extra={"error_code": error_code, "error": error_message},
        )

        if error_code in ("NotAuthorizedException", "InvalidParameterException"):
            # Invalid or expired refresh token
            return JSONResponse(
                {"error": "invalid_refresh_token", "message": "Refresh token is invalid or expired"},
                status_code=401,
            )

        # Unknown error
        return JSONResponse(
            {"error": "refresh_failed", "message": "Failed to refresh token"},
            status_code=500,
        )
