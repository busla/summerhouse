"""Property tools for apartment details and photos.

These tools allow the booking agent to provide detailed information
about the Summerhouse vacation rental apartment.
"""

import json
import logging
from pathlib import Path
from typing import Any

from strands import tool

from src.models import (
    Photo,
    PhotoCategory,
    PhotosResponse,
    Property,
    PropertyDetailsResponse,
)

logger = logging.getLogger(__name__)


# In-memory data store for property information
_PROPERTY_DATA: Property | None = None
_DATA_LOADED: bool = False


def get_property_data_store() -> Property | None:
    """Get the current property data store."""
    return _PROPERTY_DATA


def set_property_data_store(data: Property | None) -> None:
    """Set the property data store (for testing or initialization)."""
    global _PROPERTY_DATA, _DATA_LOADED
    _PROPERTY_DATA = data
    # If setting to None, also reset the loaded flag to prevent auto-loading
    if data is None:
        _DATA_LOADED = True  # Prevent auto-loading in tests


def load_property_data_from_dict(data: dict[str, Any]) -> None:
    """Load property data from a dictionary.

    Useful for loading from JSON files or test fixtures.
    """
    global _PROPERTY_DATA

    # Parse photos with category enum conversion
    photos_data = data.get("photos", [])
    photos: list[Photo] = []
    for photo_dict in photos_data:
        photo_dict = photo_dict.copy()
        if isinstance(photo_dict.get("category"), str):
            photo_dict["category"] = PhotoCategory(photo_dict["category"])
        photos.append(Photo(**photo_dict))

    # Build the Property model
    property_data = data.copy()
    property_data["photos"] = photos
    _PROPERTY_DATA = Property(**property_data)


def load_property_data_from_json(json_path: Path | str | None = None) -> Property:
    """Load property data from JSON file.

    Args:
        json_path: Path to JSON file. If None, uses default location.

    Returns:
        The loaded Property model.

    Raises:
        FileNotFoundError: If JSON file doesn't exist.
        json.JSONDecodeError: If JSON is invalid.
    """
    global _DATA_LOADED

    if json_path is None:
        # Default to bundled data file
        json_path = Path(__file__).parent.parent / "data" / "property.json"

    json_path = Path(json_path)

    with open(json_path) as f:
        data = json.load(f)

    property_data = data.get("property", {})
    load_property_data_from_dict(property_data)
    _DATA_LOADED = True

    logger.info(f"Loaded property data from {json_path}")
    return _PROPERTY_DATA  # type: ignore


def ensure_property_data_loaded() -> None:
    """Ensure property data is loaded, loading from default source if needed."""
    global _DATA_LOADED
    if not _DATA_LOADED and _PROPERTY_DATA is None:
        try:
            load_property_data_from_json()
        except FileNotFoundError:
            logger.warning("Property data file not found, starting with empty data")
            _DATA_LOADED = True  # Mark as loaded (empty) to prevent repeated attempts


@tool
def get_property_details() -> dict[str, Any]:
    """Get detailed information about the Summerhouse apartment.

    Use this tool when a guest asks about the apartment, accommodation details,
    amenities, house rules, or any specific property information.

    Returns:
        Dictionary with complete property details including bedrooms, bathrooms,
        amenities, house rules, check-in/out times, and location.
    """
    # Ensure data is loaded
    ensure_property_data_loaded()
    prop = get_property_data_store()

    if prop is None:
        return {
            "status": "error",
            "message": "Property data not available",
        }

    # Build the response
    response = PropertyDetailsResponse(
        property=prop,
        status="success",
        message=f"Details for {prop.name}",
    )

    return {
        "status": response.status,
        "property": {
            "property_id": prop.property_id,
            "name": prop.name,
            "description": prop.description,
            "address": prop.address.model_dump(),
            "coordinates": prop.coordinates.model_dump(),
            "bedrooms": prop.bedrooms,
            "bathrooms": prop.bathrooms,
            "max_guests": prop.max_guests,
            "amenities": prop.amenities,
            "check_in_time": prop.check_in_time,
            "check_out_time": prop.check_out_time,
            "house_rules": prop.house_rules,
            "highlights": prop.highlights,
            "photo_count": len(prop.photos),
        },
        "message": response.message,
    }


@tool
def get_photos(category: str | None = None, limit: int | None = None) -> dict[str, Any]:
    """Get photos of the Summerhouse apartment.

    Use this tool when a guest asks to see photos, images, or pictures of the
    property. You can filter by category like 'bedroom', 'pool', 'terrace', etc.

    Args:
        category: Optional filter - one of: exterior, living_room, bedroom,
                  bathroom, kitchen, terrace, pool, garden, view, other.
                  If not provided, returns photos from all categories.
        limit: Optional maximum number of photos to return. If not provided,
               returns all matching photos.

    Returns:
        Dictionary with list of photo URLs, captions, and categories
    """
    # Ensure data is loaded
    ensure_property_data_loaded()
    prop = get_property_data_store()

    if prop is None:
        return {
            "status": "error",
            "message": "Property data not available",
        }

    # Validate category if provided
    category_enum: PhotoCategory | None = None
    if category:
        category_lower = category.lower().strip().replace(" ", "_")
        try:
            category_enum = PhotoCategory(category_lower)
        except ValueError:
            valid_categories = [c.value for c in PhotoCategory]
            return {
                "status": "error",
                "message": f"Unknown category '{category}'. Valid categories are: {', '.join(valid_categories)}",
            }

    # Filter photos by category if specified
    photos = prop.photos
    if category_enum:
        photos = [p for p in photos if p.category == category_enum]

    # Sort by display order
    photos = sorted(photos, key=lambda p: p.display_order)

    # Apply limit if specified
    if limit is not None and limit > 0:
        photos = photos[:limit]

    # Build response
    response = PhotosResponse(
        photos=photos,
        category=category_enum,
        total_count=len(photos),
        status="success",
    )

    # Create helpful message
    if category_enum:
        category_name = category_enum.value.replace("_", " ")
        if photos:
            message = f"Found {len(photos)} {category_name} photo(s) of the apartment."
        else:
            message = f"No {category_name} photos available."
    else:
        if photos:
            message = f"Here are {len(photos)} photos of the apartment."
        else:
            message = "No photos available."

    return {
        "status": response.status,
        "photos": [
            {
                "id": p.id,
                "url": p.url,
                "caption": p.caption,
                "category": p.category.value,
            }
            for p in photos
        ],
        "category": category_enum.value if category_enum else None,
        "total_count": response.total_count,
        "message": message,
    }
