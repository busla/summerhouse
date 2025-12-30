# Quickstart: JWT Session Authentication Flow

**Feature**: 004-jwt-session-auth
**Date**: 2025-12-30

## Overview

This guide explains how the JWT session authentication flow works and how to integrate it into the booking agent. After completing this feature, authenticated users will have their JWT stored in the browser and included in subsequent AgentCore requests.

## Prerequisites

- Cognito User Pool configured with EMAIL_OTP (Essentials tier)
- AgentCore Runtime with Lambda permissions for `cognito-idp:Admin*` actions
- Frontend deployed with Cognito Identity Pool for anonymous access

## Authentication Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        User Journey                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. User asks about availability (anonymous)                            │
│     └─► AgentCore handles with Identity Pool credentials                │
│                                                                          │
│  2. User wants to book → Agent asks for name/email                      │
│     └─► User provides: "John Doe, john@example.com"                     │
│                                                                          │
│  3. Agent calls initiate_cognito_login(email="john@example.com")        │
│     └─► Cognito sends 6-digit OTP to email                              │
│     └─► Agent: "I've sent a verification code to john@example.com"      │
│                                                                          │
│  4. User enters OTP: "123456"                                           │
│     └─► Agent calls verify_cognito_otp(...)                             │
│     └─► Cognito returns tokens                                          │
│     └─► Tool returns TokenDeliveryEvent to frontend                     │
│                                                                          │
│  5. Frontend detects TokenDeliveryEvent in SSE stream                   │
│     └─► Stores tokens in localStorage                                   │
│     └─► Updates transport to include token in requests                  │
│                                                                          │
│  6. User asks "What are my reservations?"                               │
│     └─► Request includes auth_token in payload                          │
│     └─► Agent queries DynamoDB with cognito_sub from JWT                │
│     └─► Returns user-specific reservation data                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Implementation Guide

### Backend Changes

#### 1. Update verify_cognito_otp to Return Tokens

```python
# backend/src/tools/auth.py

@tool
def verify_cognito_otp(
    email: str,
    otp_code: str,
    session_token: str,
    otp_sent_at: str,
    attempts: int = 0,
) -> dict[str, Any]:
    """Verify OTP and return tokens for frontend session."""

    # ... existing validation code ...

    auth_service = _get_auth_service()
    result, updated_state = auth_service.verify_otp_with_state(auth_state, otp_code)

    if not result.success:
        return {
            "success": False,
            "error_code": result.error_code,
            "message": result.message,
            "attempts": updated_state.attempts,
        }

    # Get or create guest profile
    guest = auth_service.get_or_create_guest(email, result.cognito_sub or "")

    # NEW: Return TokenDeliveryEvent with Cognito tokens
    return {
        "event_type": "auth_tokens",  # Discriminator for frontend detection
        "success": True,
        "id_token": result.id_token,
        "access_token": result.access_token,
        "refresh_token": result.refresh_token,
        "expires_in": result.expires_in,
        "guest_id": guest.guest_id,
        "email": email,
        "cognito_sub": guest.cognito_sub,
    }
```

#### 2. Update AuthService to Return Tokens

```python
# backend/src/services/auth_service.py

class OTPVerificationResult(BaseModel):
    """Result of OTP verification including tokens."""
    success: bool
    error_code: str | None = None
    message: str | None = None
    cognito_sub: str | None = None
    # NEW: Add token fields
    id_token: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    expires_in: int | None = None

def verify_otp_with_state(
    self, state: CognitoAuthState, otp_code: str
) -> tuple[OTPVerificationResult, CognitoAuthState]:
    """Verify OTP and return tokens."""

    response = self.client.admin_respond_to_auth_challenge(
        UserPoolId=self.user_pool_id,
        ClientId=self.client_id,
        ChallengeName="EMAIL_OTP",
        Session=state.session,
        ChallengeResponses={
            "USERNAME": state.username,
            "EMAIL_OTP_CODE": otp_code,
        },
    )

    # Extract tokens from AuthenticationResult
    auth_result = response.get("AuthenticationResult", {})

    return OTPVerificationResult(
        success=True,
        cognito_sub=self._extract_sub_from_token(auth_result.get("IdToken", "")),
        id_token=auth_result.get("IdToken"),
        access_token=auth_result.get("AccessToken"),
        refresh_token=auth_result.get("RefreshToken"),
        expires_in=auth_result.get("ExpiresIn", 3600),
    ), state
```

### Frontend Changes

#### 1. Add TokenDeliveryEvent Type Guard

```typescript
// frontend/src/lib/auth.ts

interface TokenDeliveryEvent {
  event_type: 'auth_tokens'
  success: true
  id_token: string
  access_token: string
  refresh_token: string
  expires_in: number
  guest_id: string
  email: string
  cognito_sub: string
}

export function isTokenDeliveryEvent(value: unknown): value is TokenDeliveryEvent {
  if (typeof value !== 'object' || value === null) return false
  const obj = value as Record<string, unknown>
  return (
    obj.event_type === 'auth_tokens' &&
    obj.success === true &&
    typeof obj.id_token === 'string' &&
    typeof obj.access_token === 'string'
  )
}
```

#### 2. Process Token Delivery in Chat Hook

```typescript
// frontend/src/hooks/useAgentChat.ts

import { isTokenDeliveryEvent, storeSession } from '@/lib/auth'

// Inside the message processing logic:
function processToolResult(result: unknown): void {
  if (isTokenDeliveryEvent(result)) {
    storeSession({
      isAuthenticated: true,
      guestId: result.guest_id,
      email: result.email,
      idToken: result.id_token,
      accessToken: result.access_token,
      refreshToken: result.refresh_token,
      expiresAt: Date.now() + result.expires_in * 1000,
      cognitoSub: result.cognito_sub,
    })
    console.log('[Auth] Session stored after token delivery')
  }
}
```

#### 3. Include Token in Transport Requests

```typescript
// frontend/src/lib/agentcore-transport.ts

import { getAccessToken } from './auth'

async sendMessages(options: { ... }): Promise<ReadableStream<UIMessageChunk>> {
  // ... existing code ...

  // Include auth token in payload if available
  const authToken = getAccessToken()
  const payload = JSON.stringify({
    prompt: userText,
    session_id: this.sessionId,
    ...(authToken && { auth_token: authToken }),  // NEW: Add token to payload
  })

  // ... rest of existing code ...
}
```

## Testing

### Unit Test: Token Delivery Event Detection

```typescript
// frontend/tests/unit/lib/auth.test.ts

import { isTokenDeliveryEvent } from '@/lib/auth'

describe('isTokenDeliveryEvent', () => {
  it('returns true for valid token delivery event', () => {
    const event = {
      event_type: 'auth_tokens',
      success: true,
      id_token: 'eyJ...',
      access_token: 'eyJ...',
      refresh_token: 'eyJ...',
      expires_in: 3600,
      guest_id: 'GST-2025-ABC123',
      email: 'test@example.com',
      cognito_sub: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    }
    expect(isTokenDeliveryEvent(event)).toBe(true)
  })

  it('returns false for error responses', () => {
    const error = { success: false, error_code: 'INVALID_OTP' }
    expect(isTokenDeliveryEvent(error)).toBe(false)
  })
})
```

### Integration Test: Full Auth Flow

```python
# backend/tests/integration/test_auth_flow.py

def test_verify_otp_returns_tokens():
    """verify_cognito_otp should return TokenDeliveryEvent with tokens."""
    # Setup: initiate login first
    init_result = initiate_cognito_login(email="test@example.com")
    assert init_result["success"] is True

    # Verify OTP (mock Cognito response)
    with mock_cognito_otp_success():
        result = verify_cognito_otp(
            email="test@example.com",
            otp_code="123456",
            session_token=init_result["session_token"],
            otp_sent_at=init_result["otp_sent_at"],
        )

    # Assert TokenDeliveryEvent format
    assert result["event_type"] == "auth_tokens"
    assert result["success"] is True
    assert "id_token" in result
    assert "access_token" in result
    assert "refresh_token" in result
    assert "expires_in" in result
    assert result["guest_id"].startswith("GST-")
```

### E2E Test: Browser Auth Flow

```typescript
// frontend/tests/e2e/auth-flow.spec.ts

import { test, expect } from '@playwright/test'

test('user can authenticate and make authenticated requests', async ({ page }) => {
  await page.goto('/')

  // Start chat and request booking
  await page.fill('[data-testid="chat-input"]', 'I want to book March 15-20')
  await page.click('[data-testid="send-button"]')

  // Wait for agent to ask for email
  await expect(page.locator('text=email')).toBeVisible()

  // Provide email
  await page.fill('[data-testid="chat-input"]', 'John Doe, test@example.com')
  await page.click('[data-testid="send-button"]')

  // Wait for OTP prompt
  await expect(page.locator('text=verification code')).toBeVisible()

  // Enter OTP (mocked in test environment)
  await page.fill('[data-testid="chat-input"]', '123456')
  await page.click('[data-testid="send-button"]')

  // Verify session stored
  const session = await page.evaluate(() =>
    JSON.parse(localStorage.getItem('booking_session') || 'null')
  )
  expect(session).not.toBeNull()
  expect(session.isAuthenticated).toBe(true)
  expect(session.accessToken).toBeTruthy()
})
```

## Troubleshooting

### Tokens Not Appearing in Frontend

1. Check backend logs for `verify_cognito_otp` return value
2. Verify SSE stream includes `tool-result` event with token data
3. Check browser console for `[Auth] Session stored` log message
4. Inspect localStorage for `booking_session` key

### Authenticated Requests Still Failing

1. Verify `auth_token` is being included in request payload
2. Check backend receives and can decode the token
3. Ensure token hasn't expired (`expiresAt` in session)
4. Verify Cognito sub matches DynamoDB guest record

### Token Refresh Not Working

1. Check `refreshToken` is stored in session
2. Verify refresh endpoint is implemented and accessible
3. Check Cognito refresh token hasn't expired (30 days default)

## Related Documentation

- [Feature Specification](./spec.md) - User stories and requirements
- [Data Model](./data-model.md) - Type definitions
- [Tool Contracts](./contracts/tool-responses.md) - API response schemas
- [Research Notes](./research.md) - Technical decisions and rationale
