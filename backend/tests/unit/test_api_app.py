"""Tests for the FastAPI application endpoints.

Tests the API layer including message format parsing for AI SDK v6 compatibility.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


async def empty_async_generator():
    """Empty async generator for mocking stream_async."""
    return
    yield  # Makes this an async generator


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from src.api_app import app
    return TestClient(app)


class TestHealthCheck:
    """Tests for the /ping health check endpoint."""

    def test_ping_returns_healthy(self, client: TestClient):
        """Health check should return healthy status."""
        response = client.get("/ping")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Healthy"
        assert data["agent"] == "summerhouse-booking"
        assert "timestamp" in data


class TestInvokeStreamMessageParsing:
    """Tests for message format parsing in /invoke-stream endpoint."""

    def test_ai_sdk_v6_parts_format(self, client: TestClient):
        """Should parse AI SDK v6 format with parts array."""
        # AI SDK v6 sends messages with 'parts' array
        payload = {
            "messages": [
                {
                    "parts": [{"type": "text", "text": "What dates are available?"}],
                    "id": "msg_123",
                    "role": "user"
                }
            ]
        }

        with patch("src.api_app.get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.stream_async = MagicMock(return_value=empty_async_generator())
            mock_get_agent.return_value = mock_agent

            response = client.post("/invoke-stream", json=payload)

            # Should not return 400 error
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]

    def test_ai_sdk_v6_multiple_parts(self, client: TestClient):
        """Should extract text from first text part in parts array."""
        payload = {
            "messages": [
                {
                    "parts": [
                        {"type": "text", "text": "First message"},
                        {"type": "text", "text": "Second message"}
                    ],
                    "id": "msg_123",
                    "role": "user"
                }
            ]
        }

        with patch("src.api_app.get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.stream_async = MagicMock(return_value=empty_async_generator())
            mock_get_agent.return_value = mock_agent

            response = client.post("/invoke-stream", json=payload)
            assert response.status_code == 200

    def test_legacy_content_string_format(self, client: TestClient):
        """Should parse legacy format with content as string."""
        payload = {
            "messages": [
                {
                    "content": "What dates are available?",
                    "role": "user"
                }
            ]
        }

        with patch("src.api_app.get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.stream_async = MagicMock(return_value=empty_async_generator())
            mock_get_agent.return_value = mock_agent

            response = client.post("/invoke-stream", json=payload)
            assert response.status_code == 200

    def test_legacy_content_array_format(self, client: TestClient):
        """Should parse legacy format with content as array of blocks."""
        payload = {
            "messages": [
                {
                    "content": [{"type": "text", "text": "What dates are available?"}],
                    "role": "user"
                }
            ]
        }

        with patch("src.api_app.get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.stream_async = MagicMock(return_value=empty_async_generator())
            mock_get_agent.return_value = mock_agent

            response = client.post("/invoke-stream", json=payload)
            assert response.status_code == 200

    def test_empty_messages_returns_400(self, client: TestClient):
        """Should return 400 when messages array is empty."""
        payload = {"messages": []}

        response = client.post("/invoke-stream", json=payload)

        assert response.status_code == 400
        assert "No user message found" in response.json()["error"]

    def test_no_user_message_returns_400(self, client: TestClient):
        """Should return 400 when no user role message exists."""
        payload = {
            "messages": [
                {
                    "parts": [{"type": "text", "text": "Assistant response"}],
                    "role": "assistant"
                }
            ]
        }

        response = client.post("/invoke-stream", json=payload)

        assert response.status_code == 400
        assert "No user message found" in response.json()["error"]

    def test_empty_text_in_parts_returns_400(self, client: TestClient):
        """Should return 400 when user message has empty text."""
        payload = {
            "messages": [
                {
                    "parts": [{"type": "text", "text": ""}],
                    "role": "user"
                }
            ]
        }

        response = client.post("/invoke-stream", json=payload)

        assert response.status_code == 400

    def test_extracts_last_user_message(self, client: TestClient):
        """Should extract the last user message from conversation."""
        payload = {
            "messages": [
                {
                    "parts": [{"type": "text", "text": "First question"}],
                    "role": "user"
                },
                {
                    "parts": [{"type": "text", "text": "Response"}],
                    "role": "assistant"
                },
                {
                    "parts": [{"type": "text", "text": "Follow-up question"}],
                    "role": "user"
                }
            ]
        }

        with patch("src.api_app.get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.stream_async = MagicMock(return_value=empty_async_generator())
            mock_get_agent.return_value = mock_agent

            response = client.post("/invoke-stream", json=payload)
            assert response.status_code == 200


class TestInvokeStreamResponse:
    """Tests for SSE response format in /invoke-stream endpoint."""

    def test_response_includes_required_headers(self, client: TestClient):
        """Response should include SSE and AI SDK headers."""
        payload = {
            "messages": [
                {
                    "parts": [{"type": "text", "text": "Hello"}],
                    "role": "user"
                }
            ]
        }

        with patch("src.api_app.get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.stream_async = MagicMock(return_value=empty_async_generator())
            mock_get_agent.return_value = mock_agent

            response = client.post("/invoke-stream", json=payload)

            assert response.headers["content-type"].startswith("text/event-stream")
            assert response.headers["cache-control"] == "no-cache"
            assert response.headers["x-vercel-ai-ui-message-stream"] == "v1"

    def test_response_includes_start_and_finish_events(self, client: TestClient):
        """Response should include start and finish SSE events."""
        payload = {
            "messages": [
                {
                    "parts": [{"type": "text", "text": "Hello"}],
                    "role": "user"
                }
            ]
        }

        with patch("src.api_app.get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.stream_async = MagicMock(return_value=empty_async_generator())
            mock_get_agent.return_value = mock_agent

            response = client.post("/invoke-stream", json=payload)
            content = response.text

            assert '"type": "start"' in content
            assert '"type": "text-start"' in content
            assert '"type": "text-end"' in content
            assert '"type": "finish"' in content


class TestResetEndpoint:
    """Tests for the /reset endpoint."""

    def test_reset_returns_success(self, client: TestClient):
        """Reset endpoint should return success status."""
        with patch("src.api_app.reset_agent"):
            response = client.post("/reset")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "reset" in data["message"].lower()
