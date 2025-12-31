"""Area endpoints for local attractions and recommendations.

Provides REST endpoints for:
- Getting local area information (public)
- Getting personalized recommendations (public)

Area data is loaded from static JSON at startup.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from starlette.status import HTTP_400_BAD_REQUEST

from shared.models.area_info import (
    AreaCategory,
    AreaInfo,
    AreaInfoResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from shared.services.area_data import (
    ensure_area_data_loaded,
    get_area_data_store,
)

router = APIRouter(tags=["area"])


@router.get(
    "/area",
    summary="Get local area information",
    description="""
Get information about local places and attractions.

**Public endpoint** - no authentication required.

Returns places sorted by distance from the property.

**Query Parameters:**
- `category`: Optional filter by place category

**Categories:**
- golf: Golf courses
- beach: Beaches
- restaurant: Restaurants and dining
- attraction: Tourist attractions
- activity: Activities and experiences

**Notes:**
- Places are sorted by distance (closest first)
- Includes contact info, features, and family-friendly flags
""",
    response_description="List of local places",
    response_model=AreaInfoResponse,
    responses={
        200: {
            "description": "Area information retrieved",
            "content": {
                "application/json": {
                    "examples": {
                        "all_places": {
                            "summary": "All places",
                            "value": {
                                "places": [
                                    {
                                        "id": "golf-la-marquesa",
                                        "name": "La Marquesa Golf",
                                        "category": "golf",
                                        "description": "Beautiful 18-hole course",
                                        "distance_km": 3.0,
                                        "features": ["18 holes", "clubhouse"],
                                        "family_friendly": True,
                                        "tags": ["golf", "sport"],
                                    }
                                ],
                                "category": None,
                                "total_count": 1,
                            },
                        },
                        "filtered": {
                            "summary": "Filtered by beach",
                            "value": {
                                "places": [
                                    {
                                        "id": "beach-la-mata",
                                        "name": "La Mata Beach",
                                        "category": "beach",
                                        "description": "Popular blue flag beach",
                                        "distance_km": 12.0,
                                        "features": ["sandy", "blue flag"],
                                        "family_friendly": True,
                                        "tags": ["beach", "swimming"],
                                    }
                                ],
                                "category": "beach",
                                "total_count": 1,
                            },
                        },
                    }
                }
            },
        },
        400: {
            "description": "Invalid category",
        },
    },
)
async def get_area_info(
    category: str | None = Query(
        default=None,
        description="Filter by category: golf, beach, restaurant, attraction, activity",
    ),
) -> AreaInfoResponse:
    """Get local area information.

    Supports category filtering.
    """
    ensure_area_data_loaded()
    data = get_area_data_store()

    # Validate and convert category
    category_enum: AreaCategory | None = None
    if category:
        category_lower = category.lower().strip()
        try:
            category_enum = AreaCategory(category_lower)
        except ValueError:
            valid_categories = [c.value for c in AreaCategory]
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=f"Unknown category '{category}'. Valid categories are: {', '.join(valid_categories)}",
            )

    # Filter by category if specified
    if category_enum:
        filtered = [place for place in data if place.category == category_enum]
    else:
        filtered = list(data)

    # Sort by distance (closest first)
    filtered.sort(key=lambda p: p.distance_km)

    return AreaInfoResponse(
        places=filtered,
        category=category_enum,
        total_count=len(filtered),
    )


@router.get(
    "/area/recommendations",
    summary="Get personalized recommendations",
    description="""
Get personalized recommendations based on interests and filters.

**Public endpoint** - no authentication required.

Returns places sorted by relevance to interests, then by distance.

**Query Parameters:**
- `interests`: Comma-separated interests (e.g., "golf,beach,family")
- `max_distance_km`: Maximum distance filter
- `family_friendly_only`: Only family-friendly places
- `limit`: Maximum number of recommendations (1-20, default 5)

**Interest matching:**
- Matches against place tags and categories
- Partial matches in name/description also count
- Without interests, returns diverse recommendations from all categories

**Notes:**
- Places with more interest matches rank higher
- If no interests specified, returns popular places from each category
""",
    response_description="Personalized recommendations",
    response_model=RecommendationResponse,
    responses={
        200: {
            "description": "Recommendations retrieved",
            "content": {
                "application/json": {
                    "examples": {
                        "with_interests": {
                            "summary": "Golf and family interests",
                            "value": {
                                "recommendations": [
                                    {
                                        "id": "golf-la-marquesa",
                                        "name": "La Marquesa Golf",
                                        "category": "golf",
                                        "description": "Beautiful 18-hole course",
                                        "distance_km": 3.0,
                                        "features": ["18 holes", "clubhouse"],
                                        "family_friendly": True,
                                        "tags": ["golf", "sport"],
                                    }
                                ],
                                "total_count": 1,
                                "filters_applied": {
                                    "interests": ["golf", "family"],
                                    "limit": 5,
                                },
                            },
                        },
                        "no_interests": {
                            "summary": "Diverse recommendations",
                            "value": {
                                "recommendations": [
                                    {
                                        "id": "golf-la-marquesa",
                                        "name": "La Marquesa Golf",
                                        "category": "golf",
                                        "distance_km": 3.0,
                                    },
                                    {
                                        "id": "beach-la-mata",
                                        "name": "La Mata Beach",
                                        "category": "beach",
                                        "distance_km": 12.0,
                                    },
                                ],
                                "total_count": 2,
                                "filters_applied": {"limit": 5},
                            },
                        },
                    }
                }
            },
        },
    },
)
async def get_recommendations(
    interests: str | None = Query(
        default=None,
        description="Comma-separated interests (e.g., 'golf,beach,family')",
    ),
    max_distance_km: float | None = Query(
        default=None,
        ge=0,
        description="Maximum distance from property in km",
    ),
    family_friendly_only: bool = Query(
        default=False,
        description="Only return family-friendly places",
    ),
    limit: int = Query(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of recommendations",
    ),
) -> RecommendationResponse:
    """Get personalized recommendations.

    Supports interest matching and various filters.
    """
    ensure_area_data_loaded()
    data = get_area_data_store()

    # Parse comma-separated interests
    interest_list: list[str] = []
    if interests:
        interest_list = [i.strip().lower() for i in interests.split(",") if i.strip()]

    # Score and filter places
    scored_places: list[tuple[AreaInfo, int]] = []

    for place in data:
        # Apply family-friendly filter
        if family_friendly_only and not place.family_friendly:
            continue

        # Apply distance filter
        if max_distance_km is not None and place.distance_km > max_distance_km:
            continue

        # Calculate relevance score based on interest matching
        score = 0
        if interest_list:
            # Check tags (case-insensitive)
            place_tags = [t.lower() for t in place.tags]
            for interest in interest_list:
                if interest in place_tags:
                    score += 2  # Direct tag match
                # Also check if interest matches category
                if interest == place.category.value:
                    score += 2  # Category match
                # Check partial matches in description or name
                if interest in place.description.lower():
                    score += 1
                if interest in place.name.lower():
                    score += 1

        scored_places.append((place, score))

    # Filter based on interests
    if interest_list:
        # Only include places with at least one match
        scored_places = [(p, s) for p, s in scored_places if s > 0]
    else:
        # No interests specified - provide diverse recommendations
        # Group by category and pick from each
        category_places: dict[AreaCategory, list[AreaInfo]] = {}
        for place, _ in scored_places:
            if place.category not in category_places:
                category_places[place.category] = []
            category_places[place.category].append(place)

        # Take closest from each category for diversity
        diverse_places: list[tuple[AreaInfo, int]] = []
        for cat_places in category_places.values():
            cat_places.sort(key=lambda p: p.distance_km)
            for p in cat_places[:2]:  # Take up to 2 from each category
                diverse_places.append((p, 1))
        scored_places = diverse_places

    # Sort by relevance score (descending), then by distance (ascending)
    scored_places.sort(key=lambda x: (-x[1], x[0].distance_km))

    # Apply limit
    recommendations = [place for place, _ in scored_places[:limit]]

    # Build filters applied info
    filters_applied: dict[str, Any] = {}
    if interest_list:
        filters_applied["interests"] = interest_list
    if max_distance_km is not None:
        filters_applied["max_distance_km"] = max_distance_km
    if family_friendly_only:
        filters_applied["family_friendly_only"] = family_friendly_only
    filters_applied["limit"] = limit

    return RecommendationResponse(
        recommendations=recommendations,
        total_count=len(recommendations),
        filters_applied=filters_applied,
    )
