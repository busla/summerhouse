"""Availability endpoints for checking date availability.

Provides REST endpoints for:
- Checking availability and pricing for a date range
- Getting monthly calendar views with availability status

All dates are in YYYY-MM-DD format. Amounts are in EUR cents.
"""

import calendar
import datetime as dt
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.status import HTTP_400_BAD_REQUEST

from api.dependencies import get_availability_service
from api.models.availability import CalendarDay, CalendarResponse
from shared.models.availability import AvailabilityResponse
from shared.models.enums import AvailabilityStatus
from shared.services.availability import AvailabilityService

router = APIRouter(tags=["availability"])


@router.get(
    "/availability",
    summary="Check date availability",
    description="""
Check if specific dates are available for booking.

Returns availability status, unavailable dates within range,
and pricing breakdown. Use before creating a reservation to verify
dates are open.

**Notes:**
- Dates are in YYYY-MM-DD format
- check_out is exclusive (last night is check_out - 1 day)
- Amounts are in EUR cents (e.g., 15000 = €150.00)
- Returns suggested alternatives if dates are unavailable (FR-003)
""",
    response_description="Availability status with pricing breakdown",
    response_model=AvailabilityResponse,
    responses={
        200: {
            "description": "Availability check completed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "start_date": "2025-07-15",
                        "end_date": "2025-07-22",
                        "is_available": True,
                        "unavailable_dates": [],
                        "total_nights": 7,
                        "nightly_rate": 15000,
                        "cleaning_fee": 7500,
                        "total_amount": 112500,
                    }
                }
            },
        },
        400: {
            "description": "Invalid date range (check_out must be after check_in)",
        },
    },
)
async def check_availability(
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
    service: AvailabilityService = Depends(get_availability_service),
) -> AvailabilityResponse:
    """Check availability for date range.

    Verifies all dates in range are available and calculates
    total pricing based on the check-in date's season.
    """
    # Validate date range
    if check_out <= check_in:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="check_out must be after check_in",
        )

    return service.check_availability(check_in, check_out)


@router.get(
    "/availability/calendar/{month}",
    summary="Get monthly calendar",
    description="""
Get availability calendar for a specific month.

Returns each day in the month with its availability status,
check-in/out restrictions, and summary counts.

**Notes:**
- Month format: YYYY-MM (e.g., 2025-07)
- Days are returned in chronological order
- Counts help quickly assess month availability
""",
    response_description="Calendar with daily availability status",
    response_model=CalendarResponse,
    responses={
        200: {
            "description": "Calendar retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "month": "2025-07",
                        "days": [
                            {
                                "date": "2025-07-01",
                                "status": "available",
                                "is_check_in_allowed": True,
                                "is_check_out_allowed": True,
                            },
                        ],
                        "available_count": 20,
                        "booked_count": 8,
                        "blocked_count": 3,
                    }
                }
            },
        },
        400: {
            "description": "Invalid month format (expected YYYY-MM)",
        },
    },
)
async def get_calendar(
    month: str,
    service: AvailabilityService = Depends(get_availability_service),
) -> CalendarResponse:
    """Get monthly calendar view.

    Fetches availability for all days in the specified month
    and aggregates into a calendar view.
    """
    # Validate month format
    if not re.match(r"^\d{4}-\d{2}$", month):
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Invalid month format. Expected YYYY-MM (e.g., 2025-07)",
        )

    # Parse month
    try:
        year, month_num = map(int, month.split("-"))
        if month_num < 1 or month_num > 12:
            raise ValueError("Month must be between 01 and 12")
    except ValueError as e:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Invalid month: {e}",
        ) from e

    # Calculate date range for the month
    _, last_day = calendar.monthrange(year, month_num)
    start_date = dt.date(year, month_num, 1)
    end_date = dt.date(year, month_num, last_day) + dt.timedelta(days=1)

    # Get availability for the entire month
    availability_list = service.get_range(start_date, end_date)

    # Build calendar days and count statuses
    days: list[CalendarDay] = []
    available_count = 0
    booked_count = 0
    blocked_count = 0

    for avail in availability_list:
        # Determine check-in/out rules based on status
        is_check_in_allowed = avail.status == AvailabilityStatus.AVAILABLE
        is_check_out_allowed = avail.status == AvailabilityStatus.AVAILABLE

        days.append(
            CalendarDay(
                date=avail.date,
                status=avail.status,
                is_check_in_allowed=is_check_in_allowed,
                is_check_out_allowed=is_check_out_allowed,
            )
        )

        # Count statuses
        if avail.status == AvailabilityStatus.AVAILABLE:
            available_count += 1
        elif avail.status == AvailabilityStatus.BOOKED:
            booked_count += 1
        elif avail.status == AvailabilityStatus.BLOCKED:
            blocked_count += 1

    return CalendarResponse(
        month=month,
        days=days,
        available_count=available_count,
        booked_count=booked_count,
        blocked_count=blocked_count,
    )
