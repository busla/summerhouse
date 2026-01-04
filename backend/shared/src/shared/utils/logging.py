"""Structured logging utilities with correlation ID support.

Provides:
- Correlation ID context management for request tracing
- Structured logging formatter for consistent log output
- Helper functions for payment operation logging

Usage:
    from shared.utils.logging import get_logger, set_correlation_id, get_correlation_id

    # In middleware/request handler:
    set_correlation_id(request.headers.get("X-Correlation-ID"))

    # In service code:
    logger = get_logger(__name__)
    logger.info("Processing payment", extra={"payment_id": "PAY-123"})
"""

import logging
import uuid
from contextvars import ContextVar
from typing import Any

# Context variable for correlation ID - thread-safe and async-safe
_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def generate_correlation_id() -> str:
    """Generate a new correlation ID.

    Returns:
        UUID-based correlation ID string
    """
    return str(uuid.uuid4())


def set_correlation_id(correlation_id: str | None = None) -> str:
    """Set the correlation ID for the current request context.

    Args:
        correlation_id: Optional existing correlation ID. If None, generates new one.

    Returns:
        The correlation ID that was set
    """
    cid = correlation_id or generate_correlation_id()
    _correlation_id.set(cid)
    return cid


def get_correlation_id() -> str | None:
    """Get the current correlation ID.

    Returns:
        Current correlation ID or None if not set
    """
    return _correlation_id.get()


def clear_correlation_id() -> None:
    """Clear the correlation ID context."""
    _correlation_id.set(None)


class CorrelationIdFilter(logging.Filter):
    """Logging filter that adds correlation_id to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation_id to the log record.

        Args:
            record: Log record to modify

        Returns:
            True (always allows the record through)
        """
        record.correlation_id = get_correlation_id() or "no-correlation-id"
        return True


class StructuredFormatter(logging.Formatter):
    """Formatter for structured log output with correlation ID."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with structured fields.

        Args:
            record: Log record to format

        Returns:
            Formatted log string
        """
        # Ensure correlation_id exists
        if not hasattr(record, "correlation_id"):
            record.correlation_id = get_correlation_id() or "no-correlation-id"

        # Build base message
        base = super().format(record)

        # Add correlation ID prefix for easy grep/filtering
        return f"[{record.correlation_id}] {base}"


def get_logger(name: str) -> logging.Logger:
    """Get a logger with correlation ID support.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Add correlation ID filter if not already present
    if not any(isinstance(f, CorrelationIdFilter) for f in logger.filters):
        logger.addFilter(CorrelationIdFilter())

    return logger


def log_payment_operation(
    logger: logging.Logger,
    operation: str,
    *,
    payment_id: str | None = None,
    reservation_id: str | None = None,
    amount_cents: int | None = None,
    status: str | None = None,
    error: str | None = None,
    **extra: Any,
) -> None:
    """Log a payment operation with structured context.

    Args:
        logger: Logger instance
        operation: Operation name (e.g., "create_checkout_session", "process_refund")
        payment_id: Payment ID if available
        reservation_id: Reservation ID if available
        amount_cents: Amount in cents if relevant
        status: Payment/transaction status
        error: Error message if operation failed
        **extra: Additional context fields
    """
    context: dict[str, Any] = {"operation": operation}

    if payment_id:
        context["payment_id"] = payment_id
    if reservation_id:
        context["reservation_id"] = reservation_id
    if amount_cents is not None:
        context["amount_cents"] = amount_cents
    if status:
        context["status"] = status
    if error:
        context["error"] = error

    context.update(extra)

    # Build message
    msg_parts = [f"Payment operation: {operation}"]
    for key, value in context.items():
        if key != "operation":
            msg_parts.append(f"{key}={value}")

    message = " | ".join(msg_parts)

    if error:
        logger.error(message, extra=context)
    else:
        logger.info(message, extra=context)


def log_webhook_event(
    logger: logging.Logger,
    event_type: str,
    event_id: str,
    *,
    reservation_id: str | None = None,
    payment_id: str | None = None,
    result: str | None = None,
    error: str | None = None,
    **extra: Any,
) -> None:
    """Log a webhook event with structured context.

    Args:
        logger: Logger instance
        event_type: Stripe event type (e.g., "checkout.session.completed")
        event_id: Stripe event ID
        reservation_id: Associated reservation ID if available
        payment_id: Associated payment ID if available
        result: Processing result (success, duplicate, skipped, error)
        error: Error message if processing failed
        **extra: Additional context fields
    """
    context: dict[str, Any] = {
        "event_type": event_type,
        "event_id": event_id,
    }

    if reservation_id:
        context["reservation_id"] = reservation_id
    if payment_id:
        context["payment_id"] = payment_id
    if result:
        context["result"] = result
    if error:
        context["error"] = error

    context.update(extra)

    # Build message
    msg_parts = [f"Webhook event: {event_type} ({event_id})"]
    if result:
        msg_parts.append(f"result={result}")
    if reservation_id:
        msg_parts.append(f"reservation={reservation_id}")
    if error:
        msg_parts.append(f"error={error}")

    message = " | ".join(msg_parts)

    if result == "error":
        logger.error(message, extra=context)
    elif result == "duplicate" or result == "skipped":
        logger.warning(message, extra=context)
    else:
        logger.info(message, extra=context)
