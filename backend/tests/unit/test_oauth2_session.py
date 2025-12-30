"""Unit tests for OAuth2 session management (T061).

Tests the DynamoDB-based OAuth2 session storage for AgentCore Identity integration.
Per TDD gate T061z: tests written BEFORE implementation.

Tests cover:
- create_oauth2_session stores session with correct fields
- complete_oauth2 with matching user updates status to COMPLETED
- get_oauth2_session returns correct session by session_id

Key insight: AgentCore handles OAuth2 state/PKCE internally.
Application only stores session_id → guest_email mapping for user verification.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.models.oauth2_session import OAuth2Session, OAuth2SessionCreate, OAuth2SessionStatus


class TestCreateOAuth2Session:
    """Tests for creating OAuth2 sessions in DynamoDB."""

    def test_create_oauth2_session_stores_correct_fields(
        self,
        mock_dynamodb_table: MagicMock,
    ) -> None:
        """Should store session with all required fields."""
        from src.services.dynamodb import DynamoDBService

        # Given: Valid session creation data
        session_data = OAuth2SessionCreate(
            session_id="session-abc123",
            conversation_id="conv-xyz789",
            guest_email="guest@example.com",
        )

        # When: Creating an OAuth2 session
        with patch.object(DynamoDBService, "_get_table", return_value=mock_dynamodb_table):
            service = DynamoDBService()
            result = service.create_oauth2_session(session_data)

        # Then: Should return OAuth2Session with correct fields
        assert isinstance(result, OAuth2Session)
        assert result.session_id == "session-abc123"
        assert result.conversation_id == "conv-xyz789"
        assert result.guest_email == "guest@example.com"
        assert result.status == OAuth2SessionStatus.PENDING
        assert result.created_at is not None
        assert result.expires_at > 0  # Unix timestamp for TTL

        # Verify DynamoDB put_item was called
        mock_dynamodb_table.put_item.assert_called_once()

    def test_create_oauth2_session_sets_10_minute_ttl(
        self,
        mock_dynamodb_table: MagicMock,
    ) -> None:
        """Should set expires_at to 10 minutes from creation."""
        from src.services.dynamodb import DynamoDBService

        # Given: Session creation data
        session_data = OAuth2SessionCreate(
            session_id="session-ttl-test",
            conversation_id="conv-123",
            guest_email="ttl@example.com",
        )

        now = datetime.now(timezone.utc)

        # When: Creating session
        with patch.object(DynamoDBService, "_get_table", return_value=mock_dynamodb_table):
            service = DynamoDBService()
            result = service.create_oauth2_session(session_data)

        # Then: expires_at should be ~10 minutes (600 seconds) from now
        expected_expiry = int(now.timestamp()) + 600
        # Allow 5 second tolerance for test execution time
        assert abs(result.expires_at - expected_expiry) < 5


class TestGetOAuth2Session:
    """Tests for retrieving OAuth2 sessions."""

    def test_get_oauth2_session_returns_correct_session(
        self,
        mock_dynamodb_table: MagicMock,
    ) -> None:
        """Should return session when found by session_id."""
        from src.services.dynamodb import DynamoDBService

        # Given: Session exists in DynamoDB
        session_id = "session-existing"
        mock_dynamodb_table.get_item.return_value = {
            "Item": {
                "session_id": session_id,
                "conversation_id": "conv-123",
                "guest_email": "found@example.com",
                "status": "pending",
                "created_at": "2025-01-01T12:00:00+00:00",
                "expires_at": 1735732800,  # Unix timestamp
            }
        }

        # When: Getting session by ID
        with patch.object(DynamoDBService, "_get_table", return_value=mock_dynamodb_table):
            service = DynamoDBService()
            result = service.get_oauth2_session(session_id)

        # Then: Should return correct OAuth2Session
        assert result is not None
        assert result.session_id == session_id
        assert result.guest_email == "found@example.com"
        assert result.status == OAuth2SessionStatus.PENDING

    def test_get_oauth2_session_returns_none_when_not_found(
        self,
        mock_dynamodb_table: MagicMock,
    ) -> None:
        """Should return None when session_id doesn't exist."""
        from src.services.dynamodb import DynamoDBService

        # Given: No session in DynamoDB
        mock_dynamodb_table.get_item.return_value = {}

        # When: Getting non-existent session
        with patch.object(DynamoDBService, "_get_table", return_value=mock_dynamodb_table):
            service = DynamoDBService()
            result = service.get_oauth2_session("session-nonexistent")

        # Then: Should return None
        assert result is None


class TestUpdateOAuth2SessionStatus:
    """Tests for updating OAuth2 session status."""

    def test_update_session_status_to_completed(
        self,
        mock_dynamodb_table: MagicMock,
    ) -> None:
        """Should update status to COMPLETED."""
        from src.services.dynamodb import DynamoDBService

        # Given: Session exists
        session_id = "session-to-complete"
        mock_dynamodb_table.update_item.return_value = {
            "Attributes": {
                "session_id": session_id,
                "status": "completed",
            }
        }

        # When: Updating status to COMPLETED
        with patch.object(DynamoDBService, "_get_table", return_value=mock_dynamodb_table):
            service = DynamoDBService()
            result = service.update_oauth2_session_status(
                session_id, OAuth2SessionStatus.COMPLETED
            )

        # Then: Should return True for successful update
        assert result is True
        mock_dynamodb_table.update_item.assert_called_once()

    def test_update_session_status_to_failed(
        self,
        mock_dynamodb_table: MagicMock,
    ) -> None:
        """Should update status to FAILED when auth fails."""
        from src.services.dynamodb import DynamoDBService

        # Given: Session exists
        session_id = "session-to-fail"
        mock_dynamodb_table.update_item.return_value = {
            "Attributes": {"status": "failed"}
        }

        # When: Updating status to FAILED
        with patch.object(DynamoDBService, "_get_table", return_value=mock_dynamodb_table):
            service = DynamoDBService()
            result = service.update_oauth2_session_status(
                session_id, OAuth2SessionStatus.FAILED
            )

        # Then: Should return True
        assert result is True


# === Fixtures ===


@pytest.fixture
def mock_dynamodb_table() -> MagicMock:
    """Mock DynamoDB table for OAuth2 sessions.

    Returns a mock table with common methods configured.
    """
    mock_table = MagicMock()

    # Default successful put_item
    mock_table.put_item.return_value = {}

    # Default successful update_item
    mock_table.update_item.return_value = {"Attributes": {}}

    return mock_table
