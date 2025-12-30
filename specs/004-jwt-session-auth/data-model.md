# Data Model: JWT Session Authentication Flow

**Feature**: 004-jwt-session-auth
**Date**: 2025-12-30
**Version**: 1.0.0

## Overview

This document defines the data structures for JWT session authentication. The feature introduces token delivery from backend to frontend, requiring coordinated types in both Python (backend) and TypeScript (frontend).

## Entity Definitions

### AuthSession (Frontend)

Browser-side session state containing authentication tokens and user metadata.

**Storage**: `localStorage` with key `booking_session`

```typescript
interface AuthSession {
  /** Whether user is currently authenticated */
  isAuthenticated: boolean

  /** Guest profile ID from DynamoDB */
  guestId: string

  /** User's email address */
  email: string

  /** Cognito ID Token (contains user claims) */
  idToken: string

  /** Cognito Access Token (for API authorization) */
  accessToken: string

  /** Cognito Refresh Token (for token renewal) */
  refreshToken: string

  /** Token expiration timestamp in milliseconds since epoch */
  expiresAt: number

  /** Cognito user identifier (sub claim) */
  cognitoSub: string

  /** User's name (optional, from guest profile) */
  name?: string
}
```

**Validation Rules**:
- `idToken`, `accessToken`, `refreshToken` must be non-empty JWT strings
- `expiresAt` must be a future timestamp (when storing)
- `guestId` must match pattern `GST-YYYY-XXXXXX`
- `cognitoSub` must be a valid UUID v4

### TokenDeliveryEvent (Shared)

Structured message from `verify_cognito_otp` tool containing authentication tokens.

**Purpose**: Type-discriminated event that frontend can detect in tool results stream.

```typescript
// TypeScript (frontend)
interface TokenDeliveryEvent {
  /** Discriminator for event type detection */
  event_type: 'auth_tokens'

  /** Whether authentication succeeded */
  success: true

  /** Cognito ID Token */
  id_token: string

  /** Cognito Access Token */
  access_token: string

  /** Cognito Refresh Token */
  refresh_token: string

  /** Token validity duration in seconds */
  expires_in: number

  /** Guest profile ID */
  guest_id: string

  /** User email address */
  email: string

  /** Cognito user identifier */
  cognito_sub: string
}
```

```python
# Python (backend)
from pydantic import BaseModel, Field
from typing import Literal

class TokenDeliveryEvent(BaseModel):
    """Structured auth token delivery to frontend."""

    event_type: Literal["auth_tokens"] = Field(
        default="auth_tokens",
        description="Discriminator for event type detection"
    )
    success: Literal[True] = True
    id_token: str = Field(..., min_length=1)
    access_token: str = Field(..., min_length=1)
    refresh_token: str = Field(..., min_length=1)
    expires_in: int = Field(..., gt=0)
    guest_id: str = Field(..., pattern=r"^GST-\d{4}-[A-Z0-9]{6}$")
    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    cognito_sub: str = Field(..., min_length=36, max_length=36)

    model_config = {"strict": True}
```

### OTPChallenge (Backend Internal)

Server-side state during the EMAIL_OTP authentication challenge.

**Note**: This already exists as `CognitoAuthState` in `backend/src/models/auth.py`. No changes needed.

```python
class CognitoAuthState(BaseModel):
    """State for Cognito auth challenge flow."""

    session: str = Field(..., description="Cognito session token")
    challenge: CognitoAuthChallenge
    username: str = Field(..., description="Email address")
    attempts: int = Field(default=0, ge=0, le=3)
    otp_sent_at: datetime | None = None
```

### AuthenticatedRequest (Frontend → Backend)

Request payload structure when user is authenticated.

```typescript
interface AuthenticatedRequest {
  /** User's message to the agent */
  prompt: string

  /** Session ID for conversation continuity */
  session_id: string

  /** JWT access token for authenticated operations (optional) */
  auth_token?: string
}
```

### VerificationState (Frontend)

Temporary state during OTP verification flow.

**Storage**: `localStorage` with key `booking_verification`
**TTL**: 5 minutes (OTP expiry)

```typescript
interface VerificationState {
  /** Email address being verified */
  email: string

  /** Whether OTP code has been requested */
  codeRequested: boolean

  /** Whether verification is complete */
  verified: boolean

  /** Cognito session token (from initiate_cognito_login) */
  sessionToken?: string

  /** When the OTP was sent (ISO timestamp) */
  otpSentAt?: string

  /** Expiration timestamp for the OTP */
  expiresAt: number

  /** Number of verification attempts */
  attempts: number
}
```

## Type Guards (Frontend)

Functions to safely narrow types at runtime:

```typescript
/**
 * Check if a tool result is a TokenDeliveryEvent.
 */
function isTokenDeliveryEvent(value: unknown): value is TokenDeliveryEvent {
  if (typeof value !== 'object' || value === null) return false
  const obj = value as Record<string, unknown>
  return (
    obj.event_type === 'auth_tokens' &&
    obj.success === true &&
    typeof obj.id_token === 'string' &&
    typeof obj.access_token === 'string' &&
    typeof obj.refresh_token === 'string' &&
    typeof obj.expires_in === 'number'
  )
}

/**
 * Check if a tool result is an auth error.
 */
function isAuthError(value: unknown): value is AuthErrorResponse {
  if (typeof value !== 'object' || value === null) return false
  const obj = value as Record<string, unknown>
  return obj.success === false && typeof obj.error_code === 'string'
}
```

## State Transitions

### Authentication Flow States

```
┌─────────────┐     initiate_cognito_login     ┌────────────────┐
│  Anonymous  │ ─────────────────────────────► │ OTP Requested  │
└─────────────┘                                └────────────────┘
                                                       │
                                                       │ verify_cognito_otp
                                                       ▼
┌─────────────┐     clearSession()             ┌────────────────┐
│  Anonymous  │ ◄───────────────────────────── │ Authenticated  │
└─────────────┘                                └────────────────┘
       ▲                                               │
       │              token expired                    │
       └───────────────────────────────────────────────┘
                  (if refresh fails)
```

### Token Lifecycle

```
                    ┌─────────────────┐
                    │  OTP Verified   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ TokenDelivery   │ (via SSE stream)
                    │     Event       │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Store Session  │ (localStorage)
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  id_token   │     │access_token │     │refresh_token│
│ (1h TTL)    │     │  (1h TTL)   │     │  (30d TTL)  │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       ▼                   ▼                   ▼
  User claims        API authz           Token refresh
```

## Relationships

```
┌──────────────────────────────────────────────────────────────┐
│                        Frontend                               │
├──────────────────────────────────────────────────────────────┤
│  VerificationState ──(OTP flow)──► AuthSession               │
│        │                               │                      │
│        │ sessionToken                  │ accessToken          │
│        ▼                               ▼                      │
│  verify_cognito_otp ◄──(SSE)──  AgentCoreTransport           │
└──────────────────────────────────────────────────────────────┘
                              │
                              │ auth_token (in payload)
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                        Backend                                │
├──────────────────────────────────────────────────────────────┤
│  CognitoAuthState ──(verify)──► TokenDeliveryEvent           │
│        │                               │                      │
│        │ session                       │ cognito_sub          │
│        ▼                               ▼                      │
│  AuthService.verify_otp    Guest (DynamoDB)                  │
└──────────────────────────────────────────────────────────────┘
```

## Migration Notes

### Existing Types to Update

1. **`frontend/src/types/index.ts`**: Update `AuthSession` interface to include `refreshToken` and `cognitoSub`

2. **`frontend/src/lib/auth.ts`**: Update `storeSession` to handle new fields

3. **`backend/src/models/auth.py`**: Add `TokenDeliveryEvent` model

### New Types to Add

1. **`frontend/src/types/index.ts`**: Add `TokenDeliveryEvent` and `AuthenticatedRequest` interfaces

2. **`frontend/src/lib/auth.ts`**: Add `isTokenDeliveryEvent` type guard

### Breaking Changes

None. All changes are additive. Existing code will continue to work, but won't receive tokens until updated.
