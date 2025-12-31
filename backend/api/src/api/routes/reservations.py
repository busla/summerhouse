"""Reservation endpoints for booking management.

Provides REST endpoints for:
- Creating new reservations (JWT required)
- Retrieving reservations by ID (public) or for current user (JWT required)
- Modifying reservations (JWT required, owner only)
- Cancelling reservations (JWT required, owner only)

Protected endpoints require JWT token via Authorization header.
API Gateway validates the JWT and passes user identity via x-user-sub header.
"""

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)

from api.dependencies import get_booking_service
from api.models.reservations import (
    CancellationResponse,
    ReservationCreateRequest,
    ReservationListResponse,
    ReservationModifyRequest,
)
from api.security import AuthScope, require_auth, SecurityRequirement
from shared.models.enums import ReservationStatus
from shared.models.errors import BookingError, ErrorCode
from shared.models.reservation import Reservation, ReservationCreate
from shared.services.booking import BookingService
from shared.services.dynamodb import get_dynamodb_service

router = APIRouter(tags=["reservations"])


def _get_user_guest_id(request: Request) -> str | None:
    """Extract guest_id from request based on JWT sub claim.

    API Gateway validates JWT and passes sub via x-user-sub header.
    We then look up the guest by cognito_sub.
    """
    user_sub = request.headers.get("x-user-sub")
    if not user_sub:
        return None

    db = get_dynamodb_service()
    guest = db.get_guest_by_cognito_sub(user_sub)
    return guest.get("guest_id") if guest else None


@router.post(
    "/reservations",
    summary="Create reservation",
    description="""
Create a new reservation.

**Requires JWT authentication.**

Validates availability, calculates pricing, and atomically books dates.
Returns the created reservation with pricing breakdown.

**Notes:**
- Dates must be available (use GET /api/availability first)
- Must meet minimum stay requirement for the season
- Total guests (adults + children) must not exceed 4
- Guest ID is derived from JWT token
""",
    response_description="Created reservation details",
    response_model=Reservation,
    status_code=HTTP_201_CREATED,
    responses={
        201: {
            "description": "Reservation created successfully",
        },
        400: {
            "description": "Invalid request (date range, guest count)",
        },
        401: {
            "description": "JWT token required",
        },
        409: {
            "description": "Dates unavailable or minimum stay not met",
        },
    },
)
async def create_reservation(
    request: Request,
    body: ReservationCreateRequest,
    auth: SecurityRequirement = Depends(require_auth([AuthScope.OPENID])),
    service: BookingService = Depends(get_booking_service),
) -> Reservation:
    """Create a new reservation.

    Atomically books dates and creates reservation record.
    """
    # Validate date range
    if body.check_out <= body.check_in:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="check_out must be after check_in",
        )

    # Validate guest count
    total_guests = body.num_adults + body.num_children
    if total_guests > 4:
        raise BookingError(
            code=ErrorCode.MAX_GUESTS_EXCEEDED,
            details={"requested": str(total_guests), "maximum": "4"},
        )

    # Get guest ID from JWT
    guest_id = _get_user_guest_id(request)
    if not guest_id:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Guest profile not found. Complete verification first.",
        )

    # Create reservation using shared model
    create_data = ReservationCreate(
        guest_id=guest_id,
        check_in=body.check_in,
        check_out=body.check_out,
        num_adults=body.num_adults,
        num_children=body.num_children,
        special_requests=body.special_requests,
    )

    reservation, error = service.create_reservation(create_data)

    if not reservation:
        # Map error message to appropriate error code
        if "not available" in error.lower() or "unavailable" in error.lower():
            raise BookingError(
                code=ErrorCode.DATES_UNAVAILABLE,
                details={"message": error},
            )
        elif "minimum" in error.lower():
            raise BookingError(
                code=ErrorCode.MINIMUM_NIGHTS_NOT_MET,
                details={"message": error},
            )
        else:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=error,
            )

    return reservation


@router.get(
    "/reservations/{reservation_id}",
    summary="Get reservation by ID",
    description="""
Get reservation details by ID.

**Public endpoint** - no authentication required.
Can be used to check reservation status with just the ID.

**Notes:**
- Returns full reservation details including pricing
- Amounts are in EUR cents
""",
    response_description="Reservation details",
    response_model=Reservation,
    responses={
        200: {
            "description": "Reservation found",
        },
        404: {
            "description": "Reservation not found",
        },
    },
)
async def get_reservation(
    reservation_id: str,
    service: BookingService = Depends(get_booking_service),
) -> Reservation:
    """Get reservation by ID.

    Public endpoint for checking reservation status.
    """
    reservation = service.get_reservation(reservation_id)

    if not reservation:
        raise BookingError(
            code=ErrorCode.RESERVATION_NOT_FOUND,
            details={"reservation_id": reservation_id},
        )

    return reservation


@router.get(
    "/reservations",
    summary="Get my reservations",
    description="""
Get current user's reservations.

**Requires JWT authentication.**

Returns all reservations for the authenticated user,
optionally filtered by status.

**Notes:**
- Results are sorted by check-in date (ascending)
- Returns reservation summaries for efficiency
""",
    response_description="List of user's reservations",
    response_model=ReservationListResponse,
    responses={
        200: {
            "description": "Reservations retrieved",
        },
        401: {
            "description": "JWT token required",
        },
    },
)
async def get_my_reservations(
    request: Request,
    status: ReservationStatus | None = Query(
        default=None,
        description="Filter by reservation status",
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum results to return",
    ),
    auth: SecurityRequirement = Depends(require_auth([AuthScope.OPENID])),
    service: BookingService = Depends(get_booking_service),
) -> ReservationListResponse:
    """Get current user's reservations.

    Optionally filter by status.
    """
    guest_id = _get_user_guest_id(request)
    if not guest_id:
        # User is authenticated but no guest profile yet
        return ReservationListResponse(reservations=[], total_count=0)

    reservations = service.get_guest_reservations(guest_id)

    # Filter by status if specified
    if status:
        reservations = [r for r in reservations if r.status == status]

    # Apply limit
    total_count = len(reservations)
    reservations = reservations[:limit]

    return ReservationListResponse(
        reservations=reservations,
        total_count=total_count,
    )


@router.patch(
    "/reservations/{reservation_id}",
    summary="Modify reservation",
    description="""
Modify an existing reservation.

**Requires JWT authentication.**
**Only the reservation owner can modify.**

Allows changing dates, guest count, or special requests.
Date changes require availability validation.

**Notes:**
- Only include fields you want to change
- Date changes may affect pricing
- Cannot modify cancelled reservations
""",
    response_description="Updated reservation",
    response_model=Reservation,
    responses={
        200: {
            "description": "Reservation modified",
        },
        400: {
            "description": "Invalid modification",
        },
        401: {
            "description": "JWT token required",
        },
        403: {
            "description": "Not authorized to modify this reservation",
        },
        404: {
            "description": "Reservation not found",
        },
        409: {
            "description": "New dates unavailable",
        },
    },
)
async def modify_reservation(
    request: Request,
    reservation_id: str,
    body: ReservationModifyRequest,
    auth: SecurityRequirement = Depends(require_auth([AuthScope.OPENID])),
    service: BookingService = Depends(get_booking_service),
) -> Reservation:
    """Modify an existing reservation.

    Owner-only operation.
    """
    # Get current reservation
    reservation = service.get_reservation(reservation_id)
    if not reservation:
        raise BookingError(
            code=ErrorCode.RESERVATION_NOT_FOUND,
            details={"reservation_id": reservation_id},
        )

    # Verify ownership
    guest_id = _get_user_guest_id(request)
    if reservation.guest_id != guest_id:
        raise BookingError(
            code=ErrorCode.UNAUTHORIZED,
            details={"message": "You can only modify your own reservations"},
        )

    # Cannot modify cancelled reservations
    if reservation.status == ReservationStatus.CANCELLED:
        raise HTTPException(
            status_code=HTTP_409_CONFLICT,
            detail="Cannot modify cancelled reservations",
        )

    # For now, only allow modifying special_requests
    # Date/guest changes would require more complex logic
    # (release old dates, validate new dates, recalculate pricing)
    if body.check_in or body.check_out:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Date modifications not yet supported. Please cancel and rebook.",
        )

    if body.num_adults or body.num_children:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Guest count modifications not yet supported.",
        )

    # Update special requests if provided
    if body.special_requests is not None:
        now = dt.datetime.now(dt.UTC)
        db = get_dynamodb_service()
        db.update_item(
            "reservations",
            {"reservation_id": reservation_id},
            "SET special_requests = :sr, updated_at = :u",
            {":sr": body.special_requests, ":u": now.isoformat()},
        )
        reservation.special_requests = body.special_requests
        reservation.updated_at = now

    return reservation


@router.delete(
    "/reservations/{reservation_id}",
    summary="Cancel reservation",
    description="""
Cancel a reservation.

**Requires JWT authentication.**
**Only the reservation owner can cancel.**

Refund is calculated based on cancellation policy:
- 14+ days before check-in: Full refund
- 7-13 days before check-in: 50% refund
- Less than 7 days: No refund

**Notes:**
- Cancelled dates become available again
- Cannot cancel already-cancelled reservations
""",
    response_description="Cancellation result with refund info",
    response_model=CancellationResponse,
    responses={
        200: {
            "description": "Reservation cancelled",
        },
        401: {
            "description": "JWT token required",
        },
        403: {
            "description": "Not authorized to cancel this reservation",
        },
        404: {
            "description": "Reservation not found",
        },
        409: {
            "description": "Already cancelled",
        },
    },
)
async def cancel_reservation(
    request: Request,
    reservation_id: str,
    reason: str | None = Query(
        default=None,
        max_length=200,
        description="Reason for cancellation",
    ),
    auth: SecurityRequirement = Depends(require_auth([AuthScope.OPENID])),
    service: BookingService = Depends(get_booking_service),
) -> CancellationResponse:
    """Cancel a reservation.

    Owner-only operation. Applies cancellation policy for refunds.
    """
    # Get current reservation
    reservation = service.get_reservation(reservation_id)
    if not reservation:
        raise BookingError(
            code=ErrorCode.RESERVATION_NOT_FOUND,
            details={"reservation_id": reservation_id},
        )

    # Verify ownership
    guest_id = _get_user_guest_id(request)
    if reservation.guest_id != guest_id:
        raise BookingError(
            code=ErrorCode.UNAUTHORIZED,
            details={"message": "You can only cancel your own reservations"},
        )

    # Cannot cancel already cancelled
    if reservation.status == ReservationStatus.CANCELLED:
        raise HTTPException(
            status_code=HTTP_409_CONFLICT,
            detail="Reservation is already cancelled",
        )

    # Cancel and get refund amount
    success, refund_amount = service.cancel_reservation(
        reservation_id,
        reason or "Cancelled by guest",
    )

    if not success:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Failed to cancel reservation",
        )

    # Determine refund policy message
    days_until = (reservation.check_in - dt.date.today()).days
    if days_until >= 14:
        refund_policy = "Full refund (14+ days notice)"
    elif days_until >= 7:
        refund_policy = "50% refund (7-13 days notice)"
    else:
        refund_policy = "No refund (less than 7 days notice)"

    return CancellationResponse(
        reservation_id=reservation_id,
        status=ReservationStatus.CANCELLED,
        refund_amount=refund_amount if refund_amount > 0 else None,
        refund_policy=refund_policy,
    )
