"""Contract tests for OAuth2 auth API endpoints (T067).

Tests the HTTP contract for OAuth2 callback and session status endpoints.
Per TDD gate T061z: tests written BEFORE implementation.

Tests cover:
- GET /auth/callback with valid session_id returns 302 redirect
- GET /auth/callback with invalid session_id returns 400 error
- GET /auth/callback with error parameter redirects with error message
- GET /auth/session/{session_id} returns session status JSON
- GET /auth/session/{session_id} with unknown ID returns 404

The auth router handles AgentCore's OAuth2 callback (receives session_id, NOT raw code/state).
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.models.oauth2_session import OAuth2Session, OAuth2SessionStatus


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from src.api_app import app

    return TestClient(app)


@pytest.fixture
def mock_dynamodb_service() -> MagicMock:
    """Mock DynamoDBService for auth API tests."""
    mock_service = MagicMock()
    return mock_service


@pytest.fixture
def mock_identity_client() -> MagicMock:
    """Mock IdentityClient for auth API tests."""
    mock_client = MagicMock()
    return mock_client


class TestAuthCallbackEndpoint:
    """Tests for GET /auth/callback endpoint."""

    def test_callback_with_valid_session_returns_redirect(
        self,
        client: TestClient,
        mock_dynamodb_service: MagicMock,
        mock_identity_client: MagicMock,
    ) -> None:
        """Should return 302 redirect on successful callback."""
        # Given: Valid session exists
        session_id = "session-valid-callback"
        mock_dynamodb_service.get_oauth2_session.return_value = OAuth2Session(
            session_id=session_id,
            conversation_id="conv-123",
            guest_email="valid@example.com",
            status=OAuth2SessionStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            expires_at=int(datetime.now(timezone.utc).timestamp()) + 600,
        )

        # Mock successful completion
        mock_identity_client.complete_oauth2.return_value = MagicMock(
            success=True, error_code=None
        )

        # When: Callback endpoint receives session_id
        with patch(
            "src.api.auth.get_dynamodb_service", return_value=mock_dynamodb_service
        ):
            with patch(
                "src.api.auth.get_identity_client", return_value=mock_identity_client
            ):
                response = client.get(
                    f"/auth/callback?session_id={session_id}",
                    follow_redirects=False,
                )

        # Then: Should return 302 redirect to frontend
        assert response.status_code == 302
        assert "Location" in response.headers
        # Redirect should include success status
        assert "status=success" in response.headers["Location"]

    def test_callback_with_invalid_session_returns_400(
        self,
        client: TestClient,
        mock_dynamodb_service: MagicMock,
    ) -> None:
        """Should return 400 when session_id doesn't exist."""
        # Given: Session doesn't exist
        mock_dynamodb_service.get_oauth2_session.return_value = None

        # When: Callback with invalid session_id
        with patch(
            "src.api.auth.get_dynamodb_service", return_value=mock_dynamodb_service
        ):
            response = client.get(
                "/auth/callback?session_id=session-invalid",
                follow_redirects=False,
            )

        # Then: Should return 400 Bad Request
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    def test_callback_with_error_param_redirects_with_error(
        self,
        client: TestClient,
    ) -> None:
        """Should redirect with error message when OAuth2 error received."""
        # Given: OAuth2 error parameters
        error = "access_denied"
        error_description = "User cancelled the request"

        # When: Callback receives error
        response = client.get(
            f"/auth/callback?error={error}&error_description={error_description}",
            follow_redirects=False,
        )

        # Then: Should redirect with error info
        assert response.status_code == 302
        location = response.headers.get("Location", "")
        assert "error=" in location
        assert "access_denied" in location

    def test_callback_missing_session_id_returns_400(
        self,
        client: TestClient,
    ) -> None:
        """Should return 400 when session_id is missing."""
        # When: Callback without session_id
        response = client.get(
            "/auth/callback",
            follow_redirects=False,
        )

        # Then: Should return 400 Bad Request
        assert response.status_code == 400


class TestGetSessionEndpoint:
    """Tests for GET /auth/session/{session_id} endpoint."""

    def test_get_session_returns_status_json(
        self,
        client: TestClient,
        mock_dynamodb_service: MagicMock,
    ) -> None:
        """Should return session status as JSON."""
        # Given: Session exists
        session_id = "session-status-check"
        mock_dynamodb_service.get_oauth2_session.return_value = OAuth2Session(
            session_id=session_id,
            conversation_id="conv-status",
            guest_email="status@example.com",
            status=OAuth2SessionStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            expires_at=int(datetime.now(timezone.utc).timestamp()) + 600,
        )

        # When: Getting session status
        with patch(
            "src.api.auth.get_dynamodb_service", return_value=mock_dynamodb_service
        ):
            response = client.get(f"/auth/session/{session_id}")

        # Then: Should return JSON with status
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["status"] == "completed"

    def test_get_session_unknown_id_returns_404(
        self,
        client: TestClient,
        mock_dynamodb_service: MagicMock,
    ) -> None:
        """Should return 404 when session_id doesn't exist."""
        # Given: Session doesn't exist
        mock_dynamodb_service.get_oauth2_session.return_value = None

        # When: Getting unknown session
        with patch(
            "src.api.auth.get_dynamodb_service", return_value=mock_dynamodb_service
        ):
            response = client.get("/auth/session/session-unknown")

        # Then: Should return 404 Not Found
        assert response.status_code == 404
        data = response.json()
        assert "error" in data or "detail" in data

    def test_get_session_returns_pending_status(
        self,
        client: TestClient,
        mock_dynamodb_service: MagicMock,
    ) -> None:
        """Should return PENDING status when auth in progress."""
        # Given: Session is pending
        session_id = "session-pending"
        mock_dynamodb_service.get_oauth2_session.return_value = OAuth2Session(
            session_id=session_id,
            conversation_id="conv-pending",
            guest_email="pending@example.com",
            status=OAuth2SessionStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            expires_at=int(datetime.now(timezone.utc).timestamp()) + 600,
        )

        # When: Getting session status
        with patch(
            "src.api.auth.get_dynamodb_service", return_value=mock_dynamodb_service
        ):
            response = client.get(f"/auth/session/{session_id}")

        # Then: Should return pending status
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"

    def test_get_session_returns_failed_status(
        self,
        client: TestClient,
        mock_dynamodb_service: MagicMock,
    ) -> None:
        """Should return FAILED status when auth failed."""
        # Given: Session failed
        session_id = "session-failed"
        mock_dynamodb_service.get_oauth2_session.return_value = OAuth2Session(
            session_id=session_id,
            conversation_id="conv-failed",
            guest_email="failed@example.com",
            status=OAuth2SessionStatus.FAILED,
            created_at=datetime.now(timezone.utc),
            expires_at=int(datetime.now(timezone.utc).timestamp()) + 600,
        )

        # When: Getting session status
        with patch(
            "src.api.auth.get_dynamodb_service", return_value=mock_dynamodb_service
        ):
            response = client.get(f"/auth/session/{session_id}")

        # Then: Should return failed status
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
