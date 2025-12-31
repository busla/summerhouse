"""Pricing endpoints for rate information and calculations.

Provides REST endpoints for:
- Current base pricing
- Price calculation for specific date ranges
- All seasonal rates
- Minimum stay validation

All amounts are in EUR cents (e.g., 15000 = €150.00).
"""

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

from api.dependencies import get_pricing_service
from api.models.pricing import (
    BasePricingResponse,
    MinimumStayCheckResponse,
    MinimumStayInfoResponse,
    SeasonalRatesResponse,
)
from shared.models.pricing import PriceCalculation
from shared.services.pricing import PricingService

router = APIRouter(tags=["pricing"])


@router.get(
    "/pricing",
    summary="Get current pricing",
    description="""
Get current base pricing information.

Returns the pricing applicable for today, including nightly rate,
cleaning fee, and minimum stay requirement. Useful for displaying
default pricing before user selects specific dates.

**Notes:**
- Amounts are in EUR cents (e.g., 15000 = €150.00)
- Returns pricing for today's date/season
""",
    response_description="Current pricing configuration",
    response_model=BasePricingResponse,
    responses={
        200: {
            "description": "Current pricing retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "nightly_rate": 15000,
                        "cleaning_fee": 7500,
                        "minimum_nights": 7,
                        "season_name": "High Season (July-August)",
                        "currency": "EUR",
                    }
                }
            },
        },
        404: {
            "description": "No pricing configured for today's date",
        },
    },
)
async def get_current_pricing(
    service: PricingService = Depends(get_pricing_service),
) -> BasePricingResponse:
    """Get current pricing for today.

    Returns the seasonal pricing applicable for today's date.
    """
    today = dt.date.today()
    season = service.get_season_for_date(today)

    if not season:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail="No pricing configured for today's date",
        )

    return BasePricingResponse(
        nightly_rate=season.nightly_rate,
        cleaning_fee=season.cleaning_fee,
        minimum_nights=season.minimum_nights,
        season_name=season.season_name,
    )


@router.get(
    "/pricing/calculate",
    summary="Calculate stay price",
    description="""
Calculate total price for a specific stay.

Returns detailed pricing breakdown including nightly rate,
number of nights, subtotal, cleaning fee, and total amount.
Uses the pricing for the check-in date's season.

**Notes:**
- Amounts are in EUR cents
- check_out is exclusive (last night is check_out - 1 day)
- Season is determined by check-in date
""",
    response_description="Detailed pricing breakdown",
    response_model=PriceCalculation,
    responses={
        200: {
            "description": "Price calculated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "check_in": "2025-07-15",
                        "check_out": "2025-07-22",
                        "nights": 7,
                        "nightly_rate": 15000,
                        "subtotal": 105000,
                        "cleaning_fee": 7500,
                        "total_amount": 112500,
                        "minimum_nights": 7,
                        "season_name": "High Season (July-August)",
                    }
                }
            },
        },
        400: {
            "description": "Invalid date range",
        },
        404: {
            "description": "No pricing for selected dates",
        },
    },
)
async def calculate_price(
    check_in: dt.date = Query(
        ...,
        description="Check-in date (YYYY-MM-DD)",
        examples=["2025-07-15"],
    ),
    check_out: dt.date = Query(
        ...,
        description="Check-out date (YYYY-MM-DD)",
        examples=["2025-07-22"],
    ),
    service: PricingService = Depends(get_pricing_service),
) -> PriceCalculation:
    """Calculate price for date range.

    Calculates total cost based on check-in date's season.
    """
    # Validate date range
    if check_out <= check_in:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="check_out must be after check_in",
        )

    price_calc = service.calculate_price(check_in, check_out)

    if not price_calc:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail="No pricing available for selected dates",
        )

    return price_calc


@router.get(
    "/pricing/rates",
    summary="Get all seasonal rates",
    description="""
Get all seasonal pricing rates.

Returns complete pricing schedule with all active seasons,
including date ranges, nightly rates, minimum stays, and
cleaning fees. Useful for displaying full pricing calendar.

**Notes:**
- Amounts are in EUR cents
- Seasons are sorted by start date
- Only active seasons are returned
""",
    response_description="All seasonal pricing configurations",
    response_model=SeasonalRatesResponse,
    responses={
        200: {
            "description": "Seasonal rates retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "seasons": [
                            {
                                "season_id": "low-2025",
                                "season_name": "Low Season",
                                "start_date": "2025-01-01",
                                "end_date": "2025-03-31",
                                "nightly_rate": 8000,
                                "minimum_nights": 3,
                                "cleaning_fee": 5000,
                                "is_active": True,
                            }
                        ],
                        "currency": "EUR",
                    }
                }
            },
        },
    },
)
async def get_seasonal_rates(
    service: PricingService = Depends(get_pricing_service),
) -> SeasonalRatesResponse:
    """Get all seasonal pricing.

    Returns all active seasons sorted by start date.
    """
    seasons = service.get_all_seasons(active_only=True)
    return SeasonalRatesResponse(seasons=seasons)


@router.get(
    "/pricing/minimum-stay",
    summary="Validate minimum stay",
    description="""
Check if a stay duration meets minimum requirements.

Validates whether the number of nights between check-in and
check-out meets the minimum stay requirement for that season.

**Notes:**
- Season is determined by check-in date
- Returns validation message if requirement not met
""",
    response_description="Minimum stay validation result",
    response_model=MinimumStayCheckResponse,
    responses={
        200: {
            "description": "Validation completed",
            "content": {
                "application/json": {
                    "examples": {
                        "valid": {
                            "summary": "Valid stay",
                            "value": {
                                "is_valid": True,
                                "requested_nights": 7,
                                "minimum_nights": 7,
                                "season_name": "High Season (July-August)",
                                "message": "",
                            },
                        },
                        "invalid": {
                            "summary": "Stay too short",
                            "value": {
                                "is_valid": False,
                                "requested_nights": 3,
                                "minimum_nights": 7,
                                "season_name": "High Season (July-August)",
                                "message": "Minimum stay is 7 nights during High Season (July-August). You selected 3 nights.",
                            },
                        },
                    }
                }
            },
        },
        400: {
            "description": "Invalid date range",
        },
        404: {
            "description": "No pricing for selected dates",
        },
    },
)
async def check_minimum_stay(
    check_in: dt.date = Query(
        ...,
        description="Check-in date (YYYY-MM-DD)",
        examples=["2025-07-15"],
    ),
    check_out: dt.date = Query(
        ...,
        description="Check-out date (YYYY-MM-DD)",
        examples=["2025-07-22"],
    ),
    service: PricingService = Depends(get_pricing_service),
) -> MinimumStayCheckResponse:
    """Validate minimum stay requirement.

    Checks if the requested stay duration meets the minimum
    nights requirement for the check-in date's season.
    """
    # Validate date range
    if check_out <= check_in:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="check_out must be after check_in",
        )

    season = service.get_season_for_date(check_in)
    if not season:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail="No pricing available for selected dates",
        )

    is_valid, message = service.validate_minimum_stay(check_in, check_out)
    nights = (check_out - check_in).days

    return MinimumStayCheckResponse(
        is_valid=is_valid,
        requested_nights=nights,
        minimum_nights=season.minimum_nights,
        season_name=season.season_name,
        message=message,
    )


@router.get(
    "/pricing/minimum-stay/{date}",
    summary="Get minimum stay for date",
    description="""
Get minimum stay information for a specific date.

Returns the minimum nights requirement and pricing for
bookings starting on the specified date.

**Notes:**
- Date format: YYYY-MM-DD
- Returns 404 if no pricing configured for date
""",
    response_description="Minimum stay info for the date",
    response_model=MinimumStayInfoResponse,
    responses={
        200: {
            "description": "Minimum stay info retrieved",
            "content": {
                "application/json": {
                    "example": {
                        "date": "2025-07-15",
                        "minimum_nights": 7,
                        "season_name": "High Season (July-August)",
                        "nightly_rate": 15000,
                    }
                }
            },
        },
        404: {
            "description": "No pricing for specified date",
        },
    },
)
async def get_minimum_stay_for_date(
    date: dt.date,
    service: PricingService = Depends(get_pricing_service),
) -> MinimumStayInfoResponse:
    """Get minimum stay info for a specific date.

    Returns pricing and minimum stay requirement for the
    season applicable to the given date.
    """
    season = service.get_season_for_date(date)

    if not season:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"No pricing configured for {date.isoformat()}",
        )

    return MinimumStayInfoResponse(
        date=date,
        minimum_nights=season.minimum_nights,
        season_name=season.season_name,
        nightly_rate=season.nightly_rate,
    )
