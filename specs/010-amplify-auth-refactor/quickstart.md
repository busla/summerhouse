# Quickstart Guide: Amplify Authentication Refactor

**Feature**: 010-amplify-auth-refactor | **Date**: 2026-01-02 | **Phase**: 1

## Overview

This guide provides step-by-step implementation patterns for the Amplify auth refactor. Use this as a reference when implementing tasks.

## Prerequisites

✅ Already configured:
- Cognito User Pool with ESSENTIALS tier and EMAIL_OTP
- API Gateway REST API with Cognito authorizer
- DynamoDB guests table with `cognito-sub-index` GSI
- Frontend Amplify configuration
- Backend `get_guest_by_cognito_sub()` function

## Frontend Implementation

### 1. Auth Hook for Forms (`useAuthenticatedUser.ts`)

Create a hook for auth-aware forms that handles both authenticated and anonymous states:

```typescript
// frontend/src/hooks/useAuthenticatedUser.ts
'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  signIn,
  signUp,
  confirmSignIn,
  confirmSignUp,
  getCurrentUser,
  fetchAuthSession,
} from 'aws-amplify/auth'

export type AuthStep =
  | 'anonymous'      // Not authenticated, show input fields
  | 'sending_otp'    // OTP being sent
  | 'awaiting_otp'   // Waiting for user to enter OTP
  | 'verifying'      // Verifying OTP
  | 'authenticated'  // Authenticated, show read-only info

export interface AuthenticatedUser {
  email: string
  name?: string
  sub: string
}

export interface UseAuthenticatedUserReturn {
  step: AuthStep
  user: AuthenticatedUser | null
  error: string | null

  // Actions
  initiateAuth: (email: string) => Promise<void>
  confirmOtp: (code: string) => Promise<void>
  signOut: () => Promise<void>
}

export function useAuthenticatedUser(): UseAuthenticatedUserReturn {
  const [step, setStep] = useState<AuthStep>('anonymous')
  const [user, setUser] = useState<AuthenticatedUser | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pendingEmail, setPendingEmail] = useState<string>('')

  // Check existing session on mount
  useEffect(() => {
    async function checkSession() {
      try {
        const currentUser = await getCurrentUser()
        const session = await fetchAuthSession()
        const claims = session.tokens?.idToken?.payload

        setUser({
          email: claims?.email as string,
          name: claims?.name as string | undefined,
          sub: currentUser.userId,
        })
        setStep('authenticated')
      } catch {
        setStep('anonymous')
      }
    }
    checkSession()
  }, [])

  const initiateAuth = useCallback(async (email: string) => {
    setError(null)
    setStep('sending_otp')
    setPendingEmail(email)

    try {
      // Try sign in first (existing user)
      const { nextStep } = await signIn({
        username: email,
        options: {
          authFlowType: 'USER_AUTH',
          preferredChallenge: 'EMAIL_OTP',
        },
      })

      if (nextStep.signInStep === 'CONFIRM_SIGN_IN_WITH_EMAIL_CODE') {
        setStep('awaiting_otp')
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'UserNotFoundException') {
        // New user - sign up
        await signUp({
          username: email,
          password: crypto.randomUUID(), // Required but unused
          options: {
            userAttributes: { email },
            autoSignIn: { authFlowType: 'USER_AUTH' },
          },
        })
        setStep('awaiting_otp')
      } else {
        setError(err instanceof Error ? err.message : 'Authentication failed')
        setStep('anonymous')
      }
    }
  }, [])

  const confirmOtp = useCallback(async (code: string) => {
    setError(null)
    setStep('verifying')

    try {
      const result = await confirmSignIn({ challengeResponse: code })

      if (result.isSignedIn) {
        const currentUser = await getCurrentUser()
        const session = await fetchAuthSession()
        const claims = session.tokens?.idToken?.payload

        setUser({
          email: claims?.email as string,
          name: claims?.name as string | undefined,
          sub: currentUser.userId,
        })
        setStep('authenticated')
      }
    } catch (err) {
      if (err instanceof Error) {
        switch (err.name) {
          case 'CodeMismatchException':
            setError('Invalid code. Please try again.')
            break
          case 'ExpiredCodeException':
            setError('Code expired. Please request a new one.')
            break
          case 'LimitExceededException':
            setError('Too many attempts. Please wait and try again.')
            break
          default:
            setError(err.message)
        }
      }
      setStep('awaiting_otp')
    }
  }, [])

  const signOut = useCallback(async () => {
    const { signOut: amplifySignOut } = await import('aws-amplify/auth')
    await amplifySignOut()
    setUser(null)
    setStep('anonymous')
  }, [])

  return {
    step,
    user,
    error,
    initiateAuth,
    confirmOtp,
    signOut,
  }
}
```

### 2. Modify GuestDetailsForm

Update `GuestDetailsForm.tsx` to be auth-aware:

```typescript
// Key changes to frontend/src/components/booking/GuestDetailsForm.tsx

import { useAuthenticatedUser } from '@/hooks/useAuthenticatedUser'
import { Button } from '@/components/ui/button'

export function GuestDetailsForm({ ... }) {
  const { step, user, error, initiateAuth, confirmOtp, signOut } = useAuthenticatedUser()
  const [otpCode, setOtpCode] = useState('')

  // If authenticated, show read-only user info
  if (step === 'authenticated' && user) {
    return (
      <div className="space-y-4">
        <div className="rounded-lg border p-4 bg-muted/50">
          <div className="text-sm text-muted-foreground">Signed in as</div>
          <div className="font-medium">{user.name || user.email}</div>
          <div className="text-sm text-muted-foreground">{user.email}</div>
          <Button variant="link" size="sm" onClick={signOut} className="p-0 h-auto">
            Sign out
          </Button>
        </div>
        {/* Rest of form (phone, guest count, etc.) */}
      </div>
    )
  }

  // Anonymous state - show input fields with verify button
  if (step === 'anonymous' || step === 'sending_otp') {
    return (
      <Form {...form}>
        <form className="space-y-6">
          {/* Name and Email fields */}
          <FormField name="email" render={...} />

          <Button
            type="button"
            onClick={() => initiateAuth(form.getValues('email'))}
            disabled={step === 'sending_otp'}
          >
            {step === 'sending_otp' ? 'Sending...' : 'Verify Email'}
          </Button>

          {error && <p className="text-destructive text-sm">{error}</p>}
        </form>
      </Form>
    )
  }

  // OTP entry state
  if (step === 'awaiting_otp' || step === 'verifying') {
    return (
      <div className="space-y-4">
        <p>Enter the code sent to your email</p>
        <Input
          value={otpCode}
          onChange={(e) => setOtpCode(e.target.value)}
          placeholder="Enter code"
          maxLength={8}
        />
        <Button
          onClick={() => confirmOtp(otpCode)}
          disabled={step === 'verifying' || otpCode.length < 6}
        >
          {step === 'verifying' ? 'Verifying...' : 'Confirm'}
        </Button>
        {error && <p className="text-destructive text-sm">{error}</p>}
      </div>
    )
  }
}
```

### 3. API Client with Auth Token

Ensure API calls include the auth token:

```typescript
// frontend/src/lib/api-client.ts
import { fetchAuthSession } from 'aws-amplify/auth'

async function getAuthHeaders(): Promise<HeadersInit> {
  try {
    const session = await fetchAuthSession()
    const token = session.tokens?.idToken?.toString()
    if (token) {
      return { Authorization: `Bearer ${token}` }
    }
  } catch {
    // Not authenticated
  }
  return {}
}

export async function apiClient(path: string, options: RequestInit = {}) {
  const authHeaders = await getAuthHeaders()

  return fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
      ...options.headers,
    },
  })
}
```

## Backend Implementation

### 1. Customer Routes

Add customer endpoints to the API:

```python
# backend/api/src/api/routes/customers.py
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from shared.services.dynamodb import get_dynamodb_service
from shared.models.guest import Guest, GuestCreate, GuestUpdate

router = APIRouter(prefix="/customers", tags=["customers"])


def _get_cognito_sub(request: Request) -> str:
    """Extract cognito_sub from request (set by API Gateway)."""
    sub = request.headers.get("x-user-sub")
    if not sub:
        raise HTTPException(401, "Missing user identity")
    return sub


@router.get("/me")
async def get_current_customer(request: Request) -> dict:
    """Get current authenticated user's customer profile."""
    sub = _get_cognito_sub(request)
    db = get_dynamodb_service()

    guest = db.get_guest_by_cognito_sub(sub)
    if not guest:
        raise HTTPException(404, "Customer not found")

    return guest


@router.put("/me")
async def update_current_customer(
    request: Request,
    update: GuestUpdate,
) -> dict:
    """Update current customer profile."""
    sub = _get_cognito_sub(request)
    db = get_dynamodb_service()

    guest = db.get_guest_by_cognito_sub(sub)
    if not guest:
        raise HTTPException(404, "Customer not found")

    # Update only provided fields
    update_data = update.model_dump(exclude_unset=True)
    if update_data:
        updated = db.update_item(
            table="guests",
            key={"guest_id": guest["guest_id"]},
            update_expression="SET " + ", ".join(f"{k} = :{k}" for k in update_data),
            expression_attribute_values={f":{k}": v for k, v in update_data.items()},
        )
        return updated or guest

    return guest


class CustomerCreate(BaseModel):
    """Data for creating customer profile."""
    name: str | None = Field(None, min_length=2, max_length=100)
    phone: str | None = Field(None, min_length=7, max_length=20)
    preferred_language: str = Field("en", pattern="^(en|es)$")


@router.post("/me", status_code=201)
async def create_current_customer(
    request: Request,
    data: CustomerCreate,
) -> dict:
    """Create customer profile for authenticated user."""
    sub = _get_cognito_sub(request)
    email = request.headers.get("x-user-email")  # From JWT claims
    db = get_dynamodb_service()

    # Check if already exists
    existing = db.get_guest_by_cognito_sub(sub)
    if existing:
        raise HTTPException(409, "Customer profile already exists")

    # Create new guest
    from datetime import datetime, UTC
    import uuid

    guest = {
        "guest_id": f"GUEST-{datetime.now(UTC).year}-{uuid.uuid4().hex[:6].upper()}",
        "email": email,
        "cognito_sub": sub,
        "name": data.name,
        "phone": data.phone,
        "preferred_language": data.preferred_language,
        "email_verified": True,
        "first_verified_at": datetime.now(UTC).isoformat(),
        "total_bookings": 0,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }

    db.create_guest(guest)
    return guest
```

### 2. Register Router

Add the router to the main app:

```python
# backend/api/src/api/main.py
from api.routes.customers import router as customers_router

# Add to router includes
app.include_router(customers_router)
```

## Testing

### Frontend Unit Test

```typescript
// frontend/tests/unit/hooks/useAuthenticatedUser.test.ts
import { renderHook, act } from '@testing-library/react'
import { useAuthenticatedUser } from '@/hooks/useAuthenticatedUser'

// Mock Amplify auth
vi.mock('aws-amplify/auth', () => ({
  signIn: vi.fn(),
  confirmSignIn: vi.fn(),
  getCurrentUser: vi.fn().mockRejectedValue(new Error('Not authenticated')),
  fetchAuthSession: vi.fn(),
}))

describe('useAuthenticatedUser', () => {
  it('starts in anonymous state when not authenticated', async () => {
    const { result } = renderHook(() => useAuthenticatedUser())

    // Wait for initial check
    await vi.waitFor(() => {
      expect(result.current.step).toBe('anonymous')
    })
    expect(result.current.user).toBeNull()
  })
})
```

### Backend Unit Test

```python
# backend/tests/unit/routes/test_customers.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


def test_get_current_customer_not_found(client: TestClient):
    """Test GET /customers/me when no profile exists."""
    with patch("api.routes.customers.get_dynamodb_service") as mock_db:
        mock_db.return_value.get_guest_by_cognito_sub.return_value = None

        response = client.get(
            "/api/customers/me",
            headers={"x-user-sub": "test-sub-123"}
        )

        assert response.status_code == 404


def test_get_current_customer_success(client: TestClient):
    """Test GET /customers/me with existing profile."""
    guest = {
        "guest_id": "GUEST-2025-ABC123",
        "email": "test@example.com",
        "cognito_sub": "test-sub-123",
        "name": "Test User",
    }

    with patch("api.routes.customers.get_dynamodb_service") as mock_db:
        mock_db.return_value.get_guest_by_cognito_sub.return_value = guest

        response = client.get(
            "/api/customers/me",
            headers={"x-user-sub": "test-sub-123"}
        )

        assert response.status_code == 200
        assert response.json()["email"] == "test@example.com"
```

### E2E Test

```typescript
// frontend/tests/e2e/auth-flow.spec.ts
import { test, expect } from '@playwright/test'

test.describe('Email OTP Authentication', () => {
  test('shows email input for anonymous users', async ({ page }) => {
    await page.goto('/book')

    // Select dates first
    await page.click('[data-testid="date-selector"]')
    await page.click('text=Continue to guest details')

    // Should see email input (not authenticated)
    await expect(page.locator('input[name="email"]')).toBeVisible()
    await expect(page.locator('text=Verify Email')).toBeVisible()
  })

  test('shows user info for authenticated users', async ({ page }) => {
    // Authenticate first (mock or real)
    await page.goto('/book')

    // After authentication...
    await expect(page.locator('text=Signed in as')).toBeVisible()
    await expect(page.locator('input[name="email"]')).not.toBeVisible()
  })
})
```

## Key Implementation Points

### Do
- ✅ Use `USER_AUTH` flow with `preferredChallenge: 'EMAIL_OTP'`
- ✅ Handle `UserNotFoundException` by triggering sign-up
- ✅ Extract `cognito_sub` from `x-user-sub` header (set by API Gateway)
- ✅ Query guests by `cognito_sub` GSI
- ✅ Use `fetchAuthSession()` for automatic token refresh

### Don't
- ❌ Validate JWT in backend (API Gateway does this)
- ❌ Store tokens in localStorage manually (Amplify handles this)
- ❌ Modify agent code (out of scope)
- ❌ Add password fields (EMAIL_OTP only)
- ❌ Create custom session storage (use Amplify)

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `frontend/src/hooks/useAuthenticatedUser.ts` | Create | Auth state hook for forms |
| `frontend/src/components/booking/GuestDetailsForm.tsx` | Modify | Auth-aware form |
| `backend/api/src/api/routes/customers.py` | Create | Customer API endpoints |
| `backend/api/src/api/main.py` | Modify | Register customers router |
| `frontend/tests/unit/hooks/useAuthenticatedUser.test.ts` | Create | Hook unit tests |
| `backend/tests/unit/routes/test_customers.py` | Create | Route unit tests |
| `frontend/tests/e2e/auth-flow.spec.ts` | Create | E2E tests |
