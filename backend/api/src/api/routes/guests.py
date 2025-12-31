"""Guest endpoints for verification and profile management.

Provides REST endpoints for:
- Email verification initiation (public)
- Verification code confirmation (public)
- Getting guest info (JWT required)
- Updating guest profile (JWT required)

Email verification uses Cognito EMAIL_OTP for passwordless auth.
"""

import datetime as dt
import random
import string

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_429_TOO_MANY_REQUESTS,
)

from api.dependencies import get_booking_service
from api.models.guests import VerificationInitiatedResponse
from api.security import AuthScope, require_auth, SecurityRequirement
from shared.models.errors import BookingError, ErrorCode
from shared.models.guest import Guest, GuestUpdate
from shared.models.verification import (
    VerificationAttempt,
    VerificationRequest,
    VerificationResult,
)
from shared.services.booking import BookingService
from shared.services.dynamodb import get_dynamodb_service

router = APIRouter(tags=["guests"])


def _generate_code() -> str:
    """Generate a 6-digit verification code."""
    return "".join(random.choices(string.digits, k=6))


def _get_user_guest_id(request: Request) -> str | None:
    """Extract guest_id from request based on JWT sub claim."""
    user_sub = request.headers.get("x-user-sub")
    if not user_sub:
        return None

    db = get_dynamodb_service()
    guest = db.get_guest_by_cognito_sub(user_sub)
    return guest.get("guest_id") if guest else None


@router.post(
    "/guests/verify",
    summary="Initiate email verification",
    description="""
Send a verification code to the provided email address.

**Public endpoint** - no authentication required.

Initiates the verification flow by sending a 6-digit code
to the email address. Code is valid for 10 minutes.

**Notes:**
- Code expires after 10 minutes
- Rate limited to prevent abuse
- If email exists, sends code to existing account
- If email is new, creates guest record after verification
""",
    response_description="Verification initiated confirmation",
    response_model=VerificationInitiatedResponse,
    responses={
        200: {
            "description": "Verification code sent",
        },
        400: {
            "description": "Invalid email format",
        },
        429: {
            "description": "Too many requests (rate limited)",
        },
    },
)
async def initiate_verification(
    body: VerificationRequest,
) -> VerificationInitiatedResponse:
    """Send verification code to email.

    Creates or updates verification code record.
    """
    db = get_dynamodb_service()
    email = body.email.lower()
    now = dt.datetime.now(dt.UTC)
    code = _generate_code()

    # Calculate TTL (10 minutes from now)
    expires_at = int((now + dt.timedelta(minutes=10)).timestamp())

    # Check for existing code (rate limiting)
    existing = db.get_item("verification-codes", {"email": email})
    if existing:
        created = dt.datetime.fromisoformat(existing["created_at"])
        # Don't allow more than 3 codes per hour
        if (now - created).seconds < 60:
            raise HTTPException(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait before requesting another code",
            )

    # Store verification code
    code_item = {
        "email": email,
        "code": code,
        "expires_at": expires_at,
        "attempts": 0,
        "created_at": now.isoformat(),
    }
    db.put_item("verification-codes", code_item)

    # In production, send email via SES or notification service
    # For now, this is a mock - code is stored but not sent
    # TODO: Integrate with NotificationService to send email

    return VerificationInitiatedResponse()


@router.post(
    "/guests/verify/confirm",
    summary="Verify email code",
    description="""
Verify the email address using the 6-digit code.

**Public endpoint** - no authentication required.

Validates the code and marks the guest's email as verified.
If this is a new email, creates a guest record.

**Notes:**
- Code must match and not be expired
- Maximum 5 attempts per code
- On success, returns guest_id
""",
    response_description="Verification result",
    response_model=VerificationResult,
    responses={
        200: {
            "description": "Verification result (success or failure)",
            "content": {
                "application/json": {
                    "examples": {
                        "success": {
                            "summary": "Verified successfully",
                            "value": {
                                "success": True,
                                "guest_id": "abc123",
                                "error": None,
                                "is_new_guest": False,
                            },
                        },
                        "invalid_code": {
                            "summary": "Invalid code",
                            "value": {
                                "success": False,
                                "guest_id": None,
                                "error": "Invalid verification code",
                                "is_new_guest": False,
                            },
                        },
                    }
                }
            },
        },
        401: {
            "description": "Verification failed (invalid or expired code)",
        },
    },
)
async def verify_code(
    body: VerificationAttempt,
    booking_service: BookingService = Depends(get_booking_service),
) -> VerificationResult:
    """Verify email with code.

    Validates code and creates/updates guest record.
    """
    db = get_dynamodb_service()
    email = body.email.lower()
    now = dt.datetime.now(dt.UTC)

    # Get verification code record
    code_record = db.get_item("verification-codes", {"email": email})
    if not code_record:
        raise BookingError(
            code=ErrorCode.VERIFICATION_FAILED,
            details={"reason": "No verification code found. Request a new one."},
        )

    # Check expiration
    if int(now.timestamp()) > code_record["expires_at"]:
        raise BookingError(
            code=ErrorCode.OTP_EXPIRED,
            details={"reason": "Code has expired. Request a new one."},
        )

    # Check attempt count
    attempts = code_record.get("attempts", 0)
    if attempts >= 5:
        raise BookingError(
            code=ErrorCode.MAX_ATTEMPTS_EXCEEDED,
            details={"reason": "Too many attempts. Request a new code."},
        )

    # Validate code
    if body.code != code_record["code"]:
        # Increment attempt count
        db.update_item(
            "verification-codes",
            {"email": email},
            "SET attempts = attempts + :inc",
            {":inc": 1},
        )
        raise BookingError(
            code=ErrorCode.INVALID_OTP,
            details={"remaining_attempts": str(4 - attempts)},
        )

    # Code is valid - delete the verification record
    db.delete_item("verification-codes", {"email": email})

    # Get or create guest
    existing_guest = booking_service.get_guest_by_email(email)
    is_new_guest = existing_guest is None

    if is_new_guest:
        guest = booking_service.get_or_create_guest(email)
    else:
        guest = existing_guest  # type: ignore[assignment] - narrowed by is_new_guest check

    # Mark as verified
    booking_service.verify_guest_email(guest.guest_id)

    return VerificationResult(
        success=True,
        guest_id=guest.guest_id,
        is_new_guest=is_new_guest,
    )


@router.get(
    "/guests/{email}",
    summary="Get guest by email",
    description="""
Get guest information by email address.

**Requires JWT authentication.**
**Only the account owner can view their profile.**

Returns full guest profile including verification status.

**Notes:**
- Email must be URL-encoded if contains special characters
- Can only access your own profile
""",
    response_description="Guest profile",
    response_model=Guest,
    responses={
        200: {
            "description": "Guest found",
        },
        401: {
            "description": "JWT token required",
        },
        403: {
            "description": "Can only access own profile",
        },
        404: {
            "description": "Guest not found",
        },
    },
)
async def get_guest_by_email(
    request: Request,
    email: str,
    auth: SecurityRequirement = Depends(require_auth([AuthScope.OPENID])),
    booking_service: BookingService = Depends(get_booking_service),
) -> Guest:
    """Get guest profile by email.

    Owner-only access.
    """
    guest = booking_service.get_guest_by_email(email.lower())
    if not guest:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail="Guest not found",
        )

    # Verify ownership - can only access own profile
    current_guest_id = _get_user_guest_id(request)
    if guest.guest_id != current_guest_id:
        raise BookingError(
            code=ErrorCode.UNAUTHORIZED,
            details={"message": "Can only access your own profile"},
        )

    return guest


@router.patch(
    "/guests/{guest_id}",
    summary="Update guest profile",
    description="""
Update guest profile information.

**Requires JWT authentication.**
**Only the account owner can update their profile.**

Allows updating name, phone, and language preference.

**Notes:**
- Only include fields you want to change
- Language must be 'en' or 'es'
""",
    response_description="Updated guest profile",
    response_model=Guest,
    responses={
        200: {
            "description": "Profile updated",
        },
        400: {
            "description": "Invalid update data",
        },
        401: {
            "description": "JWT token required",
        },
        403: {
            "description": "Can only update own profile",
        },
        404: {
            "description": "Guest not found",
        },
    },
)
async def update_guest(
    request: Request,
    guest_id: str,
    body: GuestUpdate,
    auth: SecurityRequirement = Depends(require_auth([AuthScope.OPENID])),
    booking_service: BookingService = Depends(get_booking_service),
) -> Guest:
    """Update guest profile.

    Owner-only operation.
    """
    # Get current guest
    guest = booking_service.get_guest(guest_id)
    if not guest:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail="Guest not found",
        )

    # Verify ownership
    current_guest_id = _get_user_guest_id(request)
    if guest.guest_id != current_guest_id:
        raise BookingError(
            code=ErrorCode.UNAUTHORIZED,
            details={"message": "Can only update your own profile"},
        )

    # Build update expression
    update_parts: list[str] = []
    values: dict[str, str] = {}
    now = dt.datetime.now(dt.UTC)

    if body.name is not None:
        update_parts.append("name = :name")
        values[":name"] = body.name
    if body.phone is not None:
        update_parts.append("phone = :phone")
        values[":phone"] = body.phone
    if body.preferred_language is not None:
        update_parts.append("preferred_language = :lang")
        values[":lang"] = body.preferred_language

    if not update_parts:
        # Nothing to update
        return guest

    update_parts.append("updated_at = :updated")
    values[":updated"] = now.isoformat()

    update_expr = "SET " + ", ".join(update_parts)

    db = get_dynamodb_service()
    result = db.update_item(
        "guests",
        {"guest_id": guest_id},
        update_expr,
        values,
    )

    if not result:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Failed to update profile",
        )

    # Return updated guest
    return booking_service.get_guest(guest_id)  # type: ignore
