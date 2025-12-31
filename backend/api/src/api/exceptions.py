"""FastAPI exception handlers for converting BookingError to HTTP responses.

This module provides exception handlers that convert domain errors (BookingError)
to appropriate HTTP responses with consistent JSON structure matching ToolError.

The ErrorCode-to-HTTP status mapping follows REST conventions:
- 400 Bad Request: Validation/business rule violations
- 401 Unauthorized: Authentication required or failed
- 402 Payment Required: Payment failures
- 403 Forbidden: Authorization failures
- 404 Not Found: Resource not found
- 429 Too Many Requests: Rate limiting

Usage:
    Register handlers in FastAPI app:

    from api.exceptions import register_exception_handlers
    register_exception_handlers(app)
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_402_PAYMENT_REQUIRED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from shared.models.errors import BookingError, ErrorCode, ToolError

# Map ErrorCode to HTTP status codes
ERROR_CODE_TO_HTTP_STATUS: dict[ErrorCode, int] = {
    # Business validation errors -> 400 Bad Request
    ErrorCode.DATES_UNAVAILABLE: HTTP_400_BAD_REQUEST,
    ErrorCode.MINIMUM_NIGHTS_NOT_MET: HTTP_400_BAD_REQUEST,
    ErrorCode.MAX_GUESTS_EXCEEDED: HTTP_400_BAD_REQUEST,
    # Authentication errors -> 401 Unauthorized
    ErrorCode.AUTH_REQUIRED: HTTP_401_UNAUTHORIZED,
    ErrorCode.INVALID_OTP: HTTP_401_UNAUTHORIZED,
    ErrorCode.OTP_EXPIRED: HTTP_401_UNAUTHORIZED,
    ErrorCode.SESSION_EXPIRED: HTTP_401_UNAUTHORIZED,
    ErrorCode.AUTH_CANCELLED: HTTP_401_UNAUTHORIZED,
    # Authorization errors -> 403 Forbidden
    ErrorCode.UNAUTHORIZED: HTTP_403_FORBIDDEN,
    ErrorCode.USER_MISMATCH: HTTP_403_FORBIDDEN,
    # Verification required -> 403 (need to verify first)
    ErrorCode.VERIFICATION_REQUIRED: HTTP_403_FORBIDDEN,
    ErrorCode.VERIFICATION_FAILED: HTTP_401_UNAUTHORIZED,
    # Not found errors -> 404 Not Found
    ErrorCode.RESERVATION_NOT_FOUND: HTTP_404_NOT_FOUND,
    # Payment errors -> 402 Payment Required
    ErrorCode.PAYMENT_FAILED: HTTP_402_PAYMENT_REQUIRED,
    # Rate limiting -> 429 Too Many Requests
    ErrorCode.MAX_ATTEMPTS_EXCEEDED: HTTP_429_TOO_MANY_REQUESTS,
    # Email delivery -> 500 (server-side issue)
    ErrorCode.EMAIL_DELIVERY_FAILED: HTTP_500_INTERNAL_SERVER_ERROR,
}


def get_http_status_for_error(code: ErrorCode) -> int:
    """Get HTTP status code for an ErrorCode.

    Args:
        code: The ErrorCode to map

    Returns:
        HTTP status code, defaults to 400 if not explicitly mapped.
    """
    return ERROR_CODE_TO_HTTP_STATUS.get(code, HTTP_400_BAD_REQUEST)


async def booking_error_handler(request: Request, exc: BookingError) -> JSONResponse:
    """Handle BookingError exceptions and convert to JSON response.

    Converts domain-specific BookingError to a JSON response with:
    - Appropriate HTTP status code based on error type
    - ToolError-compatible JSON body for consistency

    Args:
        request: The incoming request (unused but required by FastAPI)
        exc: The BookingError exception

    Returns:
        JSONResponse with error details and appropriate status code.
    """
    status_code = get_http_status_for_error(exc.code)
    tool_error = exc.to_tool_error()

    return JSONResponse(
        status_code=status_code,
        content=tool_error.model_dump(mode="json"),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with a generic error response.

    Provides a fallback handler for uncaught exceptions to ensure
    consistent error format across all endpoints.

    Args:
        request: The incoming request (unused but required by FastAPI)
        exc: The uncaught exception

    Returns:
        JSONResponse with 500 status and generic error message.
    """
    # Log the actual error for debugging (in production, use proper logging)
    import logging

    logger = logging.getLogger(__name__)
    logger.exception("Unhandled exception: %s", exc)

    # Return generic error to client (don't expose internal details)
    error_response = {
        "success": False,
        "error_code": "ERR_INTERNAL",
        "message": "An unexpected error occurred",
        "recovery": "Please try again later or contact support",
        "details": None,
    }

    return JSONResponse(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with the FastAPI app.

    Call this function during app initialization to enable
    consistent error handling across all routes.

    Args:
        app: The FastAPI application instance.

    Example:
        app = FastAPI()
        register_exception_handlers(app)
    """
    app.add_exception_handler(BookingError, booking_error_handler)  # type: ignore[arg-type]
    # Note: Generic exception handler is optional - uncomment if you want
    # to catch ALL unhandled exceptions (may interfere with debugging)
    # app.add_exception_handler(Exception, generic_exception_handler)
