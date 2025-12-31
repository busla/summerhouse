"""Shared API request/response models.

This module contains common models used across multiple API endpoints,
including error response wrappers and validation error formatting.

Domain-specific models (Reservation, Guest, etc.) are in shared.models
and should be imported from there. This module provides HTTP/API layer
specific concerns only.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Re-export ToolError for convenience - this is the standard error format
from shared.models.errors import ErrorCode, ToolError

__all__ = [
    "ErrorCode",
    "ToolError",
    "ValidationErrorResponse",
    "ValidationErrorDetail",
    "SuccessMessage",
]


class ValidationErrorDetail(BaseModel):
    """Detail of a single validation error."""

    model_config = ConfigDict(strict=True)

    loc: list[str | int] = Field(
        ...,
        description="Path to the field that failed validation",
        examples=[["body", "check_in"]],
    )
    msg: str = Field(
        ...,
        description="Human-readable error message",
        examples=["field required"],
    )
    type: str = Field(
        ...,
        description="Error type identifier",
        examples=["value_error.missing"],
    )


class ValidationErrorResponse(BaseModel):
    """Response format for request validation errors (HTTP 422).

    This format matches FastAPI's default validation error response
    but wrapped in our standard error structure for consistency.
    """

    model_config = ConfigDict(strict=True)

    success: bool = False
    error_code: str = "ERR_VALIDATION"
    message: str = "Request validation failed"
    recovery: str = "Check the request parameters and try again"
    details: list[ValidationErrorDetail] = Field(default_factory=list)


class SuccessMessage(BaseModel):
    """Generic success response for operations without data payload.

    Used for endpoints that just need to acknowledge success,
    like DELETE operations or status updates.
    """

    model_config = ConfigDict(strict=True)

    success: bool = True
    message: str = Field(
        default="Operation completed successfully",
        description="Human-readable success message",
    )


def format_validation_errors(errors: list[dict[str, Any]]) -> ValidationErrorResponse:
    """Convert Pydantic validation errors to ValidationErrorResponse.

    Args:
        errors: List of error dicts from Pydantic's ValidationError.errors()

    Returns:
        ValidationErrorResponse ready for JSON serialization.

    Example:
        try:
            request = SomeRequest(**data)
        except ValidationError as e:
            return JSONResponse(
                status_code=422,
                content=format_validation_errors(e.errors()).model_dump()
            )
    """
    details = [
        ValidationErrorDetail(
            loc=[str(loc) for loc in error.get("loc", [])],
            msg=error.get("msg", ""),
            type=error.get("type", ""),
        )
        for error in errors
    ]
    return ValidationErrorResponse(details=details)
