"""Unit tests for property API routes.

Tests for:
- GET /property - Property details
- GET /property/photos - Property photos with filtering
"""

import pytest
from fastapi.testclient import TestClient
from starlette.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from api.main import app


@pytest.fixture
def client() -> TestClient:
    """Create test client for API."""
    return TestClient(app)


class TestGetPropertyDetails:
    """Tests for GET /property endpoint."""

    def test_returns_property_details(self, client: TestClient) -> None:
        """Should return property details with all fields."""
        response = client.get("/property")
        assert response.status_code == HTTP_200_OK

        data = response.json()
        assert "property" in data
        assert "status" in data

        prop = data["property"]
        assert "name" in prop
        assert "description" in prop
        assert "max_guests" in prop
        assert "bedrooms" in prop
        assert "bathrooms" in prop
        assert "amenities" in prop
        assert "address" in prop

    def test_property_has_address_info(self, client: TestClient) -> None:
        """Property should include address details."""
        response = client.get("/property")
        assert response.status_code == HTTP_200_OK

        address = response.json()["property"]["address"]
        assert "city" in address
        assert "region" in address
        assert "country" in address

    def test_property_max_guests_is_4(self, client: TestClient) -> None:
        """Property max guests should be 4 per spec."""
        response = client.get("/property")
        assert response.status_code == HTTP_200_OK
        assert response.json()["property"]["max_guests"] == 4


class TestGetPropertyPhotos:
    """Tests for GET /property/photos endpoint."""

    def test_returns_photos_list(self, client: TestClient) -> None:
        """Should return list of photos."""
        response = client.get("/property/photos")
        assert response.status_code == HTTP_200_OK

        data = response.json()
        assert "photos" in data
        assert "total_count" in data
        assert isinstance(data["photos"], list)

    def test_photos_have_required_fields(self, client: TestClient) -> None:
        """Each photo should have required fields."""
        response = client.get("/property/photos")
        assert response.status_code == HTTP_200_OK

        photos = response.json()["photos"]
        if photos:  # If any photos exist
            photo = photos[0]
            assert "id" in photo
            assert "url" in photo
            assert "category" in photo
            assert "caption" in photo

    def test_filter_by_category(self, client: TestClient) -> None:
        """Should filter photos by category."""
        response = client.get("/property/photos?category=exterior")
        assert response.status_code == HTTP_200_OK

        data = response.json()
        assert data["category"] == "exterior"
        # All returned photos should be exterior category
        for photo in data["photos"]:
            assert photo["category"] == "exterior"

    def test_invalid_category_returns_400(self, client: TestClient) -> None:
        """Invalid category should return 400 error."""
        response = client.get("/property/photos?category=invalid_category")
        assert response.status_code == HTTP_400_BAD_REQUEST

    def test_limit_parameter(self, client: TestClient) -> None:
        """Limit parameter should cap results."""
        response = client.get("/property/photos?limit=2")
        assert response.status_code == HTTP_200_OK

        photos = response.json()["photos"]
        assert len(photos) <= 2

    def test_limit_with_category(self, client: TestClient) -> None:
        """Limit should work with category filter."""
        response = client.get("/property/photos?category=bedroom&limit=1")
        assert response.status_code == HTTP_200_OK

        data = response.json()
        assert len(data["photos"]) <= 1
        if data["photos"]:
            assert data["photos"][0]["category"] == "bedroom"

    def test_photos_sorted_by_display_order(self, client: TestClient) -> None:
        """Photos should be sorted by display_order."""
        response = client.get("/property/photos")
        assert response.status_code == HTTP_200_OK

        photos = response.json()["photos"]
        if len(photos) >= 2:
            for i in range(len(photos) - 1):
                assert photos[i]["display_order"] <= photos[i + 1]["display_order"]
