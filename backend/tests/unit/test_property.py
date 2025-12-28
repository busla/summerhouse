"""Unit tests for property details tool (T085).

Tests the get_property_details functionality that provides
apartment information to guests.
"""

import pytest

from src.models import Address, Coordinates, Photo, PhotoCategory, Property
from src.tools.property import (
    get_property_details,
    load_property_data_from_dict,
    set_property_data_store,
)


@pytest.fixture(autouse=True)
def reset_property_data() -> None:
    """Reset property data before each test."""
    set_property_data_store(None)


@pytest.fixture
def sample_property_data() -> dict:
    """Create sample property data."""
    return {
        "property_id": "summerhouse-quesada",
        "name": "Summerhouse Quesada",
        "description": "Beautiful vacation apartment in Costa Blanca",
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
        "amenities": [
            "Free WiFi",
            "Air Conditioning",
            "Community Pool",
            "Private Parking",
        ],
        "photos": [
            {
                "id": "living-1",
                "url": "https://cdn.example.com/living-room.jpg",
                "caption": "Spacious living room",
                "category": "living_room",
                "display_order": 1,
            },
            {
                "id": "bedroom-1",
                "url": "https://cdn.example.com/bedroom.jpg",
                "caption": "Master bedroom",
                "category": "bedroom",
                "display_order": 2,
            },
        ],
        "check_in_time": "15:00",
        "check_out_time": "10:00",
        "house_rules": [
            "No smoking",
            "No pets",
            "Quiet hours after 22:00",
        ],
        "highlights": [
            "5 minutes to golf",
            "Community pool",
        ],
    }


class TestPropertyModel:
    """Tests for Property model validation."""

    def test_creates_valid_property(self, sample_property_data: dict) -> None:
        """Should create a valid Property instance."""
        load_property_data_from_dict(sample_property_data)
        from src.tools.property import get_property_data_store

        prop = get_property_data_store()

        assert prop is not None
        assert prop.name == "Summerhouse Quesada"
        assert prop.bedrooms == 2
        assert prop.max_guests == 4

    def test_property_has_address(self, sample_property_data: dict) -> None:
        """Should include full address details."""
        load_property_data_from_dict(sample_property_data)
        from src.tools.property import get_property_data_store

        prop = get_property_data_store()

        assert prop is not None
        assert prop.address.city == "Ciudad Quesada"
        assert prop.address.country == "Spain"

    def test_property_has_coordinates(self, sample_property_data: dict) -> None:
        """Should include GPS coordinates."""
        load_property_data_from_dict(sample_property_data)
        from src.tools.property import get_property_data_store

        prop = get_property_data_store()

        assert prop is not None
        assert prop.coordinates.latitude == pytest.approx(38.0731, abs=0.001)
        assert prop.coordinates.longitude == pytest.approx(-0.7835, abs=0.001)

    def test_property_has_amenities_list(self, sample_property_data: dict) -> None:
        """Should include list of amenities."""
        load_property_data_from_dict(sample_property_data)
        from src.tools.property import get_property_data_store

        prop = get_property_data_store()

        assert prop is not None
        assert len(prop.amenities) == 4
        assert "Free WiFi" in prop.amenities
        assert "Community Pool" in prop.amenities


class TestGetPropertyDetails:
    """Tests for get_property_details tool functionality."""

    def test_returns_success_with_property_data(
        self, sample_property_data: dict
    ) -> None:
        """Should return success status with property details."""
        load_property_data_from_dict(sample_property_data)

        result = get_property_details()

        assert result["status"] == "success"
        assert "property" in result

    def test_returns_property_name(self, sample_property_data: dict) -> None:
        """Should include property name in response."""
        load_property_data_from_dict(sample_property_data)

        result = get_property_details()

        assert result["property"]["name"] == "Summerhouse Quesada"

    def test_returns_bedroom_count(self, sample_property_data: dict) -> None:
        """Should include number of bedrooms."""
        load_property_data_from_dict(sample_property_data)

        result = get_property_details()

        assert result["property"]["bedrooms"] == 2

    def test_returns_bathroom_count(self, sample_property_data: dict) -> None:
        """Should include number of bathrooms."""
        load_property_data_from_dict(sample_property_data)

        result = get_property_details()

        assert result["property"]["bathrooms"] == 1

    def test_returns_max_guests(self, sample_property_data: dict) -> None:
        """Should include maximum guest capacity."""
        load_property_data_from_dict(sample_property_data)

        result = get_property_details()

        assert result["property"]["max_guests"] == 4

    def test_returns_amenities(self, sample_property_data: dict) -> None:
        """Should include list of amenities."""
        load_property_data_from_dict(sample_property_data)

        result = get_property_details()

        amenities = result["property"]["amenities"]
        assert len(amenities) == 4
        assert "Free WiFi" in amenities

    def test_returns_check_in_out_times(self, sample_property_data: dict) -> None:
        """Should include check-in and check-out times."""
        load_property_data_from_dict(sample_property_data)

        result = get_property_details()

        assert result["property"]["check_in_time"] == "15:00"
        assert result["property"]["check_out_time"] == "10:00"

    def test_returns_house_rules(self, sample_property_data: dict) -> None:
        """Should include house rules."""
        load_property_data_from_dict(sample_property_data)

        result = get_property_details()

        rules = result["property"]["house_rules"]
        assert len(rules) == 3
        assert "No smoking" in rules

    def test_returns_address(self, sample_property_data: dict) -> None:
        """Should include full address."""
        load_property_data_from_dict(sample_property_data)

        result = get_property_details()

        address = result["property"]["address"]
        assert address["city"] == "Ciudad Quesada"
        assert address["country"] == "Spain"

    def test_returns_coordinates(self, sample_property_data: dict) -> None:
        """Should include GPS coordinates."""
        load_property_data_from_dict(sample_property_data)

        result = get_property_details()

        coords = result["property"]["coordinates"]
        assert coords["latitude"] == pytest.approx(38.0731, abs=0.001)

    def test_returns_photo_count(self, sample_property_data: dict) -> None:
        """Should include photo count."""
        load_property_data_from_dict(sample_property_data)

        result = get_property_details()

        assert result["property"]["photo_count"] == 2

    def test_returns_highlights(self, sample_property_data: dict) -> None:
        """Should include property highlights."""
        load_property_data_from_dict(sample_property_data)

        result = get_property_details()

        highlights = result["property"]["highlights"]
        assert "5 minutes to golf" in highlights

    def test_returns_error_when_no_data(self) -> None:
        """Should return error when property data not loaded."""
        # Data is reset by fixture, so no data is available
        result = get_property_details()

        assert result["status"] == "error"
        assert "not available" in result["message"]

    def test_returns_description(self, sample_property_data: dict) -> None:
        """Should include property description."""
        load_property_data_from_dict(sample_property_data)

        result = get_property_details()

        assert "Beautiful vacation apartment" in result["property"]["description"]


class TestPropertyScenarios:
    """Scenario-based tests for property details use cases."""

    def test_guest_asks_about_amenities(self, sample_property_data: dict) -> None:
        """Guest asking 'What amenities do you have?' should get amenities list."""
        load_property_data_from_dict(sample_property_data)

        result = get_property_details()

        assert result["status"] == "success"
        assert len(result["property"]["amenities"]) > 0

    def test_guest_asks_about_capacity(self, sample_property_data: dict) -> None:
        """Guest asking 'How many people can stay?' should get max_guests."""
        load_property_data_from_dict(sample_property_data)

        result = get_property_details()

        assert result["property"]["max_guests"] == 4

    def test_guest_asks_about_check_in(self, sample_property_data: dict) -> None:
        """Guest asking 'What time is check-in?' should get check_in_time."""
        load_property_data_from_dict(sample_property_data)

        result = get_property_details()

        assert result["property"]["check_in_time"] == "15:00"

    def test_guest_asks_about_location(self, sample_property_data: dict) -> None:
        """Guest asking 'Where is it located?' should get address."""
        load_property_data_from_dict(sample_property_data)

        result = get_property_details()

        assert result["property"]["address"]["city"] == "Ciudad Quesada"
        assert result["property"]["address"]["region"] == "Alicante"
