"""API models for availability endpoints.

Extends shared availability models with API-specific response formats
for calendar views and alternative date suggestions.
"""

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from shared.models.enums import AvailabilityStatus


class CalendarDay(BaseModel):
    """Single day in calendar view.

    Provides detailed availability info for calendar rendering,
    including check-in/out restrictions.
    """

    model_config = ConfigDict(strict=True)

    date: dt.date = Field(
        ...,
        description="Calendar date (YYYY-MM-DD)",
        examples=["2025-07-15"],
    )
    status: AvailabilityStatus = Field(
        ...,
        description="Availability status for this date",
        examples=["available"],
    )
    is_check_in_allowed: bool = Field(
        default=True,
        description="Whether check-in is allowed on this date",
    )
    is_check_out_allowed: bool = Field(
        default=True,
        description="Whether check-out is allowed on this date",
    )


class CalendarResponse(BaseModel):
    """Monthly calendar view response.

    Returns all days in a month with their availability status
    and summary counts for quick overview.
    """

    model_config = ConfigDict(
        strict=True,
        json_schema_extra={
            "examples": [
                {
                    "month": "2025-07",
                    "days": [
                        {
                            "date": "2025-07-01",
                            "status": "available",
                            "is_check_in_allowed": True,
                            "is_check_out_allowed": True,
                        },
                        {
                            "date": "2025-07-02",
                            "status": "booked",
                            "is_check_in_allowed": False,
                            "is_check_out_allowed": False,
                        },
                    ],
                    "available_count": 20,
                    "booked_count": 8,
                    "blocked_count": 3,
                }
            ]
        },
    )

    month: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}$",
        description="Month in YYYY-MM format",
        examples=["2025-07"],
    )
    days: list[CalendarDay] = Field(
        ...,
        description="List of days in the month with availability status",
    )
    available_count: int = Field(
        ...,
        ge=0,
        description="Number of available days",
    )
    booked_count: int = Field(
        ...,
        ge=0,
        description="Number of booked days",
    )
    blocked_count: int = Field(
        ...,
        ge=0,
        description="Number of blocked days",
    )


class AlternativeDateRange(BaseModel):
    """Alternative date suggestion when requested dates are unavailable.

    Provides nearby available date ranges that match the
    requested stay duration.
    """

    model_config = ConfigDict(strict=True)

    check_in: dt.date = Field(
        ...,
        description="Alternative check-in date",
        examples=["2025-07-20"],
    )
    check_out: dt.date = Field(
        ...,
        description="Alternative check-out date",
        examples=["2025-07-27"],
    )
    nights: int = Field(
        ...,
        ge=1,
        description="Number of nights (same as originally requested)",
    )
    offset_days: int = Field(
        ...,
        description="Days shifted from original dates (negative=earlier, positive=later)",
    )
    direction: str = Field(
        ...,
        description="Direction of shift: 'earlier' or 'later'",
        examples=["later"],
    )
