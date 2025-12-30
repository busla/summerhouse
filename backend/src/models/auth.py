"""Authentication models for Cognito passwordless login and AgentCore Identity.

This module defines models for:
- CognitoAuthState: Tracks USER_AUTH flow state (EMAIL_OTP)
- AuthResult: Result of OTP verification
- TokenDeliveryEvent: Structured token delivery for frontend (T001)
- WorkloadToken: Agent workload access token (in-memory only)
"""

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CognitoAuthChallenge(str, Enum):
    """Cognito authentication challenges supported by passwordless flow."""

    EMAIL_OTP = "EMAIL_OTP"


class CognitoAuthState(BaseModel):
    """Tracks Cognito USER_AUTH flow state within a single authentication attempt.

    This is an in-memory model - not persisted to DynamoDB.
    Used to track the Cognito session between initiate_auth and respond_to_auth_challenge.
    """

    model_config = ConfigDict(strict=True)

    session: str = Field(..., description="Cognito session token from initiate_auth")
    challenge: CognitoAuthChallenge = Field(..., description="Current challenge type")
    username: str = Field(..., description="Cognito username (email)")
    attempts: int = Field(default=0, ge=0, le=3, description="OTP attempt count")
    otp_sent_at: datetime = Field(..., description="When OTP was sent (UTC)")

    @property
    def max_attempts_reached(self) -> bool:
        """Check if max OTP attempts (3) reached per FR-014."""
        return self.attempts >= 3

    @property
    def is_otp_expired(self) -> bool:
        """Check if OTP has expired (5-minute validity per FR-013)."""
        expiry = self.otp_sent_at + timedelta(minutes=5)
        return datetime.now(timezone.utc) > expiry


class AuthResult(BaseModel):
    """Result of OTP verification or authentication flow.

    Updated per T002 to include Cognito token fields for token delivery.
    """

    model_config = ConfigDict(strict=True)

    success: bool = Field(..., description="Whether authentication succeeded")
    guest_id: str | None = Field(default=None, description="Guest ID if authenticated")
    cognito_sub: str | None = Field(default=None, description="Cognito sub claim")
    error_code: str | None = Field(default=None, description="Error code if failed")
    message: str = Field(..., description="Human-readable status message")

    # Token fields for successful authentication (T002)
    id_token: str | None = Field(default=None, description="Cognito ID token (JWT)")
    access_token: str | None = Field(default=None, description="Cognito access token (JWT)")
    refresh_token: str | None = Field(default=None, description="Cognito refresh token")
    expires_in: int | None = Field(default=None, description="Token expiry in seconds")


class WorkloadToken(BaseModel):
    """Agent workload access token from AgentCore Identity.

    This is an in-memory model - not persisted.
    Used for agent-to-AgentCore API authentication.
    Tokens are cached and auto-refreshed by the SDK.
    """

    model_config = ConfigDict(strict=True)

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_at: datetime = Field(..., description="Token expiration time (UTC)")
    workload_name: str | None = Field(default=None, description="Workload identity name")
    user_id: str | None = Field(default=None, description="User ID if user-delegated")

    @property
    def is_expired(self) -> bool:
        """Check if token is expired (with 30-second buffer for network latency)."""
        return datetime.now(timezone.utc) >= (self.expires_at - timedelta(seconds=30))


class OAuth2CompletionResult(BaseModel):
    """Result of completing an OAuth2 3LO flow via CompleteResourceTokenAuth.

    Used to communicate success/failure and any errors from the OAuth2 callback
    processing to the caller.
    """

    model_config = ConfigDict(strict=True)

    success: bool = Field(..., description="Whether OAuth2 completion succeeded")
    error_code: str | None = Field(default=None, description="Error code if failed")
    message: str | None = Field(default=None, description="Human-readable message")


class TokenDeliveryEvent(BaseModel):
    """Structured token delivery event for frontend session storage (T001).

    This type-discriminated event is returned by verify_cognito_otp on success.
    The frontend detects this event via `event_type: "auth_tokens"` and extracts
    tokens for localStorage storage.

    Per spec clarification #1: Direct localStorage storage, no Amplify Auth.
    Per spec clarification #2: Tokens passed in request payload, not header.
    """

    model_config = ConfigDict(strict=True)

    # Type discriminator for frontend detection
    event_type: Literal["auth_tokens"] = Field(
        default="auth_tokens",
        description="Event type discriminator for frontend detection",
    )
    success: Literal[True] = Field(
        default=True,
        description="Always true for token delivery events",
    )

    # Cognito JWT tokens
    id_token: str = Field(..., min_length=1, description="Cognito ID token (JWT)")
    access_token: str = Field(..., min_length=1, description="Cognito access token (JWT)")
    refresh_token: str = Field(..., min_length=1, description="Cognito refresh token")
    expires_in: int = Field(..., gt=0, description="Token expiry in seconds")

    # User identity
    guest_id: str = Field(..., description="Guest profile ID")
    email: str = Field(..., description="Verified email address")
    cognito_sub: str = Field(
        ...,
        min_length=36,
        max_length=36,
        description="Cognito user sub (UUID format)",
    )
