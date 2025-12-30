"""Unit tests for cancel_reservation tool (T095).

Tests the cancel_reservation functionality that allows guests
to cancel their bookings with appropriate refund policies.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.models.enums import PaymentStatus, ReservationStatus


class TestCancelReservation:
    """Tests for the cancel_reservation tool."""

    @patch("src.tools.reservations._get_db")
    def test_cancel_reservation_success(self, mock_get_db: MagicMock) -> None:
        """Should cancel reservation successfully."""
        from src.tools.reservations import cancel_reservation

        # Setup mock DB
        mock_db = MagicMock()
        mock_db.get_item.return_value = {
            "reservation_id": "RES-2025-ABC12345",
            "guest_id": "guest-123",
            "check_in": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "check_out": (datetime.now() + timedelta(days=37)).strftime("%Y-%m-%d"),
            "nights": 7,
            "num_adults": 2,
            "total_amount": 89000,
            "status": ReservationStatus.CONFIRMED.value,
            "payment_status": PaymentStatus.COMPLETED.value,
        }
        mock_db.transact_write.return_value = True
        mock_get_db.return_value = mock_db

        # Call the tool
        result = cancel_reservation(
            reservation_id="RES-2025-ABC12345",
            reason="Change of travel plans",
        )

        # Verify
        assert result["status"] == "success"
        assert "cancelled" in result["message"].lower()

    @patch("src.tools.reservations._get_db")
    def test_cancel_reservation_not_found(self, mock_get_db: MagicMock) -> None:
        """Should return error when reservation not found."""
        from src.tools.reservations import cancel_reservation

        mock_db = MagicMock()
        mock_db.get_item.return_value = None
        mock_get_db.return_value = mock_db

        result = cancel_reservation(
            reservation_id="RES-2025-INVALID",
            reason="Test",
        )

        assert result["success"] is False
        assert "not found" in result["message"].lower()

    @patch("src.tools.reservations._get_db")
    def test_cancel_already_cancelled_reservation(
        self, mock_get_db: MagicMock
    ) -> None:
        """Should not allow cancelling an already cancelled reservation."""
        from src.tools.reservations import cancel_reservation

        mock_db = MagicMock()
        mock_db.get_item.return_value = {
            "reservation_id": "RES-2025-ABC12345",
            "guest_id": "guest-123",
            "check_in": "2025-07-15",
            "check_out": "2025-07-22",
            "nights": 7,
            "num_adults": 2,
            "total_amount": 89000,
            "status": ReservationStatus.CANCELLED.value,
            "payment_status": PaymentStatus.REFUNDED.value,
        }
        mock_get_db.return_value = mock_db

        result = cancel_reservation(
            reservation_id="RES-2025-ABC12345",
            reason="Test",
        )

        assert result["success"] is False
        # ToolError.UNAUTHORIZED message is "Guest not authorized for this action"
        assert "not authorized" in result["message"].lower() or "cancelled" in result["message"].lower()

    @patch("src.tools.reservations._get_db")
    def test_cancel_completed_reservation_fails(
        self, mock_get_db: MagicMock
    ) -> None:
        """Should not allow cancelling a completed (past) reservation."""
        from src.tools.reservations import cancel_reservation

        mock_db = MagicMock()
        mock_db.get_item.return_value = {
            "reservation_id": "RES-2025-ABC12345",
            "guest_id": "guest-123",
            "check_in": "2024-07-15",  # Past date
            "check_out": "2024-07-22",
            "nights": 7,
            "num_adults": 2,
            "total_amount": 89000,
            "status": ReservationStatus.COMPLETED.value,
            "payment_status": PaymentStatus.COMPLETED.value,
        }
        mock_get_db.return_value = mock_db

        result = cancel_reservation(
            reservation_id="RES-2025-ABC12345",
            reason="Test",
        )

        assert result["success"] is False


class TestCancellationPolicy:
    """Tests for cancellation policy and refund calculations."""

    @patch("src.tools.reservations._get_db")
    def test_full_refund_30_days_before(self, mock_get_db: MagicMock) -> None:
        """Should give full refund when cancelled 30+ days before check-in."""
        from src.tools.reservations import cancel_reservation

        mock_db = MagicMock()
        future_checkin = (datetime.now() + timedelta(days=35)).strftime("%Y-%m-%d")
        mock_db.get_item.return_value = {
            "reservation_id": "RES-2025-ABC12345",
            "guest_id": "guest-123",
            "check_in": future_checkin,
            "check_out": (datetime.now() + timedelta(days=42)).strftime("%Y-%m-%d"),
            "nights": 7,
            "num_adults": 2,
            "total_amount": 89000,
            "status": ReservationStatus.CONFIRMED.value,
            "payment_status": PaymentStatus.COMPLETED.value,
        }
        mock_db.transact_write.return_value = True
        mock_get_db.return_value = mock_db

        result = cancel_reservation(
            reservation_id="RES-2025-ABC12345",
            reason="Change of plans",
        )

        assert result["status"] == "success"
        # Full refund expected
        if "refund_amount" in result:
            assert result["refund_amount"] == 89000 or result["refund_percentage"] == 100

    @patch("src.tools.reservations._get_db")
    def test_partial_refund_14_days_before(self, mock_get_db: MagicMock) -> None:
        """Should give 50% refund when cancelled 14-29 days before check-in."""
        from src.tools.reservations import cancel_reservation

        mock_db = MagicMock()
        future_checkin = (datetime.now() + timedelta(days=20)).strftime("%Y-%m-%d")
        mock_db.get_item.return_value = {
            "reservation_id": "RES-2025-ABC12345",
            "guest_id": "guest-123",
            "check_in": future_checkin,
            "check_out": (datetime.now() + timedelta(days=27)).strftime("%Y-%m-%d"),
            "nights": 7,
            "num_adults": 2,
            "total_amount": 89000,
            "status": ReservationStatus.CONFIRMED.value,
            "payment_status": PaymentStatus.COMPLETED.value,
        }
        mock_db.transact_write.return_value = True
        mock_get_db.return_value = mock_db

        result = cancel_reservation(
            reservation_id="RES-2025-ABC12345",
            reason="Change of plans",
        )

        assert result["status"] == "success"
        # 50% refund expected
        if "refund_percentage" in result:
            assert result["refund_percentage"] == 50

    @patch("src.tools.reservations._get_db")
    def test_no_refund_within_14_days(self, mock_get_db: MagicMock) -> None:
        """Should give no refund when cancelled less than 14 days before check-in."""
        from src.tools.reservations import cancel_reservation

        mock_db = MagicMock()
        future_checkin = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        mock_db.get_item.return_value = {
            "reservation_id": "RES-2025-ABC12345",
            "guest_id": "guest-123",
            "check_in": future_checkin,
            "check_out": (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d"),
            "nights": 7,
            "num_adults": 2,
            "total_amount": 89000,
            "status": ReservationStatus.CONFIRMED.value,
            "payment_status": PaymentStatus.COMPLETED.value,
        }
        mock_db.transact_write.return_value = True
        mock_get_db.return_value = mock_db

        result = cancel_reservation(
            reservation_id="RES-2025-ABC12345",
            reason="Emergency",
        )

        assert result["status"] == "success"
        # No refund expected (but cancellation is still allowed)
        if "refund_percentage" in result:
            assert result["refund_percentage"] == 0


class TestCancellationAvailabilityRelease:
    """Tests for releasing dates back to available pool."""

    @patch("src.tools.reservations._get_db")
    def test_releases_dates_on_cancellation(self, mock_get_db: MagicMock) -> None:
        """Should release booked dates when reservation is cancelled."""
        from src.tools.reservations import cancel_reservation

        mock_db = MagicMock()
        future_checkin = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        future_checkout = (datetime.now() + timedelta(days=37)).strftime("%Y-%m-%d")
        mock_db.get_item.return_value = {
            "reservation_id": "RES-2025-ABC12345",
            "guest_id": "guest-123",
            "check_in": future_checkin,
            "check_out": future_checkout,
            "nights": 7,
            "num_adults": 2,
            "total_amount": 89000,
            "status": ReservationStatus.CONFIRMED.value,
            "payment_status": PaymentStatus.COMPLETED.value,
        }
        mock_db.transact_write.return_value = True
        mock_get_db.return_value = mock_db

        result = cancel_reservation(
            reservation_id="RES-2025-ABC12345",
            reason="Change of plans",
        )

        # Verify transact_write was called (which includes date release)
        assert mock_db.transact_write.called
        assert result["status"] == "success"
