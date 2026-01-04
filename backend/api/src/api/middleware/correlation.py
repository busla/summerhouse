"""Correlation ID middleware for request tracing.

Extracts X-Correlation-ID header from incoming requests or generates a new one.
Makes correlation ID available throughout the request lifecycle via contextvars.
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from shared.utils.logging import clear_correlation_id, get_correlation_id, set_correlation_id

CORRELATION_ID_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware that manages correlation IDs for request tracing."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request and add correlation ID.

        Args:
            request: Incoming request
            call_next: Next middleware/handler in chain

        Returns:
            Response with correlation ID header
        """
        # Extract existing correlation ID or generate new one
        incoming_id = request.headers.get(CORRELATION_ID_HEADER)
        correlation_id = set_correlation_id(incoming_id)

        try:
            # Process the request
            response = await call_next(request)

            # Add correlation ID to response headers
            response.headers[CORRELATION_ID_HEADER] = correlation_id

            return response
        finally:
            # Clear correlation ID after request completes
            clear_correlation_id()
