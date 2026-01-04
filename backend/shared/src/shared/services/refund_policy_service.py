"""Refund policy service for calculating refund amounts.

Implements the cancellation refund policy (FR-015, FR-016, FR-017):
- Full refund (100%): Cancel 14+ days before check-in
- Partial refund (50%): Cancel 7-14 days before check-in
- No refund (0%): Cancel <7 days before check-in

All amounts are in EUR cents to avoid floating-point issues.
"""

import datetime as dt
from typing import TypedDict


class RefundCalculation(TypedDict):
    """Result of refund policy calculation."""

    refund_amount: int  # Amount in EUR cents
    refund_percentage: int  # 0, 50, or 100
    policy_tier: str  # "full", "partial", or "none"
    days_until_check_in: int
    description: str


class RefundPolicyService:
    """Service for calculating refund amounts based on cancellation timing.

    Policy tiers:
    - FULL (100%): 14+ days before check-in
    - PARTIAL (50%): 7-13 days before check-in
    - NONE (0%): <7 days before check-in
    """

    # Policy thresholds (days before check-in)
    FULL_REFUND_DAYS = 14  # >= 14 days = full refund
    PARTIAL_REFUND_DAYS = 7  # >= 7 days = partial refund

    # Refund percentages
    FULL_REFUND_PERCENT = 100
    PARTIAL_REFUND_PERCENT = 50
    NO_REFUND_PERCENT = 0

    def calculate_refund_amount(
        self,
        payment_amount: int,
        check_in_date: dt.date,
        cancellation_date: dt.date,
    ) -> RefundCalculation:
        """Calculate refund amount based on cancellation timing.

        Args:
            payment_amount: Original payment amount in EUR cents
            check_in_date: Reservation check-in date
            cancellation_date: Date of cancellation request

        Returns:
            RefundCalculation with refund amount and policy details
        """
        # Calculate days until check-in (can be negative if after check-in)
        days_until_check_in = (check_in_date - cancellation_date).days

        # Determine policy tier and percentage
        if days_until_check_in >= self.FULL_REFUND_DAYS:
            # Full refund: 14+ days before check-in (FR-015)
            percentage = self.FULL_REFUND_PERCENT
            tier = "full"
            description = (
                f"Full refund (100%): Cancelled {days_until_check_in} days before check-in "
                f"(policy: 14+ days = full refund)"
            )
        elif days_until_check_in >= self.PARTIAL_REFUND_DAYS:
            # Partial refund: 7-13 days before check-in (FR-016)
            percentage = self.PARTIAL_REFUND_PERCENT
            tier = "partial"
            description = (
                f"Partial refund (50%): Cancelled {days_until_check_in} days before check-in "
                f"(policy: 7-13 days = 50% refund)"
            )
        else:
            # No refund: <7 days before check-in (FR-017)
            percentage = self.NO_REFUND_PERCENT
            tier = "none"
            if days_until_check_in < 0:
                description = (
                    f"No refund: Cancelled after check-in date "
                    f"(policy: cancellation not allowed after check-in)"
                )
            else:
                description = (
                    f"No refund (0%): Cancelled {days_until_check_in} days before check-in "
                    f"(policy: <7 days = no refund)"
                )

        # Calculate refund amount (integer division for cents)
        refund_amount = (payment_amount * percentage) // 100

        return RefundCalculation(
            refund_amount=refund_amount,
            refund_percentage=percentage,
            policy_tier=tier,
            days_until_check_in=days_until_check_in,
            description=description,
        )

    def get_policy_description(self) -> str:
        """Get human-readable description of the refund policy.

        Returns:
            Policy description text
        """
        return (
            "Cancellation Policy:\n"
            f"• 14+ days before check-in: Full refund (100%)\n"
            f"• 7-13 days before check-in: Partial refund (50%)\n"
            f"• Less than 7 days before check-in: No refund\n"
            f"• After check-in: No refund"
        )
