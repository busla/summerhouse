"""Availability service for date management."""

import datetime as dt
from typing import TYPE_CHECKING, Any

from src.models import Availability, AvailabilityResponse, AvailabilityStatus

if TYPE_CHECKING:
    from .dynamodb import DynamoDBService
    from .pricing import PricingService


class AvailabilityService:
    """Service for availability checking and management."""

    TABLE = "availability"

    def __init__(
        self,
        db: "DynamoDBService",
        pricing: "PricingService",
    ) -> None:
        """Initialize availability service.

        Args:
            db: DynamoDB service instance
            pricing: Pricing service instance
        """
        self.db = db
        self.pricing = pricing

    def get_date(self, date: dt.date) -> Availability | None:
        """Get availability for a single date.

        Args:
            date: Date to check

        Returns:
            Availability or None if not found
        """
        item = self.db.get_item(self.TABLE, {"date": date.isoformat()})
        if not item:
            return None
        return self._item_to_availability(item)

    def get_range(
        self,
        start_date: dt.date,
        end_date: dt.date,
    ) -> list[Availability]:
        """Get availability for a date range.

        Args:
            start_date: Start of range
            end_date: End of range (exclusive - check-out date)

        Returns:
            List of Availability objects
        """
        dates = self._date_range(start_date, end_date)
        keys = [{"date": d.isoformat()} for d in dates]
        items = self.db.batch_get(self.TABLE, keys)

        # Create map for quick lookup
        item_map = {item["date"]: item for item in items}

        today = dt.date.today()
        result = []
        for d in dates:
            date_str = d.isoformat()
            if date_str in item_map:
                result.append(self._item_to_availability(item_map[date_str]))
            else:
                # Date not in DB - treat as UNAVAILABLE (not bookable)
                # This handles: past dates, dates beyond seed range, or any gap
                # Past dates are definitely not bookable
                # Future dates without records haven't been seeded yet
                result.append(
                    Availability(
                        date=d,
                        status=AvailabilityStatus.BLOCKED,
                        block_reason="past_date" if d < today else "not_configured",
                        updated_at=dt.datetime.now(dt.UTC),
                    )
                )

        return result

    def check_availability(
        self,
        start_date: dt.date,
        end_date: dt.date,
    ) -> AvailabilityResponse:
        """Check if dates are available and calculate price.

        Args:
            start_date: Check-in date
            end_date: Check-out date

        Returns:
            AvailabilityResponse with availability and pricing
        """
        dates_to_check = self.get_range(start_date, end_date)

        unavailable = [
            a.date
            for a in dates_to_check
            if a.status != AvailabilityStatus.AVAILABLE
        ]

        is_available = len(unavailable) == 0
        total_nights = (end_date - start_date).days

        # Get pricing
        price_calc = self.pricing.calculate_price(start_date, end_date)

        return AvailabilityResponse(
            start_date=start_date,
            end_date=end_date,
            is_available=is_available,
            unavailable_dates=unavailable,
            total_nights=total_nights,
            nightly_rate=price_calc.nightly_rate if price_calc else 0,
            cleaning_fee=price_calc.cleaning_fee if price_calc else 0,
            total_amount=price_calc.total_amount if price_calc else 0,
        )

    def book_dates(
        self,
        start_date: dt.date,
        end_date: dt.date,
        reservation_id: str,
    ) -> bool:
        """Atomically book dates for a reservation.

        Uses DynamoDB transactions to prevent double-booking.

        Args:
            start_date: Check-in date
            end_date: Check-out date (exclusive)
            reservation_id: Reservation ID to associate

        Returns:
            True if booked successfully, False if dates unavailable
        """
        dates = self._date_range(start_date, end_date)
        table_name = self.db._table_name(self.TABLE)
        now = dt.datetime.now(dt.UTC).isoformat()

        # Build transaction items with conditional writes
        transact_items = [
            {
                "Update": {
                    "TableName": table_name,
                    "Key": {"date": {"S": d.isoformat()}},
                    "UpdateExpression": "SET #s = :booked, reservation_id = :rid, updated_at = :now",
                    "ConditionExpression": "#s = :available OR attribute_not_exists(#s)",
                    "ExpressionAttributeNames": {"#s": "status"},
                    "ExpressionAttributeValues": {
                        ":booked": {"S": AvailabilityStatus.BOOKED.value},
                        ":available": {"S": AvailabilityStatus.AVAILABLE.value},
                        ":rid": {"S": reservation_id},
                        ":now": {"S": now},
                    },
                }
            }
            for d in dates
        ]

        return self.db.transact_write(transact_items)

    def release_dates(
        self,
        start_date: dt.date,
        end_date: dt.date,
        reservation_id: str,
    ) -> bool:
        """Release booked dates (for cancellation).

        Only releases dates if they're booked by the given reservation.

        Args:
            start_date: Check-in date
            end_date: Check-out date (exclusive)
            reservation_id: Reservation ID that holds the booking

        Returns:
            True if released successfully
        """
        dates = self._date_range(start_date, end_date)
        table_name = self.db._table_name(self.TABLE)
        now = dt.datetime.now(dt.UTC).isoformat()

        transact_items = [
            {
                "Update": {
                    "TableName": table_name,
                    "Key": {"date": {"S": d.isoformat()}},
                    "UpdateExpression": (
                        "SET #s = :available, updated_at = :now "
                        "REMOVE reservation_id"
                    ),
                    "ConditionExpression": "reservation_id = :rid",
                    "ExpressionAttributeNames": {"#s": "status"},
                    "ExpressionAttributeValues": {
                        ":available": {"S": AvailabilityStatus.AVAILABLE.value},
                        ":rid": {"S": reservation_id},
                        ":now": {"S": now},
                    },
                }
            }
            for d in dates
        ]

        return self.db.transact_write(transact_items)

    def block_dates(
        self,
        start_date: dt.date,
        end_date: dt.date,
        reason: str,
    ) -> bool:
        """Manually block dates (owner maintenance, etc).

        Args:
            start_date: Start of block
            end_date: End of block (exclusive)
            reason: Reason for block

        Returns:
            True if blocked successfully
        """
        dates = self._date_range(start_date, end_date)
        table_name = self.db._table_name(self.TABLE)
        now = dt.datetime.now(dt.UTC).isoformat()

        transact_items = [
            {
                "Update": {
                    "TableName": table_name,
                    "Key": {"date": {"S": d.isoformat()}},
                    "UpdateExpression": (
                        "SET #s = :blocked, block_reason = :reason, updated_at = :now"
                    ),
                    "ConditionExpression": "#s = :available OR attribute_not_exists(#s)",
                    "ExpressionAttributeNames": {"#s": "status"},
                    "ExpressionAttributeValues": {
                        ":blocked": {"S": AvailabilityStatus.BLOCKED.value},
                        ":available": {"S": AvailabilityStatus.AVAILABLE.value},
                        ":reason": {"S": reason},
                        ":now": {"S": now},
                    },
                }
            }
            for d in dates
        ]

        return self.db.transact_write(transact_items)

    def _date_range(
        self,
        start: dt.date,
        end: dt.date,
    ) -> list[dt.date]:
        """Generate list of dates in range (end exclusive)."""
        return [
            start + dt.timedelta(days=i)
            for i in range((end - start).days)
        ]

    def suggest_alternative_dates(
        self,
        requested_start: dt.date,
        requested_end: dt.date,
        search_window_days: int = 14,
        max_suggestions: int = 3,
    ) -> list[dict[str, Any]]:
        """Find alternative available date ranges near the requested dates.

        Searches before and after the requested period to find available
        windows that match the requested stay duration.

        IMPORTANT: Only suggests dates that are VERIFIED available in DynamoDB.
        Dates not in DynamoDB (past dates, beyond seed range) are treated as unavailable.

        Args:
            requested_start: Originally requested check-in date
            requested_end: Originally requested check-out date
            search_window_days: How many days before/after to search
            max_suggestions: Maximum number of alternatives to return

        Returns:
            List of alternative date ranges with availability info
        """
        requested_nights = (requested_end - requested_start).days
        suggestions: list[dict[str, Any]] = []

        # Search window: X days before to X days after the requested period
        search_start = requested_start - dt.timedelta(days=search_window_days)
        search_end = requested_end + dt.timedelta(days=search_window_days)

        # Don't search in the past
        today = dt.date.today()
        if search_start < today:
            search_start = today

        # Get all availability data for the search window
        all_dates = self._date_range(search_start, search_end)
        keys = [{"date": d.isoformat()} for d in all_dates]
        items = self.db.batch_get(self.TABLE, keys)

        # Build lookup of AVAILABLE dates (only dates that exist AND are available)
        # Dates not in DynamoDB are NOT considered available (past dates, beyond seed range)
        available_dates: set[dt.date] = set()
        for item in items:
            if item.get("status") == AvailabilityStatus.AVAILABLE.value:
                available_dates.add(dt.date.fromisoformat(item["date"]))

        # Find consecutive available windows
        def is_window_available(start: dt.date, nights: int) -> bool:
            """Check if all dates in window are VERIFIED available.

            A date is only available if it EXISTS in DynamoDB with AVAILABLE status.
            Missing dates are NOT available (past dates, beyond seed range, gaps).
            """
            for i in range(nights):
                check_date = start + dt.timedelta(days=i)
                # Date must be in available_dates set (exists AND is available)
                if check_date not in available_dates:
                    return False
            return True

        # Try windows before and after, alternating
        checked_starts: set[dt.date] = set()

        # Strategy: Check dates closest to the original request first
        # First, try shifting the start date earlier
        for offset in range(1, search_window_days + 1):
            if len(suggestions) >= max_suggestions:
                break

            # Try earlier start
            earlier_start = requested_start - dt.timedelta(days=offset)
            if earlier_start >= today and earlier_start not in checked_starts:
                checked_starts.add(earlier_start)
                if is_window_available(earlier_start, requested_nights):
                    earlier_end = earlier_start + dt.timedelta(days=requested_nights)
                    suggestions.append({
                        "check_in": earlier_start.isoformat(),
                        "check_out": earlier_end.isoformat(),
                        "nights": requested_nights,
                        "offset_days": -offset,
                        "direction": "earlier",
                    })

            # Try later start
            later_start = requested_start + dt.timedelta(days=offset)
            if later_start not in checked_starts and len(suggestions) < max_suggestions:
                checked_starts.add(later_start)
                if is_window_available(later_start, requested_nights):
                    later_end = later_start + dt.timedelta(days=requested_nights)
                    suggestions.append({
                        "check_in": later_start.isoformat(),
                        "check_out": later_end.isoformat(),
                        "nights": requested_nights,
                        "offset_days": offset,
                        "direction": "later",
                    })

        # Sort by absolute offset (closest alternatives first)
        suggestions.sort(key=lambda s: abs(s["offset_days"]))

        return suggestions[:max_suggestions]

    def _item_to_availability(self, item: dict[str, Any]) -> Availability:
        """Convert DynamoDB item to Availability model."""
        return Availability(
            date=dt.date.fromisoformat(item["date"]),
            status=AvailabilityStatus(item["status"]),
            reservation_id=item.get("reservation_id"),
            block_reason=item.get("block_reason"),
            updated_at=dt.datetime.fromisoformat(item["updated_at"]),
        )
