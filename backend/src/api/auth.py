"""OAuth2 callback endpoint for AgentCore Identity integration.

This module provides the FastAPI router for:
- GET /auth/callback: Receives session_id from AgentCore redirect,
  looks up guest_email, calls CompleteResourceTokenAuth
- GET /auth/session/{session_id}: Check OAuth2 session status

Note: The callback receives session_id from AgentCore's redirect,
NOT the raw OAuth2 authorization code. AgentCore handles code exchange
and PKCE verification internally via its two-stage callback flow.
"""

import os
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, RedirectResponse

from src.services.dynamodb import get_dynamodb_service
from src.services.identity_client import get_identity_client

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
