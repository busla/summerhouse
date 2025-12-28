"""Unit tests for photos tool (T086).

Tests the get_photos functionality that provides apartment
photos to guests with filtering by category.
"""

import pytest

from src.models import PhotoCategory
from src.tools.property import (
    get_photos,
    load_property_data_from_dict,
    set_property_data_store,
)


@pytest.fixture(autouse=True)
def reset_property_data() -> None:
    """Reset property data before each test."""
    set_property_data_store(None)


@pytest.fixture
def sample_property_with_photos() -> dict:
    """Create sample property data with multiple photos."""
    return {
        "property_id": "summerhouse-quesada",
        "name": "Summerhouse Quesada",
        "description": "Beautiful vacation apartment",
        "address": {
            "street": "Calle del Sol 45",
            "city": "Ciudad Quesada",
            "region": "Alicante",
            "country": "Spain",
            "postal_code": "03170",
        },
        "coordinates": {
            "latitude": 38.0731,
            "longitude": -0.7835,
        },
        "bedrooms": 2,
        "bathrooms": 1,
        "max_guests": 4,
        "amenities": ["WiFi"],
        "photos": [
            {
                "id": "exterior-1",
                "url": "https://cdn.example.com/exterior-front.jpg",
                "caption": "Front view of the building",
                "category": "exterior",
                "display_order": 1,
            },
            {
                "id": "living-1",
                "url": "https://cdn.example.com/living-room.jpg",
                "caption": "Spacious living room",
                "category": "living_room",
                "display_order": 2,
            },
            {
                "id": "living-2",
                "url": "https://cdn.example.com/living-dining.jpg",
                "caption": "Living and dining area",
                "category": "living_room",
                "display_order": 3,
            },
            {
                "id": "bedroom-1",
                "url": "https://cdn.example.com/bedroom-master.jpg",
                "caption": "Master bedroom with double bed",
                "category": "bedroom",
                "display_order": 4,
            },
            {
                "id": "bedroom-2",
                "url": "https://cdn.example.com/bedroom-twin.jpg",
                "caption": "Second bedroom with twin beds",
                "category": "bedroom",
                "display_order": 5,
            },
            {
                "id": "bathroom-1",
                "url": "https://cdn.example.com/bathroom.jpg",
                "caption": "Modern bathroom",
                "category": "bathroom",
                "display_order": 6,
            },
            {
                "id": "kitchen-1",
                "url": "https://cdn.example.com/kitchen.jpg",
                "caption": "Fully equipped kitchen",
                "category": "kitchen",
                "display_order": 7,
            },
            {
                "id": "pool-1",
                "url": "https://cdn.example.com/pool.jpg",
                "caption": "Community swimming pool",
                "category": "pool",
                "display_order": 8,
            },
            {
                "id": "terrace-1",
                "url": "https://cdn.example.com/terrace.jpg",
                "caption": "Private terrace",
                "category": "terrace",
                "display_order": 9,
            },
        ],
        "check_in_time": "15:00",
        "check_out_time": "10:00",
        "house_rules": [],
        "highlights": [],
    }


class TestGetPhotos:
    """Tests for get_photos tool functionality."""

    def test_returns_all_photos_when_no_filter(
        self, sample_property_with_photos: dict
    ) -> None:
        """Should return all photos when no category specified."""
        load_property_data_from_dict(sample_property_with_photos)

        result = get_photos()

        assert result["status"] == "success"
        assert result["total_count"] == 9
        assert len(result["photos"]) == 9

    def test_filters_by_bedroom_category(
        self, sample_property_with_photos: dict
    ) -> None:
        """Should return only bedroom photos when filtered."""
        load_property_data_from_dict(sample_property_with_photos)

        result = get_photos(category="bedroom")

        assert result["status"] == "success"
        assert result["total_count"] == 2
        assert all(p["category"] == "bedroom" for p in result["photos"])

    def test_filters_by_living_room_category(
        self, sample_property_with_photos: dict
    ) -> None:
        """Should return only living room photos."""
        load_property_data_from_dict(sample_property_with_photos)

        result = get_photos(category="living_room")

        assert result["status"] == "success"
        assert result["total_count"] == 2
        assert all(p["category"] == "living_room" for p in result["photos"])

    def test_filters_by_pool_category(
        self, sample_property_with_photos: dict
    ) -> None:
        """Should return only pool photos."""
        load_property_data_from_dict(sample_property_with_photos)

        result = get_photos(category="pool")

        assert result["status"] == "success"
        assert result["total_count"] == 1
        assert result["photos"][0]["category"] == "pool"

    def test_filters_by_terrace_category(
        self, sample_property_with_photos: dict
    ) -> None:
        """Should return only terrace photos."""
        load_property_data_from_dict(sample_property_with_photos)

        result = get_photos(category="terrace")

        assert result["status"] == "success"
        assert result["total_count"] == 1
        assert result["photos"][0]["category"] == "terrace"

    def test_returns_sorted_by_display_order(
        self, sample_property_with_photos: dict
    ) -> None:
        """Should return photos sorted by display order."""
        load_property_data_from_dict(sample_property_with_photos)

        result = get_photos()

        # First photo should be exterior (display_order 1)
        assert result["photos"][0]["category"] == "exterior"
        # Last photo should be terrace (display_order 9)
        assert result["photos"][-1]["category"] == "terrace"

    def test_includes_url_in_response(
        self, sample_property_with_photos: dict
    ) -> None:
        """Should include photo URL in each result."""
        load_property_data_from_dict(sample_property_with_photos)

        result = get_photos()

        for photo in result["photos"]:
            assert "url" in photo
            assert photo["url"].startswith("https://")

    def test_includes_caption_in_response(
        self, sample_property_with_photos: dict
    ) -> None:
        """Should include photo caption in each result."""
        load_property_data_from_dict(sample_property_with_photos)

        result = get_photos()

        for photo in result["photos"]:
            assert "caption" in photo
            assert len(photo["caption"]) > 0

    def test_returns_error_for_unknown_category(
        self, sample_property_with_photos: dict
    ) -> None:
        """Should return error for invalid category."""
        load_property_data_from_dict(sample_property_with_photos)

        result = get_photos(category="invalid_category")

        assert result["status"] == "error"
        assert "Unknown category" in result["message"]

    def test_returns_empty_for_category_with_no_photos(
        self, sample_property_with_photos: dict
    ) -> None:
        """Should return empty list when category has no photos."""
        load_property_data_from_dict(sample_property_with_photos)

        result = get_photos(category="garden")  # No garden photos in sample

        assert result["status"] == "success"
        assert result["total_count"] == 0
        assert len(result["photos"]) == 0

    def test_applies_limit(self, sample_property_with_photos: dict) -> None:
        """Should respect limit parameter."""
        load_property_data_from_dict(sample_property_with_photos)

        result = get_photos(limit=3)

        assert result["status"] == "success"
        assert len(result["photos"]) == 3

    def test_limit_with_category_filter(
        self, sample_property_with_photos: dict
    ) -> None:
        """Should apply limit after category filtering."""
        load_property_data_from_dict(sample_property_with_photos)

        result = get_photos(category="bedroom", limit=1)

        assert result["status"] == "success"
        assert len(result["photos"]) == 1
        assert result["photos"][0]["category"] == "bedroom"

    def test_returns_error_when_no_data(self) -> None:
        """Should return error when property data not loaded."""
        result = get_photos()

        assert result["status"] == "error"
        assert "not available" in result["message"]

    def test_includes_helpful_message(
        self, sample_property_with_photos: dict
    ) -> None:
        """Should include a helpful message in response."""
        load_property_data_from_dict(sample_property_with_photos)

        result = get_photos(category="bedroom")

        assert "message" in result
        assert "bedroom" in result["message"].lower()


class TestPhotoCategoryHandling:
    """Tests for photo category enum handling."""

    def test_accepts_category_with_underscores(
        self, sample_property_with_photos: dict
    ) -> None:
        """Should accept category with underscores (living_room)."""
        load_property_data_from_dict(sample_property_with_photos)

        result = get_photos(category="living_room")

        assert result["status"] == "success"
        assert result["total_count"] == 2

    def test_accepts_category_with_spaces(
        self, sample_property_with_photos: dict
    ) -> None:
        """Should accept category with spaces (living room)."""
        load_property_data_from_dict(sample_property_with_photos)

        result = get_photos(category="living room")

        assert result["status"] == "success"
        assert result["total_count"] == 2

    def test_accepts_uppercase_category(
        self, sample_property_with_photos: dict
    ) -> None:
        """Should accept uppercase category."""
        load_property_data_from_dict(sample_property_with_photos)

        result = get_photos(category="BEDROOM")

        assert result["status"] == "success"
        assert result["total_count"] == 2


class TestPhotoScenarios:
    """Scenario-based tests for photo use cases."""

    def test_guest_wants_bedroom_photos(
        self, sample_property_with_photos: dict
    ) -> None:
        """Guest asks 'Show me the bedrooms' should get bedroom photos."""
        load_property_data_from_dict(sample_property_with_photos)

        result = get_photos(category="bedroom")

        assert result["status"] == "success"
        assert result["total_count"] == 2
        # Should include both master and twin bedrooms
        captions = [p["caption"] for p in result["photos"]]
        assert any("master" in c.lower() for c in captions)
        assert any("twin" in c.lower() for c in captions)

    def test_guest_wants_pool_photos(
        self, sample_property_with_photos: dict
    ) -> None:
        """Guest asks 'Is there a pool?' should get pool photos."""
        load_property_data_from_dict(sample_property_with_photos)

        result = get_photos(category="pool")

        assert result["status"] == "success"
        assert result["total_count"] == 1
        assert "pool" in result["photos"][0]["caption"].lower()

    def test_guest_wants_quick_overview(
        self, sample_property_with_photos: dict
    ) -> None:
        """Guest asks 'Show me a few photos' should get limited photos."""
        load_property_data_from_dict(sample_property_with_photos)

        result = get_photos(limit=3)

        assert result["status"] == "success"
        assert len(result["photos"]) == 3
        # First photos should be the most important ones (by display_order)

    def test_guest_wants_all_photos(
        self, sample_property_with_photos: dict
    ) -> None:
        """Guest asks 'Show me all photos' should get all photos."""
        load_property_data_from_dict(sample_property_with_photos)

        result = get_photos()

        assert result["status"] == "success"
        assert result["total_count"] == 9
