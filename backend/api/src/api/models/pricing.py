"""API models for pricing endpoints.

Extends shared pricing models with API-specific response formats
for current pricing, seasonal rates, and minimum stay validation.
"""

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from shared.models.pricing import Pricing


class BasePricingResponse(BaseModel):
    """Current base pricing information.

    Returns the pricing applicable for today's date,
    including nightly rate, cleaning fee, and minimum stay.
    """

    model_config = ConfigDict(
        strict=True,
        json_schema_extra={
            "examples": [
                {
                    "nightly_rate": 15000,
                    "cleaning_fee": 7500,
                    "minimum_nights": 7,
                    "season_name": "High Season (July-August)",
                    "currency": "EUR",
                }
            ]
        },
    )

    nightly_rate: int = Field(
        ...,
        ge=0,
        description="Current nightly rate in EUR cents",
        examples=[15000],
    )
    cleaning_fee: int = Field(
        ...,
        ge=0,
        description="Cleaning fee in EUR cents",
        examples=[7500],
    )
    minimum_nights: int = Field(
        ...,
        ge=1,
        description="Current minimum stay requirement",
        examples=[7],
    )
    season_name: str = Field(
        ...,
        description="Name of the current season",
        examples=["High Season (July-August)"],
    )
    currency: str = Field(
        default="EUR",
        description="Currency code (always EUR)",
    )


class SeasonalRatesResponse(BaseModel):
    """All seasonal pricing rates.

    Returns complete pricing schedule with all active seasons,
    sorted by start date.
    """

    model_config = ConfigDict(
        strict=True,
        json_schema_extra={
            "examples": [
                {
                    "seasons": [
                        {
                            "season_id": "low-2025",
                            "season_name": "Low Season",
                            "start_date": "2025-01-01",
                            "end_date": "2025-03-31",
                            "nightly_rate": 8000,
                            "minimum_nights": 3,
                            "cleaning_fee": 5000,
                            "is_active": True,
                        }
                    ],
                    "currency": "EUR",
                }
            ]
        },
    )

    seasons: list[Pricing] = Field(
        ...,
        description="List of all seasonal pricing configurations",
    )
    currency: str = Field(
        default="EUR",
        description="Currency code (always EUR)",
    )


class MinimumStayCheckResponse(BaseModel):
    """Result of minimum stay validation.

    Validates whether a requested stay duration meets
    the minimum nights requirement for the check-in date's season.
    """

    model_config = ConfigDict(
        strict=True,
        json_schema_extra={
            "examples": [
                {
                    "is_valid": True,
                    "requested_nights": 7,
                    "minimum_nights": 7,
                    "season_name": "High Season (July-August)",
                    "message": "",
                },
                {
                    "is_valid": False,
                    "requested_nights": 3,
                    "minimum_nights": 7,
                    "season_name": "High Season (July-August)",
                    "message": "Minimum stay is 7 nights during High Season (July-August). You selected 3 nights.",
                },
            ]
        },
    )

    is_valid: bool = Field(
        ...,
        description="Whether the stay meets minimum requirements",
    )
    requested_nights: int = Field(
        ...,
        ge=1,
        description="Number of nights requested",
    )
    minimum_nights: int = Field(
        ...,
        ge=1,
        description="Minimum nights required for this season",
    )
    season_name: str = Field(
        ...,
        description="Season applicable to the check-in date",
    )
    message: str = Field(
        default="",
        description="Validation message (empty if valid)",
    )


class MinimumStayInfoResponse(BaseModel):
    """Minimum stay information for a specific date.

    Returns the minimum stay requirement and pricing
    for bookings starting on a particular date.
    """

    model_config = ConfigDict(
        strict=True,
        json_schema_extra={
            "examples": [
                {
                    "date": "2025-07-15",
                    "minimum_nights": 7,
                    "season_name": "High Season (July-August)",
                    "nightly_rate": 15000,
                }
            ]
        },
    )

    date: dt.date = Field(
        ...,
        description="Date for which info was requested",
        examples=["2025-07-15"],
    )
    minimum_nights: int = Field(
        ...,
        ge=1,
        description="Minimum nights required for stays starting on this date",
    )
    season_name: str = Field(
        ...,
        description="Season applicable to this date",
    )
    nightly_rate: int = Field(
        ...,
        ge=0,
        description="Nightly rate in EUR cents for this date",
    )
