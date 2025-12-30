"""Unit tests for alternative date suggestions (T076, T077).

Tests the suggest_alternative_dates functionality that helps guests
find available dates when their requested dates are unavailable.
"""

import datetime as dt
from unittest.mock import MagicMock

import pytest

from src.models import Availability, AvailabilityStatus
from src.services.availability import AvailabilityService


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a mock DynamoDB service."""
    return MagicMock()


@pytest.fixture
def mock_pricing() -> MagicMock:
    """Create a mock Pricing service."""
    return MagicMock()


@pytest.fixture
def availability_service(mock_db: MagicMock, mock_pricing: MagicMock) -> AvailabilityService:
    """Create AvailabilityService with mock dependencies."""
    return AvailabilityService(mock_db, mock_pricing)


def mock_availability_data(
    mock_db: MagicMock,
    unavailable_dates: list[str],
) -> None:
    """Configure mock to return specific unavailable dates.

    Note: The service requires dates to EXIST in DynamoDB to be considered available.
    Missing dates are treated as unavailable (past dates, beyond seed range, etc.).
    This mock returns AVAILABLE status for all queried dates NOT in unavailable_dates.

    Args:
        mock_db: Mock DynamoDB service
        unavailable_dates: List of date strings (YYYY-MM-DD) that are unavailable
    """
    today = dt.date.today()

    def batch_get_side_effect(table: str, keys: list[dict]) -> list[dict]:
        """Return availability status for all queried dates.

        - Dates in unavailable_dates: BOOKED status
        - Past dates: Not returned (simulates not being seeded)
        - Future dates not in unavailable_dates: AVAILABLE status
        """
        items = []
        for key in keys:
            date_str = key["date"]
            date_obj = dt.date.fromisoformat(date_str)

            # Skip past dates (they wouldn't be in the database)
            if date_obj < today:
                continue

            if date_str in unavailable_dates:
                items.append({
                    "date": date_str,
                    "status": AvailabilityStatus.BOOKED.value,
                })
            else:
                # Future dates that aren't blocked are AVAILABLE
                items.append({
                    "date": date_str,
                    "status": AvailabilityStatus.AVAILABLE.value,
                })
        return items

    mock_db.batch_get.side_effect = batch_get_side_effect


class TestSuggestAlternativeDates:
    """Tests for suggest_alternative_dates method."""

    def test_suggests_earlier_dates_when_available(
        self,
        availability_service: AvailabilityService,
        mock_db: MagicMock,
    ) -> None:
        """Should suggest dates a few days earlier when available."""
        # Use dates far enough in the future for earlier suggestions to work
        # (earlier dates must be >= today)
        today = dt.date.today()
        start = today + dt.timedelta(days=20)  # 20 days from now
        end = start + dt.timedelta(days=5)  # 5-night stay

        # Block the requested dates
        blocked = [(start + dt.timedelta(days=i)).isoformat() for i in range(5)]
        mock_availability_data(mock_db, blocked)

        # When: Requesting alternatives
        suggestions = availability_service.suggest_alternative_dates(
            requested_start=start,
            requested_end=end,
            search_window_days=10,
            max_suggestions=5,
        )

        # Then: Should suggest earlier dates (since we're 20 days out)
        assert len(suggestions) > 0
        # At least one suggestion should be for earlier dates
        earlier_suggestions = [s for s in suggestions if s["offset_days"] < 0]
        assert len(earlier_suggestions) > 0

    def test_suggests_later_dates_when_available(
        self,
        availability_service: AvailabilityService,
        mock_db: MagicMock,
    ) -> None:
        """Should suggest dates a few days later when available."""
        # Use future dates (30 days from now)
        today = dt.date.today()
        start = today + dt.timedelta(days=30)

        # Block the requested dates
        blocked = [(start + dt.timedelta(days=i)).isoformat() for i in range(5)]
        mock_availability_data(mock_db, blocked)

        # When: Requesting alternatives
        suggestions = availability_service.suggest_alternative_dates(
            requested_start=start,
            requested_end=start + dt.timedelta(days=5),
            search_window_days=7,
            max_suggestions=3,
        )

        # Then: Should include some later date suggestions
        assert len(suggestions) > 0
        later_suggestions = [s for s in suggestions if s["offset_days"] > 0]
        assert len(later_suggestions) > 0

    def test_returns_empty_list_when_no_alternatives(
        self,
        availability_service: AvailabilityService,
        mock_db: MagicMock,
    ) -> None:
        """Should return empty list when entire search window is booked."""
        # Use future dates
        today = dt.date.today()
        start = today + dt.timedelta(days=30)

        # Block the entire search window (30 days before and after)
        # to ensure no alternatives can be found
        blocked = []
        for i in range(-30, 50):  # Wide range to cover search window
            d = start + dt.timedelta(days=i)
            if d >= today:  # Can't block past dates anyway
                blocked.append(d.isoformat())
        mock_availability_data(mock_db, blocked)

        # When: Requesting alternatives with small search window
        suggestions = availability_service.suggest_alternative_dates(
            requested_start=start,
            requested_end=start + dt.timedelta(days=5),
            search_window_days=7,  # Only look 7 days in each direction
            max_suggestions=3,
        )

        # Then: Should return empty list (no alternatives found within window)
        assert suggestions == []

    def test_respects_max_suggestions_limit(
        self,
        availability_service: AvailabilityService,
        mock_db: MagicMock,
    ) -> None:
        """Should not return more than max_suggestions alternatives."""
        # Use future dates
        today = dt.date.today()
        start = today + dt.timedelta(days=30)

        # Block requested dates so we get suggestions
        blocked = [(start + dt.timedelta(days=i)).isoformat() for i in range(3)]
        mock_availability_data(mock_db, blocked)

        # When: Requesting with limit of 2
        suggestions = availability_service.suggest_alternative_dates(
            requested_start=start,
            requested_end=start + dt.timedelta(days=3),
            search_window_days=14,
            max_suggestions=2,
        )

        # Then: Should return at most 2 suggestions
        assert len(suggestions) <= 2

    def test_suggestions_preserve_stay_duration(
        self,
        availability_service: AvailabilityService,
        mock_db: MagicMock,
    ) -> None:
        """Suggestions should have same number of nights as original request."""
        # Use future dates
        today = dt.date.today()
        start = today + dt.timedelta(days=30)

        # Block first 2 days of requested range
        blocked = [(start + dt.timedelta(days=i)).isoformat() for i in range(2)]
        mock_availability_data(mock_db, blocked)

        # When: Requesting 5-night stay alternatives
        requested_nights = 5
        suggestions = availability_service.suggest_alternative_dates(
            requested_start=start,
            requested_end=start + dt.timedelta(days=5),
            search_window_days=7,
            max_suggestions=3,
        )

        # Then: All suggestions should be for 5 nights
        for suggestion in suggestions:
            assert suggestion["nights"] == requested_nights

    def test_sorts_suggestions_by_proximity(
        self,
        availability_service: AvailabilityService,
        mock_db: MagicMock,
    ) -> None:
        """Suggestions should be sorted by closeness to original dates."""
        # Use future dates
        today = dt.date.today()
        start = today + dt.timedelta(days=30)

        # Block only the first date
        blocked = [start.isoformat()]
        mock_availability_data(mock_db, blocked)

        # When: Requesting alternatives
        suggestions = availability_service.suggest_alternative_dates(
            requested_start=start,
            requested_end=start + dt.timedelta(days=3),
            search_window_days=7,
            max_suggestions=5,
        )

        # Then: Suggestions should be sorted by absolute offset
        offsets = [abs(s["offset_days"]) for s in suggestions]
        assert offsets == sorted(offsets)


class TestSuggestAlternativeDatesEdgeCases:
    """Edge case tests for alternative date suggestions."""

    def test_does_not_suggest_past_dates(
        self,
        availability_service: AvailabilityService,
        mock_db: MagicMock,
    ) -> None:
        """Should not suggest dates in the past."""
        # Given: All dates available but request is for near-term dates
        mock_availability_data(mock_db, [])
        today = dt.date.today()

        # When: Requesting alternatives for tomorrow
        start = today + dt.timedelta(days=1)
        end = start + dt.timedelta(days=3)
        suggestions = availability_service.suggest_alternative_dates(
            requested_start=start,
            requested_end=end,
            search_window_days=7,
            max_suggestions=3,
        )

        # Then: No suggestions should have dates before today
        for suggestion in suggestions:
            check_in = dt.date.fromisoformat(suggestion["check_in"])
            assert check_in >= today

    def test_handles_single_night_stay(
        self,
        availability_service: AvailabilityService,
        mock_db: MagicMock,
    ) -> None:
        """Should handle single night stay requests."""
        # Use future dates
        today = dt.date.today()
        start = today + dt.timedelta(days=30)

        # Block the requested single night
        mock_availability_data(mock_db, [start.isoformat()])

        # When: Requesting 1-night alternatives
        suggestions = availability_service.suggest_alternative_dates(
            requested_start=start,
            requested_end=start + dt.timedelta(days=1),
            search_window_days=7,
            max_suggestions=3,
        )

        # Then: Should return valid 1-night suggestions
        assert len(suggestions) > 0
        for suggestion in suggestions:
            assert suggestion["nights"] == 1

    def test_includes_direction_in_response(
        self,
        availability_service: AvailabilityService,
        mock_db: MagicMock,
    ) -> None:
        """Suggestions should include direction indicator."""
        # Use future dates
        today = dt.date.today()
        start = today + dt.timedelta(days=30)

        # Given: Some dates unavailable
        mock_availability_data(mock_db, [start.isoformat()])

        # When: Requesting alternatives
        suggestions = availability_service.suggest_alternative_dates(
            requested_start=start,
            requested_end=start + dt.timedelta(days=3),
            search_window_days=7,
            max_suggestions=5,
        )

        # Then: Each suggestion should have direction field
        for suggestion in suggestions:
            assert "direction" in suggestion
            assert suggestion["direction"] in ["earlier", "later"]
            # Direction should match offset sign
            if suggestion["offset_days"] < 0:
                assert suggestion["direction"] == "earlier"
            else:
                assert suggestion["direction"] == "later"


class TestSuggestAlternativeDatesIntegration:
    """Integration-style tests for the complete flow."""

    def test_multiple_blocked_ranges(
        self,
        availability_service: AvailabilityService,
        mock_db: MagicMock,
    ) -> None:
        """Should find gaps between multiple blocked periods."""
        # Use future dates
        today = dt.date.today()
        base = today + dt.timedelta(days=30)  # Base date 30 days from now

        # Given: Two separate blocked periods (5 days each, with a 5-day gap)
        # Block 1: base to base+4 (days 0-4)
        # Gap: base+5 to base+9 (days 5-9) - available
        # Block 2: base+10 to base+14 (days 10-14)
        blocked = (
            # Block 1: 5 consecutive days
            [(base + dt.timedelta(days=i)).isoformat() for i in range(5)]
            +
            # Block 2: 5 consecutive days starting at day 10
            [(base + dt.timedelta(days=10 + i)).isoformat() for i in range(5)]
        )
        mock_availability_data(mock_db, blocked)

        # When: Requesting alternatives for dates in block 1
        # Request a 5-night stay starting at base+2 (falls in block 1)
        suggestions = availability_service.suggest_alternative_dates(
            requested_start=base + dt.timedelta(days=2),  # Falls in block 1
            requested_end=base + dt.timedelta(days=7),  # 5 nights
            search_window_days=10,
            max_suggestions=3,
        )

        # Then: Should find the gap between blocks
        # There should be suggestions outside blocked periods
        assert len(suggestions) > 0
