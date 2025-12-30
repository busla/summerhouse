"""AgentCore Identity client wrapper for OAuth2 and workload token operations.

This service wraps the bedrock_agentcore IdentityClient to provide:
1. get_workload_token: Get agent workload access token (anonymous or user-delegated)
2. initiate_oauth2: Start 3-legged OAuth2 flow
3. complete_oauth2: Complete OAuth2 after callback
4. get_session: Lookup OAuth2 session by session_id

Key insight: AgentCore handles OAuth2 state/PKCE internally via two-stage callback:
1. Cognito → AgentCore callback (AgentCore exchanges code for tokens)
2. AgentCore → App callback (App receives session_id, calls CompleteResourceTokenAuth)
"""

import os
from datetime import datetime, timezone
from typing import Optional

from bedrock_agentcore.services.identity import IdentityClient as AgentCoreIdentityClient

from src.models.auth import OAuth2CompletionResult, WorkloadToken
from src.models.oauth2_session import OAuth2SessionStatus
from src.services.dynamodb import get_dynamodb_service


class IdentityClient:
    """Wrapper around AgentCore IdentityClient with caching and Pydantic models.

    Provides:
    - Workload access tokens for agent-to-AgentCore API calls
    - Token caching with automatic refresh when expired
    - Conversion to Pydantic models for type safety
    """

    def __init__(
        self,
        workload_name: str,
        region: Optional[str] = None,
    ) -> None:
        """Initialize identity client.

        Args:
            workload_name: Name of the workload identity provider (e.g., "cognito")
            region: AWS region (defaults to AWS_DEFAULT_REGION or AWS_REGION env var)
        """
        self._workload_name = workload_name
        self._region = region or os.environ.get("AWS_DEFAULT_REGION") or os.environ.get(
            "AWS_REGION", "us-east-1"
        )
        self._sdk_client = AgentCoreIdentityClient(region=self._region)

        # Token cache: keyed by (user_id or "anonymous")
        self._token_cache: dict[str, WorkloadToken] = {}

    def get_workload_token(
        self,
        user_token: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> WorkloadToken:
        """Get workload access token for AgentCore API authentication.

        Supports three modes:
        - Anonymous (no user): Agent-level token for general operations
        - JWT-based (user_token): Token delegated via Cognito JWT
        - User ID-based (user_id): Token delegated via user identifier

        Tokens are cached and automatically refreshed when expired (30s buffer).

        Args:
            user_token: Optional Cognito JWT for user delegation
            user_id: Optional user identifier for user delegation

        Returns:
            WorkloadToken with access_token, expiration, and metadata

        Raises:
            ClientError: If AgentCore SDK fails
        """
        # Determine cache key
        cache_key = user_id or "anonymous"
        if user_token:
            # For JWT-based tokens, use a hash or "jwt" prefix
            cache_key = f"jwt:{hash(user_token)}"

        # Check cache first
        cached_token = self._token_cache.get(cache_key)
        if cached_token and not cached_token.is_expired:
            return cached_token

        # Fetch new token from SDK
        if user_token:
            response = self._sdk_client.get_workload_access_token(
                workload_name=self._workload_name,
                user_token=user_token,
            )
        elif user_id:
            response = self._sdk_client.get_workload_access_token(
                workload_name=self._workload_name,
                user_id=user_id,
            )
        else:
            response = self._sdk_client.get_workload_access_token(
                workload_name=self._workload_name,
            )

        # Convert to Pydantic model
        token = self._response_to_token(response, user_id=user_id)

        # Cache and return
        self._token_cache[cache_key] = token
        return token

    def _response_to_token(
        self,
        response: dict,
        user_id: Optional[str] = None,
    ) -> WorkloadToken:
        """Convert SDK response to WorkloadToken model.

        Args:
            response: Raw response from AgentCore SDK
            user_id: Optional user ID to include in token metadata

        Returns:
            WorkloadToken Pydantic model
        """
        # Parse expires_at from ISO format string
        expires_at_str = response.get("expiresAt")
        if isinstance(expires_at_str, str):
            # Handle ISO format with or without timezone
            if expires_at_str.endswith("Z"):
                expires_at_str = expires_at_str[:-1] + "+00:00"
            expires_at = datetime.fromisoformat(expires_at_str)
            # Ensure timezone-aware
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
        else:
            # Fallback: assume 1 hour validity
            from datetime import timedelta

            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        return WorkloadToken(
            access_token=response["accessToken"],
            token_type=response.get("tokenType", "Bearer"),
            expires_at=expires_at,
            workload_name=self._workload_name,
            user_id=user_id,
        )

    def clear_cache(self) -> None:
        """Clear all cached tokens (useful for testing)."""
        self._token_cache.clear()

    def complete_oauth2(
        self,
        session_id: str,
        user_email: str,
    ) -> OAuth2CompletionResult:
        """Complete OAuth2 3LO flow with user identity verification.

        This method:
        1. Looks up the OAuth2 session by session_id
        2. Verifies user_email matches the stored guest_email
        3. Calls AgentCore CompleteResourceTokenAuth if verified
        4. Updates session status to COMPLETED or FAILED

        This is called by the callback handler after receiving session_id from AgentCore.

        Args:
            session_id: Session URI from AgentCore callback
            user_email: Email of the user completing auth (from Cognito)

        Returns:
            OAuth2CompletionResult indicating success or failure with error code
        """
        db = get_dynamodb_service()

        # Step 1: Look up session
        session = db.get_oauth2_session(session_id)
        if session is None:
            return OAuth2CompletionResult(
                success=False,
                error_code="SESSION_NOT_FOUND",
                message=f"OAuth2 session {session_id} not found",
            )

        # Step 2: Verify user identity matches
        if user_email != session.guest_email:
            db.update_oauth2_session_status(session_id, OAuth2SessionStatus.FAILED)
            return OAuth2CompletionResult(
                success=False,
                error_code="USER_MISMATCH",
                message="OAuth2 user does not match session initiator",
            )

        # Step 3: Call AgentCore to complete the auth
        try:
            self._sdk_client.complete_resource_token_auth(
                session_uri=session_id,
                user_identifier=user_email,
            )
        except Exception as e:
            db.update_oauth2_session_status(session_id, OAuth2SessionStatus.FAILED)
            return OAuth2CompletionResult(
                success=False,
                error_code="AGENTCORE_ERROR",
                message=f"AgentCore completion failed: {e}",
            )

        # Step 4: Update session status to completed
        db.update_oauth2_session_status(session_id, OAuth2SessionStatus.COMPLETED)

        return OAuth2CompletionResult(
            success=True,
            message="OAuth2 authentication completed successfully",
        )


# Module-level singleton for performance (similar to DynamoDBService pattern)
_identity_client: Optional[IdentityClient] = None


def get_identity_client(workload_name: str = "cognito") -> IdentityClient:
    """Get shared IdentityClient instance (singleton for performance).

    Args:
        workload_name: Workload identity provider name

    Returns:
        Shared IdentityClient instance
    """
    global _identity_client
    if _identity_client is None:
        _identity_client = IdentityClient(workload_name=workload_name)
    return _identity_client


def reset_identity_client() -> None:
    """Reset singleton (for testing)."""
    global _identity_client
    _identity_client = None
