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
