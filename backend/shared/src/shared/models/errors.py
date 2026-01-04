"""Standard error codes for the Booking Agent.

Based on the error_handling specification in contracts/agent-tools.json.
All tools should use these error codes for consistent error responses.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ErrorCode(str, Enum):
    """Standard error codes as defined in agent-tools.json."""

    # Booking error codes (ERR_001-ERR_008)
    DATES_UNAVAILABLE = "ERR_001"
    MINIMUM_NIGHTS_NOT_MET = "ERR_002"
    MAX_GUESTS_EXCEEDED = "ERR_003"
    VERIFICATION_REQUIRED = "ERR_004"
    VERIFICATION_FAILED = "ERR_005"
    RESERVATION_NOT_FOUND = "ERR_006"
    UNAUTHORIZED = "ERR_007"
    PAYMENT_FAILED = "ERR_008"

    # Authentication error codes (ERR_AUTH_001-ERR_AUTH_008)
    AUTH_REQUIRED = "ERR_AUTH_001"
    INVALID_OTP = "ERR_AUTH_002"
    OTP_EXPIRED = "ERR_AUTH_003"
    MAX_ATTEMPTS_EXCEEDED = "ERR_AUTH_004"
    EMAIL_DELIVERY_FAILED = "ERR_AUTH_005"
    SESSION_EXPIRED = "ERR_AUTH_006"
    AUTH_CANCELLED = "ERR_AUTH_007"
    USER_MISMATCH = "ERR_AUTH_008"

    # Stripe/Payment error codes (ERR_STRIPE_001-ERR_STRIPE_003)
    INVALID_WEBHOOK_SIGNATURE = "ERR_STRIPE_001"
    STRIPE_API_ERROR = "ERR_STRIPE_002"
    RESERVATION_NOT_PAYABLE = "ERR_STRIPE_003"


# Human-readable error messages
ERROR_MESSAGES: dict[ErrorCode, str] = {
    # Booking errors
    ErrorCode.DATES_UNAVAILABLE: "The requested dates are not available",
    ErrorCode.MINIMUM_NIGHTS_NOT_MET: "Minimum stay requirement not met for this season",
    ErrorCode.MAX_GUESTS_EXCEEDED: "Number of guests exceeds maximum capacity (4)",
    ErrorCode.VERIFICATION_REQUIRED: "Guest verification required before booking",
    ErrorCode.VERIFICATION_FAILED: "Verification code invalid or expired",
    ErrorCode.RESERVATION_NOT_FOUND: "Reservation not found",
    ErrorCode.UNAUTHORIZED: "Guest not authorized for this action",
    ErrorCode.PAYMENT_FAILED: "Payment processing failed",
    # Authentication errors
    ErrorCode.AUTH_REQUIRED: "Authentication required to perform this action",
    ErrorCode.INVALID_OTP: "The verification code is incorrect",
    ErrorCode.OTP_EXPIRED: "The verification code has expired",
    ErrorCode.MAX_ATTEMPTS_EXCEEDED: "Maximum verification attempts exceeded",
    ErrorCode.EMAIL_DELIVERY_FAILED: "Failed to send verification email",
    ErrorCode.SESSION_EXPIRED: "Authentication session has expired",
    ErrorCode.AUTH_CANCELLED: "Authentication was cancelled by user",
    ErrorCode.USER_MISMATCH: "User identity does not match the expected user",
    # Stripe errors
    ErrorCode.INVALID_WEBHOOK_SIGNATURE: "Invalid webhook signature",
    ErrorCode.STRIPE_API_ERROR: "Stripe API error occurred",
    ErrorCode.RESERVATION_NOT_PAYABLE: "Reservation is not in a payable state",
}

# Recovery suggestions for agents
ERROR_RECOVERY: dict[ErrorCode, str] = {
    # Booking error recovery
    ErrorCode.DATES_UNAVAILABLE: "Suggest alternative dates using get_calendar",
    ErrorCode.MINIMUM_NIGHTS_NOT_MET: "Inform guest of minimum nights and suggest extending stay",
    ErrorCode.MAX_GUESTS_EXCEEDED: "Inform guest of max capacity",
    ErrorCode.VERIFICATION_REQUIRED: "Initiate verification flow with initiate_verification",
    ErrorCode.VERIFICATION_FAILED: "Offer to resend verification code",
    ErrorCode.RESERVATION_NOT_FOUND: "Ask guest to verify reservation ID",
    ErrorCode.UNAUTHORIZED: "Verify guest owns the reservation",
    ErrorCode.PAYMENT_FAILED: "Suggest trying again or different payment method",
    # Authentication error recovery
    ErrorCode.AUTH_REQUIRED: "Initiate login flow with initiate_cognito_login",
    ErrorCode.INVALID_OTP: "Ask guest to re-enter code or request new code",
    ErrorCode.OTP_EXPIRED: "Request a new verification code",
    ErrorCode.MAX_ATTEMPTS_EXCEEDED: "Request a new verification code",
    ErrorCode.EMAIL_DELIVERY_FAILED: "Verify email address is correct and try again",
    ErrorCode.SESSION_EXPIRED: "Start a new login flow",
    ErrorCode.AUTH_CANCELLED: "Offer to restart authentication if needed",
    ErrorCode.USER_MISMATCH: "Restart authentication with the correct email",
    # Stripe error recovery
    ErrorCode.INVALID_WEBHOOK_SIGNATURE: "Verify webhook secret configuration",
    ErrorCode.STRIPE_API_ERROR: "Try again or contact support",
    ErrorCode.RESERVATION_NOT_PAYABLE: "Verify reservation status is pending",
}


class ToolError(BaseModel):
    """Standard error response format for tool failures.

    All tools should return this format when an error occurs.
    The agent uses the recovery hint to determine next steps.
    """

    model_config = ConfigDict(strict=True)

    success: bool = False
    error_code: ErrorCode
    message: str
    recovery: str
    details: Optional[dict[str, str]] = None

    @classmethod
    def from_code(
        cls,
        code: ErrorCode,
        details: Optional[dict[str, str]] = None,
    ) -> "ToolError":
        """Create a ToolError from an error code.

        Args:
            code: The error code
            details: Optional additional context about the error

        Returns:
            A ToolError with the message and recovery hint for the code.
        """
        return cls(
            error_code=code,
            message=ERROR_MESSAGES[code],
            recovery=ERROR_RECOVERY[code],
            details=details,
        )


class BookingError(Exception):
    """Exception raised by booking operations.

    Can be caught and converted to a ToolError for agent responses.
    """

    def __init__(
        self,
        code: ErrorCode,
        details: Optional[dict[str, str]] = None,
    ):
        self.code = code
        self.message = ERROR_MESSAGES[code]
        self.recovery = ERROR_RECOVERY[code]
        self.details = details
        super().__init__(self.message)

    def to_tool_error(self) -> ToolError:
        """Convert this exception to a ToolError for tool responses."""
        return ToolError.from_code(self.code, self.details)


# Stripe error code to user-friendly message mapping (FR-023)
# Maps Stripe's error codes to messages suitable for end users
STRIPE_ERROR_MESSAGES: dict[str, str] = {
    # Card errors - user can fix
    "card_declined": "Your card was declined. Please try a different card.",
    "expired_card": "Your card has expired. Please use a different card.",
    "insufficient_funds": "Your card has insufficient funds. Please try a different card.",
    "incorrect_cvc": "The security code (CVC) is incorrect. Please check and try again.",
    "incorrect_number": "The card number is incorrect. Please check and try again.",
    "invalid_cvc": "The security code (CVC) is invalid. Please check and try again.",
    "invalid_expiry_month": "The expiration month is invalid. Please check and try again.",
    "invalid_expiry_year": "The expiration year is invalid. Please check and try again.",
    "invalid_number": "The card number is invalid. Please check and try again.",
    "card_velocity_exceeded": "Too many card transactions. Please wait and try again later.",
    # Processing errors - may be retryable
    "processing_error": "A processing error occurred. Please try again.",
    "rate_limit": "Too many requests. Please wait a moment and try again.",
    # Generic fallback
    "generic_decline": "Your card was declined. Please try a different card.",
}

# Stripe error codes that indicate the user should retry
STRIPE_RETRYABLE_ERRORS: set[str] = {
    "processing_error",
    "rate_limit",
    "lock_timeout",
    "api_connection_error",
}


def get_user_friendly_stripe_message(
    stripe_error_code: Optional[str],
    default_message: str = "Payment could not be processed. Please try again.",
) -> str:
    """Get a user-friendly message for a Stripe error code (FR-023).

    Args:
        stripe_error_code: The Stripe error code (e.g., 'card_declined').
        default_message: Message to use if error code is unknown.

    Returns:
        User-friendly error message.
    """
    if stripe_error_code and stripe_error_code in STRIPE_ERROR_MESSAGES:
        return STRIPE_ERROR_MESSAGES[stripe_error_code]
    return default_message


def is_stripe_error_retryable(stripe_error_code: Optional[str]) -> bool:
    """Check if a Stripe error is likely transient and retryable.

    Args:
        stripe_error_code: The Stripe error code.

    Returns:
        True if the error may be resolved by retrying.
    """
    return stripe_error_code in STRIPE_RETRYABLE_ERRORS if stripe_error_code else False
