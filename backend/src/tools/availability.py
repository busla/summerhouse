"""Availability tools for checking property availability.

These tools allow the booking agent to check if dates are available
and retrieve calendar views of availability.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any

from strands import tool

logger = logging.getLogger(__name__)

from src.models.availability import AvailabilityResponse
from src.models.enums import AvailabilityStatus
from src.services.availability import AvailabilityService
from src.services.dynamodb import get_dynamodb_service
from src.services.pricing import PricingService


def _get_db():
    """Get shared DynamoDB service instance (singleton for performance)."""
    return get_dynamodb_service()


def _get_availability_service() -> AvailabilityService:
    """Get AvailabilityService instance (uses shared DB connection)."""
    db = get_dynamodb_service()
    pricing = PricingService(db)
    return AvailabilityService(db, pricing)


def _parse_date(date_str: str) -> date:
    """Parse date string in YYYY-MM-DD format."""
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def _date_range(start: date, end: date) -> list[date]:
    """Generate list of dates from start to end (exclusive of end)."""
    dates = []
    current = start
    while current < end:
        dates.append(current)
        current += timedelta(days=1)
    return dates


@tool
def check_availability(check_in: str, check_out: str) -> dict[str, Any]:
    """Check if the property is available for the specified date range.

    Use this tool when a guest asks about availability for specific dates.
    Returns whether the dates are available, and if not, which dates are blocked.

    Args:
        check_in: Check-in date in YYYY-MM-DD format (e.g., '2025-07-15')
        check_out: Check-out date in YYYY-MM-DD format (e.g., '2025-07-22')

    Returns:
        Dictionary with availability status, unavailable dates, and pricing summary
    """
    logger.info("check_availability called", extra={"check_in": check_in, "check_out": check_out})
    try:
        start_date = _parse_date(check_in)
        end_date = _parse_date(check_out)
    except ValueError:
        return {
            "status": "error",
            "message": "Invalid date format. Please use YYYY-MM-DD format.",
        }

    if end_date <= start_date:
        return {
            "status": "error",
            "message": "Check-out date must be after check-in date.",
        }

    # Validate dates are not in the past
    today = date.today()
    if start_date < today:
        return {
            "status": "error",
            "is_available": False,
            "message": f"Cannot book past dates. Today is {today.isoformat()}. Please choose dates from {today.isoformat()} onwards.",
            "reason": "past_dates",
        }

    # Calculate number of nights
    total_nights = (end_date - start_date).days

    # Query availability table for the date range
    db = _get_db()
    dates_to_check = _date_range(start_date, end_date)

    # Batch get availability for all dates
    keys = [{"date": d.isoformat()} for d in dates_to_check]
    items = db.batch_get("availability", keys)

    # Build lookup of dates that EXIST in DynamoDB
    existing_dates: dict[str, dict] = {item["date"]: item for item in items}

    # Check availability - dates must EXIST and be AVAILABLE
    # Missing dates are treated as UNAVAILABLE (past dates, beyond seed range, gaps)
    unavailable_dates: list[str] = []
    missing_dates: list[str] = []
    for d in dates_to_check:
        date_str = d.isoformat()
        if date_str not in existing_dates:
            # Date doesn't exist in DynamoDB - treat as unavailable
            missing_dates.append(date_str)
            unavailable_dates.append(date_str)
        elif existing_dates[date_str].get("status") != AvailabilityStatus.AVAILABLE.value:
            # Date exists but is not available (booked/blocked)
            unavailable_dates.append(date_str)

    # All dates must exist AND be available
    is_available = len(unavailable_dates) == 0

    # Get pricing for the period (simplified - use pricing tool for details)
    # For now, use default rates
    default_nightly_rate = 12000  # €120.00 in cents
    default_cleaning_fee = 5000  # €50.00 in cents

    response = AvailabilityResponse(
        start_date=start_date,
        end_date=end_date,
        is_available=is_available,
        unavailable_dates=[_parse_date(d) for d in unavailable_dates],
        total_nights=total_nights,
        nightly_rate=default_nightly_rate,
        cleaning_fee=default_cleaning_fee,
        total_amount=(default_nightly_rate * total_nights) + default_cleaning_fee,
    )

    if is_available:
        return {
            "status": "success",
            "is_available": True,
            "check_in": check_in,
            "check_out": check_out,
            "total_nights": response.total_nights,
            "message": f"Great news! The property is available from {check_in} to {check_out} ({total_nights} nights).",
            "estimated_total_eur": response.total_amount / 100,
        }
    else:
        # Get alternative date suggestions (T077 enhancement)
        availability_service = _get_availability_service()
        suggestions = availability_service.suggest_alternative_dates(
            requested_start=start_date,
            requested_end=end_date,
            search_window_days=14,
            max_suggestions=3,
        )

        # Build helpful message with alternatives
        base_message = f"Unfortunately, some dates are not available: {', '.join(unavailable_dates)}"
        if suggestions:
            alt_list = []
            for s in suggestions:
                direction = "earlier" if s["offset_days"] < 0 else "later"
                days_diff = abs(s["offset_days"])
                alt_list.append(f"{s['check_in']} to {s['check_out']} ({days_diff} day(s) {direction})")
            base_message += f"\n\nAlternative dates available:\n• " + "\n• ".join(alt_list)

        return {
            "status": "success",
            "is_available": False,
            "check_in": check_in,
            "check_out": check_out,
            "unavailable_dates": unavailable_dates,
            "alternative_dates": suggestions,
            "message": base_message,
        }


@tool
def get_calendar(month: str) -> dict[str, Any]:
    """Get the availability calendar for a specific month.

    Use this tool when a guest wants to see which dates are available
    in a particular month, or when they're flexible on dates.

    Args:
        month: Month in YYYY-MM format (e.g., '2025-07')

    Returns:
        Dictionary with available and unavailable dates for the month
    """
    logger.info("get_calendar called", extra={"month": month})
    try:
        year, month_num = map(int, month.split("-"))
        first_day = date(year, month_num, 1)

        # Calculate last day of month
        if month_num == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month_num + 1, 1) - timedelta(days=1)
    except (ValueError, IndexError):
        return {
            "status": "error",
            "message": "Invalid month format. Please use YYYY-MM format (e.g., '2025-07').",
        }

    # Generate all dates in the month
    all_dates = _date_range(first_day, last_day + timedelta(days=1))

    # Query availability for the month
    db = _get_db()
    keys = [{"date": d.isoformat()} for d in all_dates]
    items = db.batch_get("availability", keys)

    # Build lookup of unavailable dates
    unavailable_lookup: dict[str, str] = {}
    for item in items:
        if item.get("status") != AvailabilityStatus.AVAILABLE.value:
            unavailable_lookup[item["date"]] = item.get("status", "unavailable")

    # Build lookup of dates that EXIST in DynamoDB
    existing_dates: set[str] = {item["date"] for item in items}

    # Categorize dates - missing dates are treated as blocked (not available)
    today = date.today()
    available_dates: list[str] = []
    booked_dates: list[str] = []
    blocked_dates: list[str] = []
    past_dates: list[str] = []

    for d in all_dates:
        date_str = d.isoformat()
        if d < today:
            # Past dates cannot be booked
            past_dates.append(date_str)
        elif date_str not in existing_dates:
            # Date doesn't exist in DynamoDB - treat as blocked
            blocked_dates.append(date_str)
        elif date_str in unavailable_lookup:
            status = unavailable_lookup[date_str]
            if status == AvailabilityStatus.BOOKED.value:
                booked_dates.append(date_str)
            else:
                blocked_dates.append(date_str)
        else:
            available_dates.append(date_str)

    total_unavailable = len(booked_dates) + len(blocked_dates) + len(past_dates)
    return {
        "status": "success",
        "month": month,
        "available_dates": available_dates,
        "booked_dates": booked_dates,
        "blocked_dates": blocked_dates,
        "past_dates": past_dates,
        "total_available": len(available_dates),
        "total_unavailable": total_unavailable,
        "message": f"In {month}, there are {len(available_dates)} available dates and {total_unavailable} unavailable dates.",
    }
