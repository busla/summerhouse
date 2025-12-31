"""AgentCore Identity client wrapper for workload token operations.

This service wraps the bedrock_agentcore IdentityClient to provide:
1. get_workload_token: Get agent workload access token (anonymous or user-delegated)

Note: OAuth2 completion is handled by the frontend via @aws-sdk/client-bedrock-agentcore's
CompleteResourceTokenAuthCommand. The backend only handles workload tokens for agent operations.
"""

import os
from datetime import datetime, timezone
from typing import Optional

from bedrock_agentcore.services.identity import IdentityClient as AgentCoreIdentityClient

from shared.models.auth import WorkloadToken


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
