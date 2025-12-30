# Data Model: AgentCore Identity OAuth2 Login

**Feature**: 003-agentcore-identity-oauth2
**Date**: 2025-12-29
**Storage**: AWS DynamoDB (OAuth2 sessions), AWS Cognito (user identity)

## Overview

This document defines the data model additions for AgentCore Identity OAuth2 authentication. The feature introduces one new DynamoDB table for OAuth2 session state and extends the existing Guest model with Cognito identity binding.

## Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────────┐
│     Guest       │───1:1─│   Cognito User      │
│   (extended)    │       │   (sub binding)     │
└─────────────────┘       └─────────────────────┘
        │
        │ identified by
        ▼
┌─────────────────┐       ┌─────────────────────┐
│  OAuth2Session  │───N:1─│   Conversation      │
│   (new table)   │       │   (AgentCore)       │
└─────────────────┘       └─────────────────────┘

┌─────────────────┐
│  WorkloadToken  │       (in-memory only,
│   (transient)   │        auto-refreshed)
└─────────────────┘
```

## Model Changes

### 1. Guest Model Extension

**Existing File**: `backend/src/models/guest.py`

**New Field**: `cognito_sub` - Links Guest to Cognito User Pool identity

| Attribute | Type | Description |
|-----------|------|-------------|
| `cognito_sub` | String (optional) | Cognito User Pool subject identifier (UUID format) |

**Updated Pydantic Model**:
```python
class Guest(BaseModel):
    """A registered guest (customer) in the system."""

    model_config = ConfigDict(strict=True)

    guest_id: str = Field(..., description="Unique guest ID (UUID)")
    email: EmailStr = Field(..., description="Guest email (verified)")
    cognito_sub: str | None = Field(
        default=None,
        description="Cognito User Pool subject identifier for OAuth2 binding"
    )
    name: str | None = Field(default=None, description="Full name")
    phone: str | None = Field(default=None, description="Phone number")
    preferred_language: str = Field(
        default="en", pattern="^(en|es)$", description="Preferred language"
    )
    email_verified: bool = Field(default=False, description="Email verification status")
    first_verified_at: datetime | None = Field(
        default=None, description="First verification timestamp"
    )
    total_bookings: int = Field(
        default=0, ge=0, description="Count of completed bookings"
    )
    notes: str | None = Field(default=None, description="Internal notes")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
```

**New GSI**: `cognito-sub-index` on `cognito_sub` for lookup by Cognito identity

**Access Patterns**:
| Pattern | Index | Query |
|---------|-------|-------|
| Get guest by Cognito sub | cognito-sub-index | `cognito_sub = X` |

---

## New Tables

### 2. OAuth2 Sessions Table (SIMPLIFIED)

**Table Name**: `booking-{env}-oauth2-sessions`

**Purpose**: **Conversation-to-callback bridge** for agent-initiated OAuth2 flows.

Unlike browser-based applications (which use cookies to identify users in callbacks), agent conversations have no browser session context. This table bridges that gap:

1. **Agent initiates OAuth2** → stores `session_id → guest_email` mapping
2. **HTTP callback receives `session_id`** → looks up `guest_email` from table
3. **Callback calls `CompleteResourceTokenAuth`** → passes `guest_email` as `user_identifier`

**Key Insight**: AgentCore uses a two-stage callback flow:
1. Cognito → AgentCore callback (AgentCore handles code exchange + PKCE)
2. AgentCore → App callback (App receives `session_id`, calls `CompleteResourceTokenAuth`)

The app must verify the user completing the OAuth2 flow is the same user who initiated it. In browser apps, this is done via cookies. In our agent-first architecture, the DynamoDB table provides this correlation.

**Terminology Note**: The application uses `session_id` as the attribute name. AgentCore API uses `session_uri` as the parameter name in `CompleteResourceTokenAuth(session_uri=..., user_identifier=...)`. These refer to the same value.

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| `session_id` | String | PK | Session URI from AgentCore's callback redirect (maps to AgentCore's `sessionUri`) |
| `conversation_id` | String | | AgentCore conversation ID for session binding |
| `guest_email` | String | | Email of guest initiating auth (for user verification) |
| `status` | String | | `pending`, `completed`, `expired`, `failed` |
| `created_at` | String | | ISO 8601 timestamp |
| `expires_at` | Number | | Unix timestamp (TTL - 10 minutes) |

**Indexes**:
- **Primary Key**: `session_id` (PK)
- ~~**GSI: state-index**~~: Removed - AgentCore manages state internally

**TTL**: `expires_at` - DynamoDB auto-deletes expired sessions after 10 minutes

**Access Patterns**:
| Pattern | Index | Query |
|---------|-------|-------|
| Get session by ID | Primary | `PK = session_id` |

**Pydantic Model**:
```python
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class OAuth2SessionStatus(str, Enum):
    """Status of an OAuth2 authentication session."""

    PENDING = "pending"  # Waiting for user to complete auth
    COMPLETED = "completed"  # User verified successfully
    EXPIRED = "expired"  # Session timed out
    FAILED = "failed"  # Auth failed (user mismatch, error)


class OAuth2Session(BaseModel):
    """OAuth2 session for user identity correlation only.

    AgentCore handles OAuth2 state, PKCE, and code exchange internally.
    This model only tracks user identity for CompleteResourceTokenAuth verification.
    """

    model_config = ConfigDict(strict=True)

    session_id: str = Field(
        ..., description="Session URI from AgentCore's callback redirect"
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
    created_at: datetime = Field(..., description="Creation timestamp")
    expires_at: int = Field(..., description="Unix epoch timestamp for DynamoDB TTL (10 min from creation)")


class OAuth2SessionCreate(BaseModel):
    """Data required to create a new OAuth2 session."""

    model_config = ConfigDict(strict=True)

    session_id: str  # From AgentCore when initiating OAuth2
    conversation_id: str
    guest_email: EmailStr  # Validated at insertion; must match Guest.email format
```

---

### 3. Workload Token (In-Memory Only)

**Not persisted** - Managed by `IdentityClient` with automatic refresh

Used for agent-to-AgentCore API authentication. Tokens are cached in memory by the SDK.

**Pydantic Model** (for type safety, not storage):
```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkloadToken(BaseModel):
    """Agent workload access token (in-memory only)."""

    model_config = ConfigDict(strict=True)

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_at: datetime = Field(..., description="Token expiration time")
    workload_name: str | None = Field(
        default=None, description="Workload identity name"
    )
    user_id: str | None = Field(
        default=None, description="User ID if user-delegated"
    )

    @property
    def is_expired(self) -> bool:
        """Check if token is expired (with 30-second buffer)."""
        from datetime import timedelta

        return datetime.utcnow() >= (self.expires_at - timedelta(seconds=30))
```

---

### 4. Cognito Authentication State (In-Memory)

**Not persisted** - Tracks Cognito USER_AUTH flow state within a single request

**Pydantic Model**:
```python
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class CognitoAuthChallenge(str, Enum):
    """Cognito authentication challenges."""

    EMAIL_OTP = "EMAIL_OTP"


class CognitoAuthState(BaseModel):
    """Tracks Cognito USER_AUTH flow state (in-memory)."""

    model_config = ConfigDict(strict=True)

    session: str = Field(..., description="Cognito session token")
    challenge: CognitoAuthChallenge = Field(..., description="Current challenge type")
    username: str = Field(..., description="Cognito username (email)")
    attempts: int = Field(default=0, ge=0, le=3, description="OTP attempt count")
    otp_sent_at: datetime = Field(..., description="When OTP was sent")

    @property
    def max_attempts_reached(self) -> bool:
        """Check if max OTP attempts (3) reached."""
        return self.attempts >= 3
```

---

## Data Integrity Rules

### OAuth2 Session Lifecycle

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   PENDING   │────▶│  COMPLETED  │     │   EXPIRED   │
└─────────────┘     └─────────────┘     └─────────────┘
       │                                       ▲
       │                                       │
       └───────────────────────────────────────┘
              (TTL auto-expire after 10 min)
       │
       └──────────────────────────┐
                                  ▼
                           ┌─────────────┐
                           │   FAILED    │
                           └─────────────┘
```

### State Parameter Validation (FR-011)

~~AgentCore handles OAuth2 state internally.~~ **CORRECTED**: Application does NOT manage state parameter.

AgentCore's two-stage callback architecture:
1. AgentCore generates and validates state parameter internally
2. App callback receives `session_id` (sessionUri), not raw state
3. App verifies user identity, not OAuth2 state

### PKCE Code Verifier Security (FR-010)

~~Application implements PKCE.~~ **CORRECTED**: AgentCore handles PKCE internally.

AgentCore's code exchange flow:
1. AgentCore generates `code_verifier` and `code_challenge` internally
2. AgentCore's callback receives authorization code from Cognito
3. AgentCore performs code exchange with PKCE verification
4. App callback only receives `session_id`, not authorization code

### User Identity Verification (FR-012)

**Purpose**: Verify the user completing OAuth2 is the same user who initiated it.

1. **Session Creation**: When agent initiates OAuth2, store `OAuth2Session(session_id, conversation_id, guest_email)`
2. **Callback Correlation**: When callback receives `session_id`, lookup stored `guest_email`
3. **Verification**: Call `CompleteResourceTokenAuth(session_uri=session_id, user_identifier=guest_email)`
4. **Security**: AgentCore validates that `user_identifier` matches the authenticated user

---

## Terraform Resources

```hcl
# OAuth2 Sessions Table (STANDALONE in infrastructure/main.tf)
# Per FR-023: NOT part of terraform-aws-agentcore module
# Only tracks session_id ↔ guest_email mapping for user verification
module "oauth2_sessions_label" {
  source  = "cloudposse/label/null"
  version = "~> 0.25"

  namespace   = "booking"
  environment = var.environment
  name        = "oauth2-sessions"
}

module "oauth2_sessions_table" {
  source  = "terraform-aws-modules/dynamodb-table/aws"
  version = "~> 4.0"

  name     = module.oauth2_sessions_label.id  # booking-{env}-oauth2-sessions
  hash_key = "session_id"

  attributes = [
    {
      name = "session_id"
      type = "S"
    }
  ]

  # No GSI needed - lookup by session_id only
  # AgentCore provides session_id in callback redirect

  ttl_enabled        = true
  ttl_attribute_name = "expires_at"

  billing_mode = "PAY_PER_REQUEST"

  tags = module.oauth2_sessions_label.tags
}

# Add GSI to existing guests table for cognito_sub lookup
# This would be added to the existing guests table module
```

### Guests Table Update

Add GSI to existing `booking-{env}-guests` table:

```hcl
# In existing guests table configuration, add:
global_secondary_indexes = [
  # ... existing email-index ...
  {
    name            = "cognito-sub-index"
    hash_key        = "cognito_sub"
    projection_type = "ALL"
  }
]

# Note: cognito_sub attribute must be added
attributes = [
  # ... existing attributes ...
  {
    name = "cognito_sub"
    type = "S"
  }
]
```

---

## Cognito User Pool Configuration

Not a DynamoDB model, but critical infrastructure configuration:

```hcl
resource "aws_cognito_user_pool" "main" {
  name = "booking-${var.environment}-users"

  # Essentials tier required for EMAIL_OTP
  user_pool_tier = "ESSENTIALS"

  # Passwordless via EMAIL_OTP
  sign_in_policy {
    allowed_first_auth_factors = ["EMAIL_OTP"]
  }

  # No MFA (handled by EMAIL_OTP as primary factor)
  mfa_configuration = "OFF"

  # Email as primary identifier
  username_attributes = ["email"]
  auto_verified_attributes = ["email"]

  # Email configuration for OTP delivery
  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }

  # OTP code settings
  email_otp_configuration {
    message_template = "Your booking verification code is {####}"
  }
}

resource "aws_cognito_user_pool_client" "agent" {
  name         = "booking-agent"
  user_pool_id = aws_cognito_user_pool.main.id

  # OAuth2 configuration
  allowed_oauth_flows          = ["code"]
  allowed_oauth_scopes         = ["openid", "email", "profile"]
  allowed_oauth_flows_user_pool_client = true

  # PKCE required (no client secret for public clients)
  generate_secret = false

  # Callback URL
  callback_urls = [var.oauth2_callback_url]

  # Supported identity providers
  supported_identity_providers = ["COGNITO"]

  # USER_AUTH flow with EMAIL_OTP
  explicit_auth_flows = [
    "ALLOW_USER_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH"
  ]
}
```
