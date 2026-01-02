"""API models for reservation endpoints.

Extends shared reservation models with API-specific request/response formats.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from shared.models.enums import ReservationStatus
from shared.models.reservation import ReservationSummary


class ReservationCreateRequest(BaseModel):
    """Request to create a new reservation.

    Guest ID is not included - it's derived from the JWT token.
    """

    model_config = ConfigDict(
        # Note: strict=False allows string-to-date coercion from JSON
        # (JSON has no native date type, dates arrive as ISO strings)
        strict=False,
        json_schema_extra={
            "examples": [
                {
                    "check_in": "2025-07-15",
                    "check_out": "2025-07-22",
                    "num_adults": 2,
                    "num_children": 1,
                    "special_requests": "Late arrival around 10pm",
                }
            ]
        },
    )

    check_in: date = Field(
        ...,
        description="Check-in date (YYYY-MM-DD)",
        examples=["2025-07-15"],
    )
    check_out: date = Field(
        ...,
        description="Check-out date (YYYY-MM-DD)",
        examples=["2025-07-22"],
    )
    num_adults: int = Field(
        ...,
        ge=1,
        le=4,
        description="Number of adult guests (1-4)",
        examples=[2],
    )
    num_children: int = Field(
        default=0,
        ge=0,
        le=4,
        description="Number of child guests (0-4)",
        examples=[0],
    )
    special_requests: str | None = Field(
        default=None,
        max_length=500,
        description="Special requests or notes",
        examples=["Late arrival around 10pm"],
    )


class ReservationModifyRequest(BaseModel):
    """Request to modify an existing reservation.

    Only include fields that should be changed.
    Date changes require availability validation.
    """

    model_config = ConfigDict(
        # Note: strict=False allows string-to-date coercion from JSON
        strict=False,
        json_schema_extra={
            "examples": [
                {
                    "check_out": "2025-07-25",
                    "special_requests": "Extended stay, late checkout if possible",
                }
            ]
        },
    )

    check_in: date | None = Field(
        default=None,
        description="New check-in date",
    )
    check_out: date | None = Field(
        default=None,
        description="New check-out date",
    )
    num_adults: int | None = Field(
        default=None,
        ge=1,
        le=4,
        description="New number of adults (1-4)",
    )
    num_children: int | None = Field(
        default=None,
        ge=0,
        le=4,
        description="New number of children (0-4)",
    )
    special_requests: str | None = Field(
        default=None,
        max_length=500,
        description="Updated special requests",
    )


class ReservationListResponse(BaseModel):
    """List of reservations with total count.

    Returns reservation summaries for efficient listing.
    """

    model_config = ConfigDict(
        strict=True,
        json_schema_extra={
            "examples": [
                {
                    "reservations": [
                        {
                            "reservation_id": "RES-2025-ABC123",
                            "check_in": "2025-07-15",
                            "check_out": "2025-07-22",
                            "status": "confirmed",
                            "total_amount": 112500,
                        }
                    ],
                    "total_count": 1,
                }
            ]
        },
    )

    reservations: list[ReservationSummary] = Field(
        ...,
        description="List of reservation summaries",
    )
    total_count: int = Field(
        ...,
        ge=0,
        description="Total number of reservations",
    )


class CancellationResponse(BaseModel):
    """Reservation cancellation result.

    Returns cancellation status and refund information
    based on cancellation policy.
    """

    model_config = ConfigDict(
        strict=True,
        json_schema_extra={
            "examples": [
                {
                    "reservation_id": "RES-2025-ABC123",
                    "status": "cancelled",
                    "refund_amount": 112500,
                    "refund_policy": "Full refund (14+ days notice)",
                },
                {
                    "reservation_id": "RES-2025-XYZ789",
                    "status": "cancelled",
                    "refund_amount": 56250,
                    "refund_policy": "50% refund (7-13 days notice)",
                },
            ]
        },
    )

    reservation_id: str = Field(
        ...,
        description="Cancelled reservation ID",
    )
    status: ReservationStatus = Field(
        ...,
        description="New reservation status (will be 'cancelled')",
    )
    refund_amount: int | None = Field(
        default=None,
        ge=0,
        description="Refund amount in EUR cents (if applicable)",
    )
    refund_policy: str = Field(
        ...,
        description="Cancellation policy that was applied",
    )
