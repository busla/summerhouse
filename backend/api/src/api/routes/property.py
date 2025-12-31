"""Property endpoints for apartment details and photos.

Provides REST endpoints for:
- Getting property details (public)
- Getting property photos with optional category filter (public)

Property data is loaded from static JSON at startup.
"""

from fastapi import APIRouter, HTTPException, Query
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_503_SERVICE_UNAVAILABLE

from shared.models.property import (
    Photo,
    PhotoCategory,
    PhotosResponse,
    Property,
    PropertyDetailsResponse,
)
from shared.services.property_data import (
    ensure_property_data_loaded,
    get_property_data_store,
)

router = APIRouter(tags=["property"])


@router.get(
    "/property",
    summary="Get property details",
    description="""
Get detailed information about the Quesada Apartment.

**Public endpoint** - no authentication required.

Returns complete property information including:
- Name and description
- Address and coordinates
- Bedrooms, bathrooms, and max guests
- Amenities list
- Check-in/out times
- House rules
- Highlights

**Notes:**
- Photo URLs are included separately via /api/property/photos
- This endpoint returns a summary with photo_count
""",
    response_description="Complete property details",
    response_model=PropertyDetailsResponse,
    responses={
        200: {
            "description": "Property details retrieved",
        },
        503: {
            "description": "Property data unavailable",
        },
    },
)
async def get_property_details() -> PropertyDetailsResponse:
    """Get apartment property details.

    Returns complete property information.
    """
    ensure_property_data_loaded()
    prop = get_property_data_store()

    if prop is None:
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail="Property data not available",
        )

    return PropertyDetailsResponse(
        property=prop,
        status="success",
        message=f"Details for {prop.name}",
    )


@router.get(
    "/property/photos",
    summary="Get property photos",
    description="""
Get photos of the Quesada Apartment.

**Public endpoint** - no authentication required.

Returns photo URLs with captions, sorted by display order.

**Query Parameters:**
- `category`: Optional filter by photo category
- `limit`: Optional maximum number of photos to return

**Categories:**
- exterior, living_room, bedroom, bathroom, kitchen
- terrace, pool, garden, view, other

**Notes:**
- Photos are sorted by display_order
- All photos are hosted on CDN
""",
    response_description="List of property photos",
    response_model=PhotosResponse,
    responses={
        200: {
            "description": "Photos retrieved",
            "content": {
                "application/json": {
                    "examples": {
                        "all_photos": {
                            "summary": "All photos",
                            "value": {
                                "photos": [
                                    {
                                        "id": "exterior-1",
                                        "url": "https://cdn.example.com/exterior.jpg",
                                        "caption": "Front view of apartment",
                                        "category": "exterior",
                                        "display_order": 1,
                                    }
                                ],
                                "category": None,
                                "total_count": 1,
                                "status": "success",
                                "message": "Here are 1 photos of the apartment.",
                            },
                        },
                        "filtered_by_category": {
                            "summary": "Filtered by bedroom",
                            "value": {
                                "photos": [
                                    {
                                        "id": "bedroom-1",
                                        "url": "https://cdn.example.com/bedroom.jpg",
                                        "caption": "Master bedroom",
                                        "category": "bedroom",
                                        "display_order": 5,
                                    }
                                ],
                                "category": "bedroom",
                                "total_count": 1,
                                "status": "success",
                                "message": "Found 1 bedroom photo(s) of the apartment.",
                            },
                        },
                    }
                }
            },
        },
        400: {
            "description": "Invalid category",
        },
        503: {
            "description": "Property data unavailable",
        },
    },
)
async def get_property_photos(
    category: str | None = Query(
        default=None,
        description="Filter by category: exterior, living_room, bedroom, bathroom, kitchen, terrace, pool, garden, view, other",
    ),
    limit: int | None = Query(
        default=None,
        ge=1,
        le=100,
        description="Maximum number of photos to return",
    ),
) -> PhotosResponse:
    """Get property photos with optional filtering.

    Supports category and limit filters.
    """
    ensure_property_data_loaded()
    prop = get_property_data_store()

    if prop is None:
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail="Property data not available",
        )

    # Validate and convert category
    category_enum: PhotoCategory | None = None
    if category:
        category_lower = category.lower().strip().replace(" ", "_")
        try:
            category_enum = PhotoCategory(category_lower)
        except ValueError:
            valid_categories = [c.value for c in PhotoCategory]
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=f"Unknown category '{category}'. Valid categories are: {', '.join(valid_categories)}",
            )

    # Filter photos by category if specified
    photos: list[Photo] = prop.photos
    if category_enum:
        photos = [p for p in photos if p.category == category_enum]

    # Sort by display order
    photos = sorted(photos, key=lambda p: p.display_order)

    # Apply limit if specified
    if limit is not None:
        photos = photos[:limit]

    # Build response message
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

    return PhotosResponse(
        photos=photos,
        category=category_enum,
        total_count=len(photos),
        status="success",
        message=message,
    )
