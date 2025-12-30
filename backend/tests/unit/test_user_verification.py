"""Unit tests for OAuth2 user verification (T062).

Tests the user identity verification during OAuth2 callback processing.
Per TDD gate T061z: tests written BEFORE implementation.

Tests cover:
- Concurrent sessions are correctly isolated by session_id
- CompleteResourceTokenAuth with mismatched user_identifier returns error
- Callback correctly correlates session_id to guest_email

Key insight: AgentCore handles OAuth2 state/PKCE internally. This module
verifies user identity: session_id → guest_email → CompleteResourceTokenAuth.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.models.oauth2_session import OAuth2Session, OAuth2SessionStatus


class TestConcurrentSessionIsolation:
    """Tests for concurrent OAuth2 session handling."""

    def test_concurrent_sessions_isolated_by_session_id(
        self,
        mock_dynamodb_table: MagicMock,
    ) -> None:
        """Should retrieve correct session when multiple exist."""
        from src.services.dynamodb import DynamoDBService

        # Given: Two concurrent sessions for different users
        session_alice = {
            "session_id": "session-alice",
            "conversation_id": "conv-alice",
            "guest_email": "alice@example.com",
            "status": "pending",
            "created_at": "2025-01-01T12:00:00+00:00",
            "expires_at": 1735732800,
        }
        session_bob = {
            "session_id": "session-bob",
            "conversation_id": "conv-bob",
            "guest_email": "bob@example.com",
            "status": "pending",
            "created_at": "2025-01-01T12:00:00+00:00",
            "expires_at": 1735732800,
        }

        def mock_get_item(Key: dict) -> dict:
            """Return correct session based on session_id."""
            session_id = Key.get("session_id")
            if session_id == "session-alice":
                return {"Item": session_alice}
            elif session_id == "session-bob":
                return {"Item": session_bob}
            return {}

        mock_dynamodb_table.get_item.side_effect = mock_get_item

        # When: Retrieving each session
        with patch.object(DynamoDBService, "_get_table", return_value=mock_dynamodb_table):
            service = DynamoDBService()
            result_alice = service.get_oauth2_session("session-alice")
            result_bob = service.get_oauth2_session("session-bob")

        # Then: Each should return correct user's session
        assert result_alice is not None
        assert result_alice.guest_email == "alice@example.com"

        assert result_bob is not None
        assert result_bob.guest_email == "bob@example.com"


class TestCompleteResourceTokenAuth:
    """Tests for CompleteResourceTokenAuth user verification."""

    def test_complete_oauth2_with_matching_user_succeeds(
        self,
        mock_identity_client: MagicMock,
        mock_dynamodb_service: MagicMock,
    ) -> None:
        """Should complete auth when user_identifier matches session guest_email."""
        from src.services.identity_client import IdentityClient

        # Given: Session exists with guest_email
        session_id = "session-match"
        guest_email = "matching@example.com"

        mock_dynamodb_service.get_oauth2_session.return_value = OAuth2Session(
            session_id=session_id,
            conversation_id="conv-123",
            guest_email=guest_email,
            status=OAuth2SessionStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            expires_at=int(datetime.now(timezone.utc).timestamp()) + 600,
        )

        # AgentCore SDK returns success
        mock_identity_client.complete_resource_token_auth.return_value = {
            "success": True,
            "resourceToken": "token-xyz",
        }

        # When: Completing OAuth2 with matching email
        with patch(
            "src.services.identity_client.AgentCoreIdentityClient",
            return_value=mock_identity_client,
        ):
            with patch(
                "src.services.identity_client.get_dynamodb_service",
                return_value=mock_dynamodb_service,
            ):
                client = IdentityClient(workload_name="cognito")
                result = client.complete_oauth2(session_id, guest_email)

        # Then: Should succeed and update status to COMPLETED
        assert result.success is True
        mock_dynamodb_service.update_oauth2_session_status.assert_called_once_with(
            session_id, OAuth2SessionStatus.COMPLETED
        )

    def test_complete_oauth2_with_mismatched_user_fails(
        self,
        mock_identity_client: MagicMock,
        mock_dynamodb_service: MagicMock,
    ) -> None:
        """Should fail when user_identifier doesn't match session guest_email."""
        from src.services.identity_client import IdentityClient

        # Given: Session exists with different guest_email
        session_id = "session-mismatch"
        session_email = "original@example.com"
        wrong_email = "imposter@example.com"

        mock_dynamodb_service.get_oauth2_session.return_value = OAuth2Session(
            session_id=session_id,
            conversation_id="conv-123",
            guest_email=session_email,
            status=OAuth2SessionStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            expires_at=int(datetime.now(timezone.utc).timestamp()) + 600,
        )

        # When: Completing OAuth2 with wrong email
        with patch(
            "src.services.identity_client.AgentCoreIdentityClient",
            return_value=mock_identity_client,
        ):
            with patch(
                "src.services.identity_client.get_dynamodb_service",
                return_value=mock_dynamodb_service,
            ):
                client = IdentityClient(workload_name="cognito")
                result = client.complete_oauth2(session_id, wrong_email)

        # Then: Should fail with USER_MISMATCH error
        assert result.success is False
        assert result.error_code == "USER_MISMATCH"

        # Should update status to FAILED
        mock_dynamodb_service.update_oauth2_session_status.assert_called_once_with(
            session_id, OAuth2SessionStatus.FAILED
        )

    def test_complete_oauth2_with_nonexistent_session_fails(
        self,
        mock_identity_client: MagicMock,
        mock_dynamodb_service: MagicMock,
    ) -> None:
        """Should fail when session_id doesn't exist."""
        from src.services.identity_client import IdentityClient

        # Given: Session doesn't exist
        mock_dynamodb_service.get_oauth2_session.return_value = None

        # When: Completing OAuth2 with unknown session
        with patch(
            "src.services.identity_client.AgentCoreIdentityClient",
            return_value=mock_identity_client,
        ):
            with patch(
                "src.services.identity_client.get_dynamodb_service",
                return_value=mock_dynamodb_service,
            ):
                client = IdentityClient(workload_name="cognito")
                result = client.complete_oauth2("session-nonexistent", "any@example.com")

        # Then: Should fail with SESSION_NOT_FOUND error
        assert result.success is False
        assert result.error_code == "SESSION_NOT_FOUND"


class TestCallbackSessionCorrelation:
    """Tests for callback session_id to guest_email correlation."""

    def test_callback_correlates_session_to_guest_email(
        self,
        mock_dynamodb_table: MagicMock,
    ) -> None:
        """Should correctly correlate session_id to stored guest_email."""
        from src.services.dynamodb import DynamoDBService

        # Given: Session stored with guest_email
        session_id = "session-callback"
        expected_email = "callback@example.com"

        mock_dynamodb_table.get_item.return_value = {
            "Item": {
                "session_id": session_id,
                "conversation_id": "conv-callback",
                "guest_email": expected_email,
                "status": "pending",
                "created_at": "2025-01-01T12:00:00+00:00",
                "expires_at": 1735732800,
            }
        }

        # When: Callback looks up session
        with patch.object(DynamoDBService, "_get_table", return_value=mock_dynamodb_table):
            service = DynamoDBService()
            session = service.get_oauth2_session(session_id)

        # Then: guest_email should be correctly retrieved
        assert session is not None
        assert session.guest_email == expected_email

        # Verify correct key was used
        mock_dynamodb_table.get_item.assert_called_once_with(
            Key={"session_id": session_id}
        )


# === Fixtures ===


@pytest.fixture
def mock_dynamodb_table() -> MagicMock:
    """Mock DynamoDB table for OAuth2 sessions."""
    mock_table = MagicMock()
    mock_table.put_item.return_value = {}
    mock_table.update_item.return_value = {"Attributes": {}}
    return mock_table


@pytest.fixture
def mock_identity_client() -> MagicMock:
    """Mock AgentCore Identity SDK client."""
    mock_client = MagicMock()
    # Default successful complete_resource_token_auth
    mock_client.complete_resource_token_auth.return_value = {
        "success": True,
        "resourceToken": "mock-resource-token",
    }
    return mock_client


@pytest.fixture
def mock_dynamodb_service() -> MagicMock:
    """Mock DynamoDBService for OAuth2 operations."""
    mock_service = MagicMock()
    mock_service.update_oauth2_session_status.return_value = True
    return mock_service
