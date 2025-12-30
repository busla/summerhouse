"""Unit tests for get_reservation tool (T093).

Tests the get_reservation functionality that retrieves
existing booking details for guests.
"""

from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.models.enums import PaymentStatus, ReservationStatus


class TestGetReservation:
    """Tests for the get_reservation tool."""

    @patch("src.tools.reservations._get_db")
    def test_get_reservation_success(self, mock_get_db: MagicMock) -> None:
        """Should return reservation details successfully."""
        from src.tools.reservations import get_reservation

        # Setup mock
        mock_db = MagicMock()
        mock_db.get_item.return_value = {
            "reservation_id": "RES-2025-ABC12345",
            "guest_id": "guest-123",
            "check_in": "2025-07-15",
            "check_out": "2025-07-22",
            "nights": 7,
            "num_adults": 2,
            "num_children": 1,
            "total_amount": 89000,  # cents
            "status": ReservationStatus.CONFIRMED.value,
            "payment_status": PaymentStatus.COMPLETED.value,
            "special_requests": "Early check-in please",
            "created_at": "2025-06-01T10:00:00Z",
        }
        mock_get_db.return_value = mock_db

        # Call the tool
        result = get_reservation("RES-2025-ABC12345")

        # Verify
        assert result["status"] == "success"
        assert result["reservation_id"] == "RES-2025-ABC12345"
        assert result["check_in"] == "2025-07-15"
        assert result["check_out"] == "2025-07-22"
        assert result["nights"] == 7
        assert result["num_adults"] == 2
        assert result["num_children"] == 1
        assert result["total_amount_eur"] == 890.0

    @patch("src.tools.reservations._get_db")
    def test_get_reservation_not_found(self, mock_get_db: MagicMock) -> None:
        """Should return error when reservation not found."""
        from src.tools.reservations import get_reservation

        # Setup mock to return None (not found)
        mock_db = MagicMock()
        mock_db.get_item.return_value = None
        mock_get_db.return_value = mock_db

        # Call the tool
        result = get_reservation("RES-2025-INVALID")

        # Verify - ToolError format uses "success" and "error_code"
        assert result["success"] is False
        assert result["error_code"] == "ERR_006"  # RESERVATION_NOT_FOUND
        assert "not found" in result["message"].lower()

    @patch("src.tools.reservations._get_db")
    def test_get_reservation_includes_payment_status(
        self, mock_get_db: MagicMock
    ) -> None:
        """Should include payment status in response."""
        from src.tools.reservations import get_reservation

        # Setup mock
        mock_db = MagicMock()
        mock_db.get_item.return_value = {
            "reservation_id": "RES-2025-ABC12345",
            "guest_id": "guest-123",
            "check_in": "2025-07-15",
            "check_out": "2025-07-22",
            "nights": 7,
            "num_adults": 2,
            "total_amount": 89000,
            "status": ReservationStatus.PENDING.value,
            "payment_status": PaymentStatus.PENDING.value,
            "created_at": "2025-06-01T10:00:00Z",
        }
        mock_get_db.return_value = mock_db

        # Call the tool
        result = get_reservation("RES-2025-ABC12345")

        # Verify
        assert result["status"] == "success"
        assert result["payment_status"] == PaymentStatus.PENDING.value
        assert result["reservation_status"] == ReservationStatus.PENDING.value

    @patch("src.tools.reservations._get_db")
    def test_get_reservation_includes_message(self, mock_get_db: MagicMock) -> None:
        """Should include helpful message in response."""
        from src.tools.reservations import get_reservation

        # Setup mock
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
            "created_at": "2025-06-01T10:00:00Z",
        }
        mock_get_db.return_value = mock_db

        # Call the tool
        result = get_reservation("RES-2025-ABC12345")

        # Verify
        assert "message" in result
        assert "RES-2025-ABC12345" in result["message"]
        assert "7 nights" in result["message"]


class TestGetReservationScenarios:
    """Scenario-based tests for get_reservation."""

    @patch("src.tools.reservations._get_db")
    def test_guest_checks_upcoming_booking(self, mock_get_db: MagicMock) -> None:
        """Guest asking 'What's my booking?' should get reservation details."""
        from src.tools.reservations import get_reservation

        mock_db = MagicMock()
        mock_db.get_item.return_value = {
            "reservation_id": "RES-2025-ABC12345",
            "guest_id": "guest-123",
            "check_in": "2025-08-01",
            "check_out": "2025-08-08",
            "nights": 7,
            "num_adults": 2,
            "num_children": 2,
            "total_amount": 105000,
            "status": ReservationStatus.CONFIRMED.value,
            "payment_status": PaymentStatus.COMPLETED.value,
            "created_at": "2025-06-15T14:30:00Z",
        }
        mock_get_db.return_value = mock_db

        result = get_reservation("RES-2025-ABC12345")

        assert result["status"] == "success"
        assert result["check_in"] == "2025-08-01"
        assert result["num_adults"] == 2
        assert result["num_children"] == 2

    @patch("src.tools.reservations._get_db")
    def test_guest_checks_pending_payment(self, mock_get_db: MagicMock) -> None:
        """Guest with pending payment should see payment reminder."""
        from src.tools.reservations import get_reservation

        mock_db = MagicMock()
        mock_db.get_item.return_value = {
            "reservation_id": "RES-2025-ABC12345",
            "guest_id": "guest-123",
            "check_in": "2025-08-01",
            "check_out": "2025-08-08",
            "nights": 7,
            "num_adults": 2,
            "total_amount": 89000,
            "status": ReservationStatus.PENDING.value,
            "payment_status": PaymentStatus.PENDING.value,
            "created_at": "2025-06-15T14:30:00Z",
        }
        mock_get_db.return_value = mock_db

        result = get_reservation("RES-2025-ABC12345")

        assert result["status"] == "success"
        assert result["payment_status"] == PaymentStatus.PENDING.value
