"""OAuth2 session models for AgentCore Identity integration.

This module defines the OAuth2Session model for tracking the mapping between
AgentCore session_id and guest_email. This enables user identity verification
in the callback flow via CompleteResourceTokenAuth.

Key insight: AgentCore handles OAuth2 state, PKCE, and code exchange internally.
The application only needs to correlate session_id → guest_email for user verification.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class OAuth2SessionStatus(str, Enum):
    """Status of an OAuth2 authentication session."""

    PENDING = "pending"  # Waiting for user to complete auth
    COMPLETED = "completed"  # User verified successfully
    EXPIRED = "expired"  # Session timed out (10 minutes)
    FAILED = "failed"  # Auth failed (user mismatch, cancelled, error)


class OAuth2Session(BaseModel):
    """OAuth2 session for conversation-to-callback bridge.

    Unlike browser-based applications (which use cookies), agent conversations
    have no browser session. This model bridges that gap:

    1. Agent initiates OAuth2 → stores session_id → guest_email mapping
    2. HTTP callback receives session_id → looks up guest_email from table
    3. Callback calls CompleteResourceTokenAuth(session_uri, user_identifier)

    AgentCore handles state, PKCE, and code exchange internally.
    """

    model_config = ConfigDict(strict=True)

    session_id: str = Field(
        ...,
        description="Session URI from AgentCore (maps to sessionUri in CompleteResourceTokenAuth)",
    )
    conversation_id: str = Field(
        ..., description="AgentCore conversation ID for session binding"
    )
    guest_email: str = Field(
        ..., description="Email of guest initiating auth (for user verification)"
    )
    status: OAuth2SessionStatus = Field(
        default=OAuth2SessionStatus.PENDING, description="Session status"
    )
    created_at: datetime = Field(..., description="Creation timestamp (UTC)")
    expires_at: int = Field(
        ..., description="Unix epoch timestamp for DynamoDB TTL (10 min from creation)"
    )


class OAuth2SessionCreate(BaseModel):
    """Data required to create a new OAuth2 session.

    Used when initiating an OAuth2 flow from an agent tool.
    """

    model_config = ConfigDict(strict=True)

    session_id: str = Field(..., description="From AgentCore when initiating OAuth2")
    conversation_id: str = Field(..., description="Current agent conversation ID")
    guest_email: EmailStr = Field(..., description="Guest email for user verification")
