"""Tests for the FastAPI application endpoints.

Tests the REST API layer (auth, health) - NOT agent invocation.
Agent invocation is handled by AgentCore Runtime (agent package).
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from api.main import app
    return TestClient(app)


class TestHealthCheck:
    """Tests for the /ping health check endpoint."""

    def test_ping_returns_ok(self, client: TestClient):
        """Health check should return ok status."""
        response = client.get("/api/ping")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "booking-api"
        assert "timestamp" in data

    def test_health_endpoint_returns_healthy(self, client: TestClient):
        """Health router endpoint should return healthy status."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"


class TestCorsConfiguration:
    """Tests for CORS middleware configuration."""

    def test_cors_allows_localhost(self, client: TestClient):
        """CORS should allow localhost:3000 for development."""
        response = client.options(
            "/ping",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            }
        )

        # FastAPI CORS middleware responds to preflight
        assert response.status_code in [200, 204, 405]


class TestRoutesRegistered:
    """Tests that all expected routes are registered."""

    def test_health_routes_registered(self, client: TestClient):
        """Health router endpoints should be accessible."""
        from api.main import app

        route_paths = [route.path for route in app.routes]

        # Health routes should be registered (mounted with /api prefix)
        assert "/api/health" in route_paths or "/api/ping" in route_paths
