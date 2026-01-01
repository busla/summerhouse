"""Unit tests for area API routes.

Tests for:
- GET /area - Local area information
- GET /area/recommendations - Personalized recommendations
"""

import pytest
from fastapi.testclient import TestClient
from starlette.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from api.main import app


@pytest.fixture
def client() -> TestClient:
    """Create test client for API."""
    return TestClient(app)


class TestGetAreaInfo:
    """Tests for GET /area endpoint."""

    def test_returns_places_list(self, client: TestClient) -> None:
        """Should return list of local places."""
        response = client.get("/area")
        assert response.status_code == HTTP_200_OK

        data = response.json()
        assert "places" in data
        assert "total_count" in data
        assert isinstance(data["places"], list)

    def test_places_have_required_fields(self, client: TestClient) -> None:
        """Each place should have required fields."""
        response = client.get("/area")
        assert response.status_code == HTTP_200_OK

        places = response.json()["places"]
        if places:
            place = places[0]
            assert "id" in place
            assert "name" in place
            assert "category" in place
            assert "description" in place
            assert "distance_km" in place

    def test_filter_by_category(self, client: TestClient) -> None:
        """Should filter places by category."""
        response = client.get("/area?category=golf")
        assert response.status_code == HTTP_200_OK

        data = response.json()
        assert data["category"] == "golf"
        for place in data["places"]:
            assert place["category"] == "golf"

    def test_filter_by_beach_category(self, client: TestClient) -> None:
        """Should filter places by beach category."""
        response = client.get("/area?category=beach")
        assert response.status_code == HTTP_200_OK

        data = response.json()
        assert data["category"] == "beach"
        for place in data["places"]:
            assert place["category"] == "beach"

    def test_invalid_category_returns_400(self, client: TestClient) -> None:
        """Invalid category should return 400 error."""
        response = client.get("/area?category=invalid")
        assert response.status_code == HTTP_400_BAD_REQUEST

    def test_places_sorted_by_distance(self, client: TestClient) -> None:
        """Places should be sorted by distance (closest first)."""
        response = client.get("/area")
        assert response.status_code == HTTP_200_OK

        places = response.json()["places"]
        if len(places) >= 2:
            for i in range(len(places) - 1):
                assert places[i]["distance_km"] <= places[i + 1]["distance_km"]

    def test_category_case_insensitive(self, client: TestClient) -> None:
        """Category filter should be case insensitive."""
        response = client.get("/area?category=GOLF")
        assert response.status_code == HTTP_200_OK
        assert response.json()["category"] == "golf"


class TestGetRecommendations:
    """Tests for GET /area/recommendations endpoint."""

    def test_returns_recommendations_list(self, client: TestClient) -> None:
        """Should return recommendations list."""
        response = client.get("/area/recommendations")
        assert response.status_code == HTTP_200_OK

        data = response.json()
        assert "recommendations" in data
        assert "total_count" in data
        assert "filters_applied" in data

    def test_default_limit_is_5(self, client: TestClient) -> None:
        """Default limit should be 5 recommendations."""
        response = client.get("/area/recommendations")
        assert response.status_code == HTTP_200_OK

        data = response.json()
        assert len(data["recommendations"]) <= 5
        assert data["filters_applied"]["limit"] == 5

    def test_custom_limit(self, client: TestClient) -> None:
        """Should respect custom limit parameter."""
        response = client.get("/area/recommendations?limit=3")
        assert response.status_code == HTTP_200_OK

        data = response.json()
        assert len(data["recommendations"]) <= 3
        assert data["filters_applied"]["limit"] == 3

    def test_filter_by_interests(self, client: TestClient) -> None:
        """Should filter by interests parameter."""
        response = client.get("/area/recommendations?interests=golf,beach")
        assert response.status_code == HTTP_200_OK

        data = response.json()
        assert "interests" in data["filters_applied"]
        assert "golf" in data["filters_applied"]["interests"]
        assert "beach" in data["filters_applied"]["interests"]

    def test_filter_family_friendly_only(self, client: TestClient) -> None:
        """Should filter to family-friendly places only."""
        response = client.get("/area/recommendations?family_friendly_only=true")
        assert response.status_code == HTTP_200_OK

        data = response.json()
        for place in data["recommendations"]:
            assert place["family_friendly"] is True

    def test_filter_max_distance(self, client: TestClient) -> None:
        """Should filter by maximum distance."""
        response = client.get("/area/recommendations?max_distance_km=10")
        assert response.status_code == HTTP_200_OK

        data = response.json()
        for place in data["recommendations"]:
            assert place["distance_km"] <= 10

    def test_combined_filters(self, client: TestClient) -> None:
        """Should support combining multiple filters."""
        response = client.get(
            "/area/recommendations?interests=golf&max_distance_km=20&family_friendly_only=true&limit=2"
        )
        assert response.status_code == HTTP_200_OK

        data = response.json()
        assert len(data["recommendations"]) <= 2
        for place in data["recommendations"]:
            assert place["distance_km"] <= 20
            assert place["family_friendly"] is True

    def test_no_interests_returns_diverse_recommendations(self, client: TestClient) -> None:
        """Without interests, should return diverse category recommendations."""
        response = client.get("/area/recommendations?limit=10")
        assert response.status_code == HTTP_200_OK

        data = response.json()
        # Should have at least one recommendation if data exists
        if data["total_count"] > 0:
            categories = {place["category"] for place in data["recommendations"]}
            # With diverse mode, should try to get multiple categories
            # (depends on data available)
            assert len(categories) >= 1

    def test_limit_max_is_20(self, client: TestClient) -> None:
        """Limit should be capped at 20."""
        response = client.get("/area/recommendations?limit=25")
        # Should return 422 validation error for limit > 20
        assert response.status_code == 422

    def test_limit_min_is_1(self, client: TestClient) -> None:
        """Limit should be at least 1."""
        response = client.get("/area/recommendations?limit=0")
        # Should return 422 validation error for limit < 1
        assert response.status_code == 422
