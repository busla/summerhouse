"""Reservation tools for creating and managing bookings.

These tools allow the booking agent to create reservations,
check reservation details, and manage bookings with double-booking prevention.
"""

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from strands import tool

logger = logging.getLogger(__name__)

from src.models.enums import AvailabilityStatus, PaymentStatus, ReservationStatus
from src.models.errors import ErrorCode, ToolError
from src.models.reservation import Reservation
from src.services.dynamodb import DynamoDBService, get_dynamodb_service


def _get_db() -> DynamoDBService:
    """Get shared DynamoDB service instance (singleton for performance)."""
    return get_dynamodb_service()


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


def _generate_reservation_id() -> str:
    """Generate a unique reservation ID."""
    year = datetime.now().year
    unique_part = uuid.uuid4().hex[:8].upper()
    return f"RES-{year}-{unique_part}"


def _check_dates_available(db: DynamoDBService, dates: list[date]) -> tuple[bool, list[str]]:
    """Check if all dates are available.

    Returns tuple of (all_available, list_of_unavailable_dates)
    """
    keys = [{"date": d.isoformat()} for d in dates]
    items = db.batch_get("availability", keys)

    unavailable = []
    for item in items:
        if item.get("status") != AvailabilityStatus.AVAILABLE.value:
            unavailable.append(item["date"])

    return len(unavailable) == 0, unavailable


def _get_pricing_for_dates(check_in: date, check_out: date) -> tuple[int, int]:  # noqa: ARG001
    """Get nightly rate and cleaning fee for dates.

    Returns (nightly_rate_cents, cleaning_fee_cents)
    """
    # Simplified pricing logic - in production, query pricing table
    # and handle seasonal variations
    return (12000, 5000)  # €120/night, €50 cleaning


@tool
def create_reservation(
    guest_id: str,
    check_in: str,
    check_out: str,
    num_adults: int,
    num_children: int = 0,
    special_requests: str | None = None,
) -> dict[str, Any]:
    """Create a new reservation with double-booking prevention.

    Use this tool when a guest confirms they want to book the property.
    This will check availability and create a pending reservation.
    The reservation must be paid to be confirmed.

    IMPORTANT: Only call this after the guest has confirmed they want to book.
    First use check_availability to verify dates are available.

    Args:
        guest_id: The verified guest's ID (from verification process)
        check_in: Check-in date in YYYY-MM-DD format (e.g., '2025-07-15')
        check_out: Check-out date in YYYY-MM-DD format (e.g., '2025-07-22')
        num_adults: Number of adult guests (at least 1)
        num_children: Number of children (default: 0)
        special_requests: Any special requests from the guest (optional)

    Returns:
        Dictionary with reservation details or error message
    """
    logger.info("create_reservation called", extra={"guest_id": guest_id, "check_in": check_in, "check_out": check_out, "num_adults": num_adults, "num_children": num_children})
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

    if num_adults < 1:
        return {
            "status": "error",
            "message": "At least 1 adult guest is required.",
        }

    total_guests = num_adults + num_children
    max_guests = 6  # Property maximum
    if total_guests > max_guests:
        error = ToolError.from_code(
            ErrorCode.MAX_GUESTS_EXCEEDED,
            details={"requested": str(total_guests), "maximum": str(max_guests)},
        )
        return error.model_dump()

    nights = (end_date - start_date).days
    dates_to_book = _date_range(start_date, end_date)

    db = _get_db()

    # Check availability with atomic check
    is_available, unavailable_dates = _check_dates_available(db, dates_to_book)

    if not is_available:
        error = ToolError.from_code(
            ErrorCode.DATES_UNAVAILABLE,
            details={"unavailable_dates": ", ".join(unavailable_dates)},
        )
        return error.model_dump()

    # Get pricing
    nightly_rate, cleaning_fee = _get_pricing_for_dates(start_date, end_date)
    total_amount = (nightly_rate * nights) + cleaning_fee

    # Generate reservation ID
    reservation_id = _generate_reservation_id()
    now = datetime.now(timezone.utc)

    # Create reservation record
    reservation = Reservation(
        reservation_id=reservation_id,
        guest_id=guest_id,
        check_in=start_date,
        check_out=end_date,
        num_adults=num_adults,
        num_children=num_children,
        status=ReservationStatus.PENDING,
        payment_status=PaymentStatus.PENDING,
        total_amount=total_amount,
        cleaning_fee=cleaning_fee,
        nightly_rate=nightly_rate,
        nights=nights,
        special_requests=special_requests,
        created_at=now,
        updated_at=now,
    )

    # Use transactional write to atomically:
    # 1. Create reservation
    # 2. Mark dates as booked

    # Build transaction items
    transact_items: list[dict[str, Any]] = []

    # Add reservation
    reservation_item = reservation.model_dump(mode="json")
    # Convert date/datetime to strings for DynamoDB
    reservation_item["check_in"] = start_date.isoformat()
    reservation_item["check_out"] = end_date.isoformat()
    reservation_item["created_at"] = now.isoformat()
    reservation_item["updated_at"] = now.isoformat()

    transact_items.append(
        {
            "Put": {
                "TableName": db._table_name("reservations"),
                "Item": {k: _serialize_dynamodb(v) for k, v in reservation_item.items() if v is not None},
                "ConditionExpression": "attribute_not_exists(reservation_id)",
            }
        }
    )

    # Add availability updates with condition checks (double-booking prevention)
    for d in dates_to_book:
        transact_items.append(
            {
                "Put": {
                    "TableName": db._table_name("availability"),
                    "Item": {
                        "date": {"S": d.isoformat()},
                        "status": {"S": AvailabilityStatus.BOOKED.value},
                        "reservation_id": {"S": reservation_id},
                        "updated_at": {"S": now.isoformat()},
                    },
                    # Only succeed if date is available or doesn't exist
                    "ConditionExpression": "attribute_not_exists(#s) OR #s = :available",
                    "ExpressionAttributeNames": {"#s": "status"},
                    "ExpressionAttributeValues": {
                        ":available": {"S": AvailabilityStatus.AVAILABLE.value}
                    },
                }
            }
        )

    # Execute transaction
    success = db.transact_write(transact_items)

    if not success:
        # Booking conflict is a form of dates unavailable (race condition)
        error = ToolError.from_code(
            ErrorCode.DATES_UNAVAILABLE,
            details={"reason": "booking_conflict"},
        )
        return error.model_dump()

    return {
        "status": "success",
        "reservation_id": reservation_id,
        "check_in": check_in,
        "check_out": check_out,
        "nights": nights,
        "num_adults": num_adults,
        "num_children": num_children,
        "total_amount_eur": total_amount / 100,
        "total_amount_cents": total_amount,
        "payment_status": PaymentStatus.PENDING.value,
        "reservation_status": ReservationStatus.PENDING.value,
        "message": f"Reservation {reservation_id} created! Total: €{total_amount / 100:.2f} for {nights} nights. Please proceed with payment to confirm your booking.",
    }


def _serialize_dynamodb(value: Any) -> dict[str, Any]:
    """Serialize a Python value to DynamoDB format."""
    if isinstance(value, str):
        return {"S": value}
    elif isinstance(value, bool):
        return {"BOOL": value}
    elif isinstance(value, int | float):
        return {"N": str(value)}
    elif value is None:
        return {"NULL": True}
    elif isinstance(value, list):
        return {"L": [_serialize_dynamodb(v) for v in value]}
    elif isinstance(value, dict):
        return {"M": {k: _serialize_dynamodb(v) for k, v in value.items()}}
    else:
        return {"S": str(value)}


@tool
def modify_reservation(
    reservation_id: str,
    new_check_in: str | None = None,
    new_check_out: str | None = None,
    new_num_adults: int | None = None,
    new_num_children: int | None = None,
    new_special_requests: str | None = None,
) -> dict[str, Any]:
    """Modify an existing reservation.

    Use this tool when a guest wants to change their booking dates or
    number of guests. Price will be recalculated for date changes.

    IMPORTANT: Only modify reservations that are pending or confirmed.
    Cannot modify cancelled or completed reservations.

    Args:
        reservation_id: The reservation ID (e.g., 'RES-2025-ABCD1234')
        new_check_in: New check-in date in YYYY-MM-DD format (optional)
        new_check_out: New check-out date in YYYY-MM-DD format (optional)
        new_num_adults: New number of adults (optional)
        new_num_children: New number of children (optional)
        new_special_requests: Updated special requests (optional)

    Returns:
        Dictionary with updated reservation details or error message
    """
    logger.info("modify_reservation called", extra={"reservation_id": reservation_id})
    db = _get_db()

    # Get existing reservation
    item = db.get_item("reservations", {"reservation_id": reservation_id})

    if not item:
        error = ToolError.from_code(
            ErrorCode.RESERVATION_NOT_FOUND,
            details={"reservation_id": reservation_id},
        )
        return error.model_dump()

    # Check if reservation can be modified
    current_status = item.get("status")
    if current_status in [ReservationStatus.CANCELLED.value, ReservationStatus.COMPLETED.value]:
        error = ToolError.from_code(
            ErrorCode.UNAUTHORIZED,
            details={"reason": f"Cannot modify a {current_status} reservation"},
        )
        return error.model_dump()

    # Parse dates
    current_check_in = _parse_date(item["check_in"])
    current_check_out = _parse_date(item["check_out"])

    # Determine new dates
    try:
        check_in = _parse_date(new_check_in) if new_check_in else current_check_in
        check_out = _parse_date(new_check_out) if new_check_out else current_check_out
    except ValueError:
        return {
            "status": "error",
            "message": "Invalid date format. Please use YYYY-MM-DD format.",
        }

    if check_out <= check_in:
        return {
            "status": "error",
            "message": "Check-out date must be after check-in date.",
        }

    # Determine new guest counts
    num_adults = new_num_adults if new_num_adults is not None else item["num_adults"]
    num_children = new_num_children if new_num_children is not None else item.get("num_children", 0)

    if num_adults < 1:
        return {
            "status": "error",
            "message": "At least 1 adult guest is required.",
        }

    total_guests = num_adults + num_children
    max_guests = 6
    if total_guests > max_guests:
        return {
            "status": "error",
            "message": f"Maximum {max_guests} guests allowed. You requested {total_guests}.",
        }

    # Check if dates are changing
    dates_changing = (check_in != current_check_in or check_out != current_check_out)

    if dates_changing:
        # Get dates to check (excluding current booking's dates)
        current_dates = set(_date_range(current_check_in, current_check_out))
        new_dates = set(_date_range(check_in, check_out))

        # Only need to check dates that are new (not already booked by this reservation)
        dates_to_check = list(new_dates - current_dates)

        if dates_to_check:
            is_available, unavailable_dates = _check_dates_available(db, dates_to_check)
            if not is_available:
                error = ToolError.from_code(
                    ErrorCode.DATES_UNAVAILABLE,
                    details={"unavailable_dates": ", ".join(unavailable_dates)},
                )
                return error.model_dump()

    # Recalculate pricing if dates changed
    nights = (check_out - check_in).days
    nightly_rate, cleaning_fee = _get_pricing_for_dates(check_in, check_out)
    new_total = (nightly_rate * nights) + cleaning_fee
    old_total = int(item["total_amount"])
    price_difference = new_total - old_total

    # Build update
    now = datetime.now(timezone.utc)
    updates = {
        "check_in": check_in.isoformat(),
        "check_out": check_out.isoformat(),
        "nights": nights,
        "num_adults": num_adults,
        "num_children": num_children,
        "total_amount": new_total,
        "nightly_rate": nightly_rate,
        "updated_at": now.isoformat(),
    }

    if new_special_requests is not None:
        updates["special_requests"] = new_special_requests

    # Update reservation
    db.update_item("reservations", {"reservation_id": reservation_id}, updates)

    # If dates changed, update availability
    if dates_changing:
        # Release old dates that are no longer needed
        dates_to_release = list(current_dates - new_dates)
        for d in dates_to_release:
            db.update_item(
                "availability",
                {"date": d.isoformat()},
                {
                    "status": AvailabilityStatus.AVAILABLE.value,
                    "reservation_id": None,
                    "updated_at": now.isoformat(),
                },
            )

        # Book new dates
        dates_to_book = list(new_dates - current_dates)
        for d in dates_to_book:
            db.put_item(
                "availability",
                {
                    "date": d.isoformat(),
                    "status": AvailabilityStatus.BOOKED.value,
                    "reservation_id": reservation_id,
                    "updated_at": now.isoformat(),
                },
            )

    # Build response
    result = {
        "status": "success",
        "reservation_id": reservation_id,
        "check_in": check_in.isoformat(),
        "check_out": check_out.isoformat(),
        "nights": nights,
        "num_adults": num_adults,
        "num_children": num_children,
        "new_total_cents": new_total,
        "new_total_eur": new_total / 100,
        "old_total_cents": old_total,
        "price_difference_cents": price_difference,
        "price_difference_eur": price_difference / 100,
        "message": f"Reservation {reservation_id} has been updated. New total: €{new_total / 100:.2f}",
    }

    if price_difference > 0:
        result["message"] += f" (additional €{price_difference / 100:.2f} due)"
    elif price_difference < 0:
        result["message"] += f" (€{abs(price_difference) / 100:.2f} refund due)"

    return result


@tool
def cancel_reservation(
    reservation_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Cancel an existing reservation.

    Use this tool when a guest wants to cancel their booking.
    Refund amount depends on how far in advance the cancellation is made:
    - 30+ days before: 100% refund
    - 14-29 days before: 50% refund
    - Less than 14 days: No refund

    IMPORTANT: Cannot cancel already cancelled or completed reservations.

    Args:
        reservation_id: The reservation ID (e.g., 'RES-2025-ABCD1234')
        reason: Optional reason for cancellation

    Returns:
        Dictionary with cancellation details and refund information
    """
    logger.info("cancel_reservation called", extra={"reservation_id": reservation_id})
    db = _get_db()

    # Get existing reservation
    item = db.get_item("reservations", {"reservation_id": reservation_id})

    if not item:
        error = ToolError.from_code(
            ErrorCode.RESERVATION_NOT_FOUND,
            details={"reservation_id": reservation_id},
        )
        return error.model_dump()

    # Check if reservation can be cancelled
    current_status = item.get("status")
    if current_status == ReservationStatus.CANCELLED.value:
        error = ToolError.from_code(
            ErrorCode.UNAUTHORIZED,
            details={"reason": "Reservation has already been cancelled"},
        )
        return error.model_dump()

    if current_status == ReservationStatus.COMPLETED.value:
        error = ToolError.from_code(
            ErrorCode.UNAUTHORIZED,
            details={"reason": "Cannot cancel a completed reservation"},
        )
        return error.model_dump()

    # Parse check-in date and calculate days until arrival
    check_in = _parse_date(item["check_in"])
    check_out = _parse_date(item["check_out"])
    today = date.today()
    days_until_checkin = (check_in - today).days

    # Check if reservation is in the past
    if check_in <= today:
        error = ToolError.from_code(
            ErrorCode.UNAUTHORIZED,
            details={"reason": "Cannot cancel a reservation that has already started"},
        )
        return error.model_dump()

    # Calculate refund based on cancellation policy
    total_amount = int(item["total_amount"])

    if days_until_checkin >= 30:
        refund_percentage = 100
        refund_amount = total_amount
    elif days_until_checkin >= 14:
        refund_percentage = 50
        refund_amount = total_amount // 2
    else:
        refund_percentage = 0
        refund_amount = 0

    # Prepare transaction items
    now = datetime.now(timezone.utc)
    transact_items: list[dict[str, Any]] = []

    # Update reservation status
    transact_items.append(
        {
            "Update": {
                "TableName": db._table_name("reservations"),
                "Key": {"reservation_id": {"S": reservation_id}},
                "UpdateExpression": "SET #s = :cancelled, payment_status = :refund_status, cancellation_reason = :reason, cancelled_at = :now, refund_amount = :refund, updated_at = :now",
                "ExpressionAttributeNames": {"#s": "status"},
                "ExpressionAttributeValues": {
                    ":cancelled": {"S": ReservationStatus.CANCELLED.value},
                    ":refund_status": {"S": PaymentStatus.REFUNDED.value if refund_amount > 0 else PaymentStatus.CANCELLED.value},
                    ":reason": {"S": reason or "No reason provided"},
                    ":now": {"S": now.isoformat()},
                    ":refund": {"N": str(refund_amount)},
                },
            }
        }
    )

    # Release all booked dates
    dates_to_release = _date_range(check_in, check_out)
    for d in dates_to_release:
        transact_items.append(
            {
                "Put": {
                    "TableName": db._table_name("availability"),
                    "Item": {
                        "date": {"S": d.isoformat()},
                        "status": {"S": AvailabilityStatus.AVAILABLE.value},
                        "updated_at": {"S": now.isoformat()},
                    },
                }
            }
        )

    # Execute transaction
    success = db.transact_write(transact_items)

    if not success:
        # Use PAYMENT_FAILED as closest match for transactional failure
        error = ToolError.from_code(
            ErrorCode.PAYMENT_FAILED,
            details={"operation": "cancellation", "reason": "Transaction failed"},
        )
        return error.model_dump()

    return {
        "status": "success",
        "reservation_id": reservation_id,
        "check_in": item["check_in"],
        "check_out": item["check_out"],
        "days_until_checkin": days_until_checkin,
        "refund_percentage": refund_percentage,
        "refund_amount_cents": refund_amount,
        "refund_amount_eur": refund_amount / 100,
        "original_amount_cents": total_amount,
        "original_amount_eur": total_amount / 100,
        "cancellation_reason": reason or "No reason provided",
        "cancelled_at": now.isoformat(),
        "message": f"Reservation {reservation_id} has been cancelled. Refund: €{refund_amount / 100:.2f} ({refund_percentage}% of €{total_amount / 100:.2f}).",
    }


@tool
def get_my_reservations(auth_token: str | None = None) -> dict[str, Any]:
    """Get all reservations for the authenticated user.

    Use this tool when an authenticated guest asks about their bookings,
    such as "What are my reservations?" or "Show me my bookings".

    This tool requires the user to be authenticated. If no auth_token is
    provided or the token is invalid, returns an authentication required error.

    Args:
        auth_token: JWT token from the authenticated user's session.
                   Contains the cognito_sub claim to identify the user.

    Returns:
        Dictionary with list of user's reservations or error if not authenticated
    """
    from src.utils.jwt import extract_cognito_sub

    logger.info("get_my_reservations called")

    # Extract cognito_sub from JWT
    cognito_sub = extract_cognito_sub(auth_token)
    if not cognito_sub:
        error = ToolError.from_code(
            ErrorCode.VERIFICATION_REQUIRED,
            details={"reason": "Authentication required to view your reservations"},
        )
        return error.model_dump()

    db = _get_db()

    # Look up guest by cognito_sub
    guest = db.get_guest_by_cognito_sub(cognito_sub)
    if not guest:
        # User is authenticated but has no guest record yet
        logger.info(
            "Authenticated user has no guest record",
            extra={"cognito_sub": cognito_sub[:8] + "..."},
        )
        return {
            "status": "success",
            "reservations": [],
            "count": 0,
            "message": "You don't have any reservations yet. Would you like to make a booking?",
        }

    guest_id = guest["guest_id"]
    logger.info("Looking up reservations for guest", extra={"guest_id": guest_id})

    # Get reservations for this guest
    reservations = db.get_reservations_by_guest_id(guest_id)

    # Format reservations for response
    formatted = []
    for res in reservations:
        formatted.append({
            "reservation_id": res["reservation_id"],
            "check_in": res["check_in"],
            "check_out": res["check_out"],
            "nights": res.get("nights", 0),
            "num_adults": res.get("num_adults", 1),
            "num_children": res.get("num_children", 0),
            "total_amount_eur": int(res.get("total_amount", 0)) / 100,
            "status": res.get("status", "unknown"),
            "payment_status": res.get("payment_status", "unknown"),
        })

    if not formatted:
        return {
            "status": "success",
            "reservations": [],
            "count": 0,
            "message": "You don't have any reservations yet. Would you like to make a booking?",
        }

    return {
        "status": "success",
        "reservations": formatted,
        "count": len(formatted),
        "message": f"Found {len(formatted)} reservation(s).",
    }


@tool
def get_reservation(reservation_id: str) -> dict[str, Any]:
    """Get details of an existing reservation.

    Use this tool when a guest asks about their booking,
    wants to see reservation details, or check status.

    Args:
        reservation_id: The reservation ID (e.g., 'RES-2025-ABCD1234')

    Returns:
        Dictionary with reservation details or error if not found
    """
    logger.info("get_reservation called", extra={"reservation_id": reservation_id})
    db = _get_db()

    item = db.get_item("reservations", {"reservation_id": reservation_id})

    if not item:
        error = ToolError.from_code(
            ErrorCode.RESERVATION_NOT_FOUND,
            details={"reservation_id": reservation_id},
        )
        return error.model_dump()

    return {
        "status": "success",
        "reservation_id": item["reservation_id"],
        "check_in": item["check_in"],
        "check_out": item["check_out"],
        "nights": item["nights"],
        "num_adults": item["num_adults"],
        "num_children": item.get("num_children", 0),
        "total_amount_eur": int(item["total_amount"]) / 100,
        "reservation_status": item["status"],
        "payment_status": item["payment_status"],
        "special_requests": item.get("special_requests"),
        "created_at": item["created_at"],
        "message": f"Reservation {reservation_id}: {item['check_in']} to {item['check_out']} ({item['nights']} nights), Status: {item['status']}, Payment: {item['payment_status']}",
    }
