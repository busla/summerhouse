"""Customer endpoints for authenticated profile management.

Provides REST endpoints for:
- GET /customers/me - Get current customer profile
- PUT /customers/me - Update current customer profile
- POST /customers/me - Create customer profile

All endpoints require JWT authentication via API Gateway Cognito authorizer.
The cognito_sub is extracted from x-user-sub header set by API Gateway.

Trust Model:
- API Gateway validates JWT using Cognito authorizer
- After validation, API Gateway injects x-user-sub header with cognito sub claim
- Backend trusts this header since it comes from API Gateway, not the client

Requirements: T026a, T027, T029b-T033, T035
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from api.security import AuthScope, require_auth, SecurityRequirement
from shared.services.dynamodb import get_dynamodb_service

# Structured logger for auth events (T035)
logger = logging.getLogger(__name__)


# === Authentication Helpers ===


def _get_header_case_insensitive(request: Request, header_name: str) -> str | None:
    """Extract header value with case-insensitive lookup.

    HTTP headers are case-insensitive per RFC 7230.
    """
    for name, value in request.headers.items():
        if name.lower() == header_name.lower():
            return value.strip() if value else None
    return None


def _get_cognito_sub(request: Request) -> str:
    """Extract cognito_sub from x-user-sub header injected by API Gateway.

    API Gateway validates the JWT token using Cognito authorizer and injects
    the x-user-sub header with the cognito sub claim. This header is trusted
    because it comes from API Gateway after successful JWT validation.

    Args:
        request: FastAPI request object

    Returns:
        The cognito sub (user identifier) from the validated JWT

    Raises:
        HTTPException: 401 if x-user-sub header is missing or empty

    Usage:
        @router.get("/me")
        def get_profile(cognito_sub: str = Depends(_get_cognito_sub)):
            return {"user_id": cognito_sub}
    """
    cognito_sub = _get_header_case_insensitive(request, "x-user-sub")

    if cognito_sub is None:
        logger.warning(
            "auth_header_missing",
            extra={"header": "x-user-sub", "path": request.url.path},
        )
        raise HTTPException(
            status_code=401,
            detail="Authentication required: missing x-user-sub header",
        )

    if not cognito_sub:
        logger.warning(
            "auth_header_empty",
            extra={"header": "x-user-sub", "path": request.url.path},
        )
        raise HTTPException(
            status_code=401,
            detail="Authentication required: empty x-user-sub header",
        )

    logger.debug(
        "auth_header_extracted",
        extra={"cognito_sub": cognito_sub[:8] + "...", "path": request.url.path},
    )
    return cognito_sub


def _get_user_email(request: Request) -> str:
    """Extract email from x-user-email header injected by API Gateway.

    API Gateway extracts the email claim from the validated JWT and injects
    it as the x-user-email header.

    Args:
        request: FastAPI request object

    Returns:
        The user's email from the validated JWT

    Raises:
        HTTPException: 400 if x-user-email header is missing or empty
    """
    email = _get_header_case_insensitive(request, "x-user-email")

    if not email:
        logger.warning(
            "email_header_missing",
            extra={"header": "x-user-email", "path": request.url.path},
        )
        raise HTTPException(
            status_code=400,
            detail="Missing email: x-user-email header required",
        )

    # Log with masked email for privacy (show first 3 chars + domain)
    masked_email = email[:3] + "***" + email[email.find("@") :] if "@" in email else "***"
    logger.debug(
        "email_header_extracted",
        extra={"email_masked": masked_email, "path": request.url.path},
    )
    return email


# === Pydantic Models (T006b) ===


class CustomerCreate(BaseModel):
    """Data for creating customer profile.

    All fields are optional - email comes from JWT claims.
    """

    model_config = ConfigDict(strict=True)

    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="Full name (2-100 characters)",
    )
    phone: str | None = Field(
        default=None,
        min_length=7,
        max_length=20,
        description="Phone number (7-20 characters)",
    )
    preferred_language: str = Field(
        default="en",
        pattern=r"^(en|es)$",
        description="Preferred language (en or es)",
    )


class CustomerUpdate(BaseModel):
    """Fields that can be updated for a customer profile.

    All fields are optional - only provided fields are updated.
    """

    model_config = ConfigDict(strict=True)

    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="Full name (2-100 characters)",
    )
    phone: str | None = Field(
        default=None,
        min_length=7,
        max_length=20,
        description="Phone number (7-20 characters)",
    )
    preferred_language: str | None = Field(
        default=None,
        pattern=r"^(en|es)$",
        description="Preferred language (en or es)",
    )


class CustomerResponse(BaseModel):
    """Customer profile response model.

    Returns the full customer profile after GET, POST, or PUT operations.
    """

    model_config = ConfigDict(strict=True)

    guest_id: str = Field(..., description="Unique guest ID (UUID)")
    email: str = Field(..., description="Guest email address")
    cognito_sub: str | None = Field(default=None, description="Cognito user sub")
    name: str | None = Field(default=None, description="Full name")
    phone: str | None = Field(default=None, description="Phone number")
    preferred_language: str = Field(default="en", description="Preferred language")
    email_verified: bool = Field(default=False, description="Email verified status")
    created_at: str | None = Field(default=None, description="Creation timestamp")
    updated_at: str | None = Field(default=None, description="Last update timestamp")


# === Router Setup ===

router = APIRouter(prefix="/customers", tags=["customers"])


# === Endpoint Implementations (T029b-T033) ===


@router.get("/me", response_model=CustomerResponse)
def get_customer_me(
    cognito_sub: str = Depends(_get_cognito_sub),
    auth: SecurityRequirement = Depends(require_auth([AuthScope.OPENID])),
) -> dict[str, Any]:
    """Get current customer profile.

    Retrieves the authenticated user's profile using their cognito_sub.

    Returns:
        CustomerResponse: The customer profile

    Raises:
        HTTPException: 401 if not authenticated, 404 if profile not found
    """
    db = get_dynamodb_service()
    guest = db.get_guest_by_cognito_sub(cognito_sub)

    if guest is None:
        logger.info(
            "customer_profile_not_found",
            extra={"cognito_sub": cognito_sub[:8] + "...", "action": "get"},
        )
        raise HTTPException(
            status_code=404,
            detail="Customer profile not found",
        )

    logger.info(
        "customer_profile_retrieved",
        extra={
            "cognito_sub": cognito_sub[:8] + "...",
            "guest_id": guest.get("guest_id", "")[:8] + "...",
        },
    )
    return guest


@router.post("/me", response_model=CustomerResponse, status_code=201)
def create_customer_me(
    request: Request,
    data: CustomerCreate,
    cognito_sub: str = Depends(_get_cognito_sub),
    auth: SecurityRequirement = Depends(require_auth([AuthScope.OPENID])),
) -> dict[str, Any]:
    """Create customer profile for authenticated user.

    Creates a new profile using cognito_sub from JWT and email from x-user-email header.

    Returns:
        CustomerResponse: The created customer profile

    Raises:
        HTTPException: 401 if not authenticated, 400 if email missing, 409 if profile exists
    """
    # Get email from header (injected by API Gateway from JWT)
    email = _get_user_email(request)

    db = get_dynamodb_service()

    # Check if profile already exists
    existing = db.get_guest_by_cognito_sub(cognito_sub)
    if existing is not None:
        logger.warning(
            "customer_profile_already_exists",
            extra={
                "cognito_sub": cognito_sub[:8] + "...",
                "existing_guest_id": existing.get("guest_id", "")[:8] + "...",
            },
        )
        raise HTTPException(
            status_code=409,
            detail="Customer profile already exists",
        )

    # Create new guest record
    now = datetime.now(timezone.utc).isoformat()
    guest_id = str(uuid.uuid4())
    guest = {
        "guest_id": guest_id,
        "email": email,
        "cognito_sub": cognito_sub,
        "name": data.name,
        "phone": data.phone,
        "preferred_language": data.preferred_language,
        "email_verified": True,  # Email verified via Cognito
        "created_at": now,
        "updated_at": now,
    }

    db.create_guest(guest)

    # Mask email for logging (privacy)
    masked_email = email[:3] + "***" + email[email.find("@") :] if "@" in email else "***"
    logger.info(
        "customer_profile_created",
        extra={
            "cognito_sub": cognito_sub[:8] + "...",
            "guest_id": guest_id[:8] + "...",
            "email_masked": masked_email,
            "preferred_language": data.preferred_language,
        },
    )
    return guest


@router.put("/me", response_model=CustomerResponse)
def update_customer_me(
    data: CustomerUpdate,
    cognito_sub: str = Depends(_get_cognito_sub),
    auth: SecurityRequirement = Depends(require_auth([AuthScope.OPENID])),
) -> dict[str, Any]:
    """Update current customer profile.

    Updates only the fields that are provided (partial update).

    Returns:
        CustomerResponse: The updated customer profile

    Raises:
        HTTPException: 401 if not authenticated, 404 if profile not found
    """
    db = get_dynamodb_service()

    # Check if profile exists
    existing = db.get_guest_by_cognito_sub(cognito_sub)
    if existing is None:
        logger.info(
            "customer_profile_not_found",
            extra={"cognito_sub": cognito_sub[:8] + "...", "action": "update"},
        )
        raise HTTPException(
            status_code=404,
            detail="Customer profile not found",
        )

    # Build update expression for provided fields only
    update_fields: dict[str, Any] = {}
    if data.name is not None:
        update_fields["name"] = data.name
    if data.phone is not None:
        update_fields["phone"] = data.phone
    if data.preferred_language is not None:
        update_fields["preferred_language"] = data.preferred_language

    # Always update updated_at timestamp
    update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Build DynamoDB update expression
    update_parts = []
    expression_values = {}
    expression_names = {}

    for idx, (field, value) in enumerate(update_fields.items()):
        placeholder = f":v{idx}"
        name_placeholder = f"#n{idx}"
        update_parts.append(f"{name_placeholder} = {placeholder}")
        expression_values[placeholder] = value
        expression_names[name_placeholder] = field

    update_expression = "SET " + ", ".join(update_parts)

    result = db.update_item(
        table="guests",
        key={"guest_id": existing["guest_id"]},
        update_expression=update_expression,
        expression_attribute_values=expression_values,
        expression_attribute_names=expression_names,
    )

    # Log which fields were updated (excluding timestamp)
    updated_field_names = [k for k in update_fields.keys() if k != "updated_at"]
    logger.info(
        "customer_profile_updated",
        extra={
            "cognito_sub": cognito_sub[:8] + "...",
            "guest_id": existing.get("guest_id", "")[:8] + "...",
            "updated_fields": updated_field_names,
        },
    )

    return result if result else existing
