"""Property tools for apartment details and photos.

These tools allow the booking agent to provide detailed information
about the Quesada Apartment vacation rental.
"""

import logging
from typing import Any

from strands import tool

from shared.models import (
    PhotoCategory,
    PhotosResponse,
    PropertyDetailsResponse,
)

# Re-export data utilities from service module for backwards compatibility
from shared.services.property_data import (
    ensure_property_data_loaded,
    get_property_data_store,
    load_property_data_from_dict,
    load_property_data_from_json,
    set_property_data_store,
)

logger = logging.getLogger(__name__)


@tool
def get_property_details() -> dict[str, Any]:
    """Get detailed information about the Quesada Apartment.

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
    """Get photos of the Quesada Apartment.

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
