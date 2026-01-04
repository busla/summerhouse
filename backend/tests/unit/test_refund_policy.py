"""Unit tests for RefundPolicyService calculation logic.

Tests verify the service correctly calculates refund amounts based on
cancellation timing (FR-015, FR-016, FR-017):
- Full refund: 14+ days before check-in (FR-015)
- 50% refund: 7-14 days before check-in (FR-016)
- No refund: <7 days before check-in (FR-017)

TDD: These tests are written FIRST and expected to FAIL until
RefundPolicyService is implemented.

Test categories:
- T031-A: Full refund scenarios (14+ days)
- T031-B: Partial refund scenarios (7-14 days)
- T031-C: No refund scenarios (<7 days)
- T031-D: Edge cases (exact boundaries)
"""

import datetime as dt
from decimal import Decimal

import pytest


# === Test Configuration ===

TEST_PAYMENT_AMOUNT = 112500  # EUR cents (€1,125.00)


# === T031-A: Full Refund Tests (14+ days) ===


class TestFullRefundPolicy:
    """Tests for full refund scenarios (FR-015)."""

    def test_full_refund_15_days_before(self) -> None:
        """15 days before check-in gets 100% refund."""
        from shared.services.refund_policy_service import RefundPolicyService

        service = RefundPolicyService()
        check_in_date = dt.date(2026, 7, 20)
        cancellation_date = dt.date(2026, 7, 5)  # 15 days before

        result = service.calculate_refund_amount(
            payment_amount=TEST_PAYMENT_AMOUNT,
            check_in_date=check_in_date,
            cancellation_date=cancellation_date,
        )

        assert result["refund_amount"] == TEST_PAYMENT_AMOUNT
        assert result["refund_percentage"] == 100
        assert result["policy_tier"] == "full"

    def test_full_refund_exactly_14_days_before(self) -> None:
        """Exactly 14 days before check-in gets 100% refund (inclusive boundary)."""
        from shared.services.refund_policy_service import RefundPolicyService

        service = RefundPolicyService()
        check_in_date = dt.date(2026, 7, 20)
        cancellation_date = dt.date(2026, 7, 6)  # Exactly 14 days before

        result = service.calculate_refund_amount(
            payment_amount=TEST_PAYMENT_AMOUNT,
            check_in_date=check_in_date,
            cancellation_date=cancellation_date,
        )

        assert result["refund_amount"] == TEST_PAYMENT_AMOUNT
        assert result["refund_percentage"] == 100
        assert result["policy_tier"] == "full"

    def test_full_refund_30_days_before(self) -> None:
        """30 days before check-in gets 100% refund."""
        from shared.services.refund_policy_service import RefundPolicyService

        service = RefundPolicyService()
        check_in_date = dt.date(2026, 7, 30)
        cancellation_date = dt.date(2026, 6, 30)  # 30 days before

        result = service.calculate_refund_amount(
            payment_amount=TEST_PAYMENT_AMOUNT,
            check_in_date=check_in_date,
            cancellation_date=cancellation_date,
        )

        assert result["refund_amount"] == TEST_PAYMENT_AMOUNT
        assert result["policy_tier"] == "full"


# === T031-B: Partial Refund Tests (7-14 days) ===


class TestPartialRefundPolicy:
    """Tests for partial refund scenarios (FR-016)."""

    def test_partial_refund_13_days_before(self) -> None:
        """13 days before check-in gets 50% refund."""
        from shared.services.refund_policy_service import RefundPolicyService

        service = RefundPolicyService()
        check_in_date = dt.date(2026, 7, 20)
        cancellation_date = dt.date(2026, 7, 7)  # 13 days before

        result = service.calculate_refund_amount(
            payment_amount=TEST_PAYMENT_AMOUNT,
            check_in_date=check_in_date,
            cancellation_date=cancellation_date,
        )

        expected_refund = TEST_PAYMENT_AMOUNT // 2  # 56250
        assert result["refund_amount"] == expected_refund
        assert result["refund_percentage"] == 50
        assert result["policy_tier"] == "partial"

    def test_partial_refund_10_days_before(self) -> None:
        """10 days before check-in gets 50% refund."""
        from shared.services.refund_policy_service import RefundPolicyService

        service = RefundPolicyService()
        check_in_date = dt.date(2026, 7, 20)
        cancellation_date = dt.date(2026, 7, 10)  # 10 days before

        result = service.calculate_refund_amount(
            payment_amount=TEST_PAYMENT_AMOUNT,
            check_in_date=check_in_date,
            cancellation_date=cancellation_date,
        )

        expected_refund = TEST_PAYMENT_AMOUNT // 2
        assert result["refund_amount"] == expected_refund
        assert result["policy_tier"] == "partial"

    def test_partial_refund_exactly_7_days_before(self) -> None:
        """Exactly 7 days before check-in gets 50% refund (inclusive boundary)."""
        from shared.services.refund_policy_service import RefundPolicyService

        service = RefundPolicyService()
        check_in_date = dt.date(2026, 7, 20)
        cancellation_date = dt.date(2026, 7, 13)  # Exactly 7 days before

        result = service.calculate_refund_amount(
            payment_amount=TEST_PAYMENT_AMOUNT,
            check_in_date=check_in_date,
            cancellation_date=cancellation_date,
        )

        expected_refund = TEST_PAYMENT_AMOUNT // 2
        assert result["refund_amount"] == expected_refund
        assert result["refund_percentage"] == 50
        assert result["policy_tier"] == "partial"


# === T031-C: No Refund Tests (<7 days) ===


class TestNoRefundPolicy:
    """Tests for no refund scenarios (FR-017)."""

    def test_no_refund_6_days_before(self) -> None:
        """6 days before check-in gets 0% refund."""
        from shared.services.refund_policy_service import RefundPolicyService

        service = RefundPolicyService()
        check_in_date = dt.date(2026, 7, 20)
        cancellation_date = dt.date(2026, 7, 14)  # 6 days before

        result = service.calculate_refund_amount(
            payment_amount=TEST_PAYMENT_AMOUNT,
            check_in_date=check_in_date,
            cancellation_date=cancellation_date,
        )

        assert result["refund_amount"] == 0
        assert result["refund_percentage"] == 0
        assert result["policy_tier"] == "none"

    def test_no_refund_1_day_before(self) -> None:
        """1 day before check-in gets 0% refund."""
        from shared.services.refund_policy_service import RefundPolicyService

        service = RefundPolicyService()
        check_in_date = dt.date(2026, 7, 20)
        cancellation_date = dt.date(2026, 7, 19)  # 1 day before

        result = service.calculate_refund_amount(
            payment_amount=TEST_PAYMENT_AMOUNT,
            check_in_date=check_in_date,
            cancellation_date=cancellation_date,
        )

        assert result["refund_amount"] == 0
        assert result["policy_tier"] == "none"

    def test_no_refund_same_day(self) -> None:
        """Same day as check-in gets 0% refund."""
        from shared.services.refund_policy_service import RefundPolicyService

        service = RefundPolicyService()
        check_in_date = dt.date(2026, 7, 20)
        cancellation_date = dt.date(2026, 7, 20)  # Same day

        result = service.calculate_refund_amount(
            payment_amount=TEST_PAYMENT_AMOUNT,
            check_in_date=check_in_date,
            cancellation_date=cancellation_date,
        )

        assert result["refund_amount"] == 0
        assert result["policy_tier"] == "none"

    def test_no_refund_after_check_in(self) -> None:
        """After check-in date gets 0% refund."""
        from shared.services.refund_policy_service import RefundPolicyService

        service = RefundPolicyService()
        check_in_date = dt.date(2026, 7, 20)
        cancellation_date = dt.date(2026, 7, 21)  # Day after check-in

        result = service.calculate_refund_amount(
            payment_amount=TEST_PAYMENT_AMOUNT,
            check_in_date=check_in_date,
            cancellation_date=cancellation_date,
        )

        assert result["refund_amount"] == 0
        assert result["policy_tier"] == "none"


# === T031-D: Edge Cases ===


class TestRefundPolicyEdgeCases:
    """Edge case tests for refund policy."""

    def test_handles_odd_amount_for_50_percent(self) -> None:
        """50% refund handles odd amounts correctly (rounds down)."""
        from shared.services.refund_policy_service import RefundPolicyService

        service = RefundPolicyService()
        check_in_date = dt.date(2026, 7, 20)
        cancellation_date = dt.date(2026, 7, 10)  # 10 days - partial

        odd_amount = 11111  # Odd amount in cents

        result = service.calculate_refund_amount(
            payment_amount=odd_amount,
            check_in_date=check_in_date,
            cancellation_date=cancellation_date,
        )

        # Should round down: 11111 / 2 = 5555 (integer division)
        assert result["refund_amount"] == 5555
        assert result["policy_tier"] == "partial"

    def test_returns_days_until_check_in(self) -> None:
        """Result includes days_until_check_in for transparency."""
        from shared.services.refund_policy_service import RefundPolicyService

        service = RefundPolicyService()
        check_in_date = dt.date(2026, 7, 20)
        cancellation_date = dt.date(2026, 7, 5)  # 15 days before

        result = service.calculate_refund_amount(
            payment_amount=TEST_PAYMENT_AMOUNT,
            check_in_date=check_in_date,
            cancellation_date=cancellation_date,
        )

        assert result["days_until_check_in"] == 15

    def test_returns_policy_description(self) -> None:
        """Result includes human-readable policy description."""
        from shared.services.refund_policy_service import RefundPolicyService

        service = RefundPolicyService()
        check_in_date = dt.date(2026, 7, 20)
        cancellation_date = dt.date(2026, 7, 10)  # 10 days - partial

        result = service.calculate_refund_amount(
            payment_amount=TEST_PAYMENT_AMOUNT,
            check_in_date=check_in_date,
            cancellation_date=cancellation_date,
        )

        assert "description" in result
        assert "50%" in result["description"] or "partial" in result["description"].lower()
