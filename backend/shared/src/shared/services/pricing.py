"""Pricing service for rate calculation."""

import datetime as dt
from typing import TYPE_CHECKING, Any

from shared.models import PriceCalculation, Pricing

if TYPE_CHECKING:
    from .dynamodb import DynamoDBService


class PricingService:
    """Service for pricing and rate calculations."""

    TABLE = "pricing"

    def __init__(self, db: "DynamoDBService") -> None:
        """Initialize pricing service.

        Args:
            db: DynamoDB service instance
        """
        self.db = db

    def get_all_seasons(self, active_only: bool = True) -> list[Pricing]:
        """Get all pricing seasons.

        Args:
            active_only: Only return active seasons

        Returns:
            List of Pricing objects
        """
        # For a small table, scan is acceptable
        table = self.db._get_table(self.TABLE)
        response = table.scan()
        items = response.get("Items", [])

        seasons = [self._item_to_pricing(item) for item in items]
        if active_only:
            seasons = [s for s in seasons if s.is_active]

        return sorted(seasons, key=lambda s: s.start_date)

    def get_season_for_date(self, check_date: dt.date) -> Pricing | None:
        """Get the pricing season for a specific date.

        Args:
            check_date: Date to check

        Returns:
            Pricing for that date or None
        """
        seasons = self.get_all_seasons(active_only=True)
        date_str = check_date.isoformat()

        for season in seasons:
            if season.start_date.isoformat() <= date_str <= season.end_date.isoformat():
                return season

        return None

    def calculate_price(
        self,
        check_in: dt.date,
        check_out: dt.date,
    ) -> PriceCalculation | None:
        """Calculate total price for a stay.

        Uses the pricing for the check-in date for the entire stay.
        Returns None if no pricing is available.

        Args:
            check_in: Check-in date
            check_out: Check-out date

        Returns:
            PriceCalculation with breakdown or None
        """
        season = self.get_season_for_date(check_in)
        if not season:
            return None

        nights = (check_out - check_in).days
        if nights < 1:
            return None

        subtotal = nights * season.nightly_rate
        total = subtotal + season.cleaning_fee

        return PriceCalculation(
            check_in=check_in,
            check_out=check_out,
            nights=nights,
            nightly_rate=season.nightly_rate,
            subtotal=subtotal,
            cleaning_fee=season.cleaning_fee,
            total_amount=total,
            minimum_nights=season.minimum_nights,
            season_name=season.season_name,
        )

    def validate_minimum_stay(
        self,
        check_in: dt.date,
        check_out: dt.date,
    ) -> tuple[bool, str]:
        """Check if stay meets minimum nights requirement.

        Args:
            check_in: Check-in date
            check_out: Check-out date

        Returns:
            Tuple of (is_valid, error_message)
        """
        season = self.get_season_for_date(check_in)
        if not season:
            return False, "No pricing available for selected dates"

        nights = (check_out - check_in).days
        if nights < season.minimum_nights:
            return False, (
                f"Minimum stay is {season.minimum_nights} nights "
                f"during {season.season_name}. You selected {nights} nights."
            )

        return True, ""

    def _item_to_pricing(self, item: dict[str, Any]) -> Pricing:
        """Convert DynamoDB item to Pricing model."""
        # Handle is_active as string or boolean (DynamoDB may store as either)
        is_active_raw = item.get("is_active", True)
        if isinstance(is_active_raw, str):
            is_active = is_active_raw.lower() == "true"
        else:
            is_active = bool(is_active_raw)

        return Pricing(
            season_id=item["season_id"],
            season_name=item["season_name"],
            start_date=dt.date.fromisoformat(item["start_date"]),
            end_date=dt.date.fromisoformat(item["end_date"]),
            nightly_rate=int(item["nightly_rate"]),
            minimum_nights=int(item["minimum_nights"]),
            cleaning_fee=int(item["cleaning_fee"]),
            is_active=is_active,
        )

    def create_season(self, pricing: Pricing) -> bool:
        """Create a new pricing season.

        Args:
            pricing: Pricing data

        Returns:
            True if created
        """
        item = {
            "season_id": pricing.season_id,
            "season_name": pricing.season_name,
            "start_date": pricing.start_date.isoformat(),
            "end_date": pricing.end_date.isoformat(),
            "nightly_rate": pricing.nightly_rate,
            "minimum_nights": pricing.minimum_nights,
            "cleaning_fee": pricing.cleaning_fee,
            "is_active": pricing.is_active,
        }
        return self.db.put_item(self.TABLE, item)
