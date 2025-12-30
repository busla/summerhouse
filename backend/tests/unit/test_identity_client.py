"""Unit tests for AgentCore Identity client (T051).

Tests the IdentityClient wrapper for workload token operations.
Per TDD gate T051z: tests written BEFORE implementation.

Tests cover:
- get_workload_token() returns WorkloadToken (anonymous mode)
- Token caching: cached token returned if not expired
- Token refresh: new token fetched when is_expired=True
- get_workload_token(user_id=X) returns user-delegated token
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.models.auth import WorkloadToken


class TestGetWorkloadToken:
    """Tests for getting workload access tokens."""

    def test_get_workload_token_returns_workload_token_model(
        self,
        mock_agentcore_identity_client: MagicMock,
    ) -> None:
        """Should return WorkloadToken model on successful anonymous token fetch."""
        from src.services.identity_client import IdentityClient

        # Given: AgentCore Identity SDK returns a valid token response
        # (mock is configured in fixture)

        # When: Getting workload token (anonymous mode)
        with patch(
            "src.services.identity_client.AgentCoreIdentityClient",
            return_value=mock_agentcore_identity_client,
        ):
            client = IdentityClient(workload_name="cognito")
            token = client.get_workload_token()

        # Then: Should return WorkloadToken model with correct fields
        assert isinstance(token, WorkloadToken)
        assert token.access_token == "mock-workload-access-token"
        assert token.token_type == "Bearer"
        assert token.workload_name == "cognito"
        assert token.user_id is None  # Anonymous mode
        assert token.expires_at is not None

    def test_get_workload_token_caches_token(
        self,
        mock_agentcore_identity_client: MagicMock,
    ) -> None:
        """Should return cached token if not expired."""
        from src.services.identity_client import IdentityClient

        # Given: First call returns a valid token
        with patch(
            "src.services.identity_client.AgentCoreIdentityClient",
            return_value=mock_agentcore_identity_client,
        ):
            client = IdentityClient(workload_name="cognito")

            # When: Getting token twice
            token1 = client.get_workload_token()
            token2 = client.get_workload_token()

        # Then: Should return same cached token (SDK called only once)
        assert token1.access_token == token2.access_token
        # SDK's get_workload_access_token called only once due to caching
        assert mock_agentcore_identity_client.get_workload_access_token.call_count == 1

    def test_get_workload_token_refreshes_expired_token(
        self,
        mock_agentcore_identity_client: MagicMock,
    ) -> None:
        """Should fetch new token when cached token is expired."""
        from src.services.identity_client import IdentityClient

        # Given: First call returns an already-expired token
        expired_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        mock_agentcore_identity_client.get_workload_access_token.return_value = {
            "accessToken": "mock-expired-token",
            "tokenType": "Bearer",
            "expiresAt": expired_time.isoformat(),
        }

        with patch(
            "src.services.identity_client.AgentCoreIdentityClient",
            return_value=mock_agentcore_identity_client,
        ):
            client = IdentityClient(workload_name="cognito")

            # First call - gets expired token
            token1 = client.get_workload_token()
            assert token1.is_expired  # Verify it's expired

            # Reset mock to return fresh token
            fresh_time = datetime.now(timezone.utc) + timedelta(hours=1)
            mock_agentcore_identity_client.get_workload_access_token.return_value = {
                "accessToken": "mock-fresh-token",
                "tokenType": "Bearer",
                "expiresAt": fresh_time.isoformat(),
            }

            # When: Getting token again
            token2 = client.get_workload_token()

        # Then: Should have fetched a new token
        assert token2.access_token == "mock-fresh-token"
        assert not token2.is_expired
        assert mock_agentcore_identity_client.get_workload_access_token.call_count == 2

    def test_get_workload_token_with_user_id_returns_user_delegated_token(
        self,
        mock_agentcore_identity_client: MagicMock,
    ) -> None:
        """Should return user-delegated token when user_id is provided."""
        from src.services.identity_client import IdentityClient

        # Given: AgentCore returns user-delegated token
        mock_agentcore_identity_client.get_workload_access_token.return_value = {
            "accessToken": "mock-user-delegated-token",
            "tokenType": "Bearer",
            "expiresAt": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        }

        user_id = "guest-123-abc"

        # When: Getting workload token with user_id
        with patch(
            "src.services.identity_client.AgentCoreIdentityClient",
            return_value=mock_agentcore_identity_client,
        ):
            client = IdentityClient(workload_name="cognito")
            token = client.get_workload_token(user_id=user_id)

        # Then: Should return token with user_id set
        assert isinstance(token, WorkloadToken)
        assert token.access_token == "mock-user-delegated-token"
        assert token.user_id == user_id

        # Verify SDK was called with user_id
        mock_agentcore_identity_client.get_workload_access_token.assert_called_with(
            workload_name="cognito",
            user_id=user_id,
        )

    def test_get_workload_token_with_user_token_returns_jwt_delegated_token(
        self,
        mock_agentcore_identity_client: MagicMock,
    ) -> None:
        """Should return token when user_token (JWT) is provided."""
        from src.services.identity_client import IdentityClient

        # Given: AgentCore returns JWT-delegated token
        mock_agentcore_identity_client.get_workload_access_token.return_value = {
            "accessToken": "mock-jwt-delegated-token",
            "tokenType": "Bearer",
            "expiresAt": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        }

        user_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.mock.signature"

        # When: Getting workload token with user_token
        with patch(
            "src.services.identity_client.AgentCoreIdentityClient",
            return_value=mock_agentcore_identity_client,
        ):
            client = IdentityClient(workload_name="cognito")
            token = client.get_workload_token(user_token=user_token)

        # Then: Should return valid token
        assert isinstance(token, WorkloadToken)
        assert token.access_token == "mock-jwt-delegated-token"

        # Verify SDK was called with user_token
        mock_agentcore_identity_client.get_workload_access_token.assert_called_with(
            workload_name="cognito",
            user_token=user_token,
        )


class TestGetWorkloadTokenErrorHandling:
    """Tests for error handling in workload token operations."""

    def test_get_workload_token_raises_on_sdk_error(
        self,
        mock_agentcore_identity_client: MagicMock,
    ) -> None:
        """Should raise exception when AgentCore SDK fails."""
        from botocore.exceptions import ClientError

        from src.services.identity_client import IdentityClient

        # Given: SDK raises a client error
        mock_agentcore_identity_client.get_workload_access_token.side_effect = (
            ClientError(
                {
                    "Error": {
                        "Code": "AccessDeniedException",
                        "Message": "Access denied",
                    }
                },
                "GetWorkloadAccessToken",
            )
        )

        # When/Then: Should propagate the error
        with patch(
            "src.services.identity_client.AgentCoreIdentityClient",
            return_value=mock_agentcore_identity_client,
        ):
            client = IdentityClient(workload_name="cognito")
            with pytest.raises(ClientError):
                client.get_workload_token()


# === Fixtures ===


@pytest.fixture
def mock_agentcore_identity_client() -> MagicMock:
    """Mock AgentCore Identity SDK client.

    Returns realistic responses for workload token operations.
    """
    mock_client = MagicMock()

    # Default: return valid anonymous token
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_client.get_workload_access_token.return_value = {
        "accessToken": "mock-workload-access-token",
        "tokenType": "Bearer",
        "expiresAt": expires_at.isoformat(),
    }

    return mock_client
