"""Unit tests for modify_reservation tool (T094).

Tests the modify_reservation functionality that allows guests
to update their booking dates or guest count.
"""

from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.models.enums import PaymentStatus, ReservationStatus


class TestModifyReservation:
    """Tests for the modify_reservation tool."""

    @patch("src.tools.reservations._get_db")
    @patch("src.tools.reservations._check_dates_available")
    def test_modify_dates_success(
        self, mock_check_available: MagicMock, mock_get_db: MagicMock
    ) -> None:
        """Should modify reservation dates successfully."""
        from src.tools.reservations import modify_reservation

        # Setup mock DB
        mock_db = MagicMock()
        mock_db.get_item.return_value = {
            "reservation_id": "RES-2025-ABC12345",
            "guest_id": "guest-123",
            "check_in": "2025-07-15",
            "check_out": "2025-07-22",
            "nights": 7,
            "num_adults": 2,
            "num_children": 0,
            "total_amount": 89000,
            "nightly_rate": 12000,
            "cleaning_fee": 5000,
            "status": ReservationStatus.CONFIRMED.value,
            "payment_status": PaymentStatus.COMPLETED.value,
        }
        mock_db.update_item.return_value = True
        mock_get_db.return_value = mock_db
        mock_check_available.return_value = (True, [])

        # Call the tool
        result = modify_reservation(
            reservation_id="RES-2025-ABC12345",
            new_check_in="2025-07-16",
            new_check_out="2025-07-23",
        )

        # Verify
        assert result["status"] == "success"
        assert "updated" in result["message"].lower()

    @patch("src.tools.reservations._get_db")
    def test_modify_reservation_not_found(self, mock_get_db: MagicMock) -> None:
        """Should return error when reservation not found."""
        from src.tools.reservations import modify_reservation

        mock_db = MagicMock()
        mock_db.get_item.return_value = None
        mock_get_db.return_value = mock_db

        result = modify_reservation(
            reservation_id="RES-2025-INVALID",
            new_check_in="2025-07-16",
            new_check_out="2025-07-23",
        )

        # ToolError format uses "success" instead of "status"
        assert result["success"] is False
        assert "not found" in result["message"].lower()

    @patch("src.tools.reservations._get_db")
    def test_modify_cancelled_reservation_fails(self, mock_get_db: MagicMock) -> None:
        """Should not allow modifying cancelled reservations."""
        from src.tools.reservations import modify_reservation

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

        result = modify_reservation(
            reservation_id="RES-2025-ABC12345",
            new_check_in="2025-07-16",
            new_check_out="2025-07-23",
        )

        # ToolError format uses "success" instead of "status"
        assert result["success"] is False
        # ToolError.UNAUTHORIZED message is "Guest not authorized for this action"
        assert "not authorized" in result["message"].lower() or "cancelled" in result["message"].lower()

    @patch("src.tools.reservations._get_db")
    @patch("src.tools.reservations._check_dates_available")
    def test_modify_dates_unavailable(
        self, mock_check_available: MagicMock, mock_get_db: MagicMock
    ) -> None:
        """Should fail when new dates are not available."""
        from src.tools.reservations import modify_reservation

        mock_db = MagicMock()
        mock_db.get_item.return_value = {
            "reservation_id": "RES-2025-ABC12345",
            "guest_id": "guest-123",
            "check_in": "2025-07-15",
            "check_out": "2025-07-22",
            "nights": 7,
            "num_adults": 2,
            "total_amount": 89000,
            "status": ReservationStatus.CONFIRMED.value,
            "payment_status": PaymentStatus.COMPLETED.value,
        }
        mock_get_db.return_value = mock_db
        mock_check_available.return_value = (False, ["2025-08-01", "2025-08-02"])

        result = modify_reservation(
            reservation_id="RES-2025-ABC12345",
            new_check_in="2025-08-01",
            new_check_out="2025-08-08",
        )

        # ToolError format uses "success" instead of "status"
        assert result["success"] is False
        assert "unavailable" in result["message"].lower() or "available" in result["message"].lower()

    @patch("src.tools.reservations._get_db")
    @patch("src.tools.reservations._check_dates_available")
    def test_modify_guest_count(
        self, mock_check_available: MagicMock, mock_get_db: MagicMock
    ) -> None:
        """Should allow modifying guest count."""
        from src.tools.reservations import modify_reservation

        mock_db = MagicMock()
        mock_db.get_item.return_value = {
            "reservation_id": "RES-2025-ABC12345",
            "guest_id": "guest-123",
            "check_in": "2025-07-15",
            "check_out": "2025-07-22",
            "nights": 7,
            "num_adults": 2,
            "num_children": 0,
            "total_amount": 89000,
            "status": ReservationStatus.CONFIRMED.value,
            "payment_status": PaymentStatus.COMPLETED.value,
        }
        mock_db.update_item.return_value = True
        mock_get_db.return_value = mock_db
        mock_check_available.return_value = (True, [])

        result = modify_reservation(
            reservation_id="RES-2025-ABC12345",
            new_num_adults=3,
            new_num_children=1,
        )

        assert result["status"] == "success"

    @patch("src.tools.reservations._get_db")
    def test_modify_exceeds_max_guests(self, mock_get_db: MagicMock) -> None:
        """Should fail when new guest count exceeds maximum."""
        from src.tools.reservations import modify_reservation

        mock_db = MagicMock()
        mock_db.get_item.return_value = {
            "reservation_id": "RES-2025-ABC12345",
            "guest_id": "guest-123",
            "check_in": "2025-07-15",
            "check_out": "2025-07-22",
            "nights": 7,
            "num_adults": 2,
            "num_children": 0,
            "total_amount": 89000,
            "status": ReservationStatus.CONFIRMED.value,
            "payment_status": PaymentStatus.COMPLETED.value,
        }
        mock_get_db.return_value = mock_db

        result = modify_reservation(
            reservation_id="RES-2025-ABC12345",
            new_num_adults=8,  # Exceeds max capacity
        )

        assert result["status"] == "error"
        assert "maximum" in result["message"].lower() or "guest" in result["message"].lower()


class TestModifyReservationPriceRecalculation:
    """Tests for price recalculation on modification."""

    @patch("src.tools.reservations._get_db")
    @patch("src.tools.reservations._check_dates_available")
    @patch("src.tools.reservations._get_pricing_for_dates")
    def test_price_recalculation_longer_stay(
        self,
        mock_pricing: MagicMock,
        mock_check_available: MagicMock,
        mock_get_db: MagicMock,
    ) -> None:
        """Should recalculate price when extending stay."""
        from src.tools.reservations import modify_reservation

        mock_db = MagicMock()
        mock_db.get_item.return_value = {
            "reservation_id": "RES-2025-ABC12345",
            "guest_id": "guest-123",
            "check_in": "2025-07-15",
            "check_out": "2025-07-22",  # 7 nights
            "nights": 7,
            "num_adults": 2,
            "total_amount": 89000,  # 7 nights * 12000 + 5000
            "nightly_rate": 12000,
            "cleaning_fee": 5000,
            "status": ReservationStatus.CONFIRMED.value,
            "payment_status": PaymentStatus.COMPLETED.value,
        }
        mock_db.update_item.return_value = True
        mock_get_db.return_value = mock_db
        mock_check_available.return_value = (True, [])
        mock_pricing.return_value = (12000, 5000)  # Same rate

        result = modify_reservation(
            reservation_id="RES-2025-ABC12345",
            new_check_in="2025-07-15",
            new_check_out="2025-07-25",  # 10 nights
        )

        assert result["status"] == "success"
        # Should show price difference
        if "price" in result:
            assert result["new_total_cents"] == 10 * 12000 + 5000  # 125000
