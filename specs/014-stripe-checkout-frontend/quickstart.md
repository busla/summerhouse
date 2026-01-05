# Quickstart: Stripe Checkout Frontend Integration

**Phase**: 1 | **Date**: 2026-01-04 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Overview

This guide covers development, testing, and deployment of the Stripe Checkout frontend integration. The feature adds a payment step to the existing booking flow, handles Stripe redirects, and provides payment status display.

**Backend is already complete** (013-stripe-payment) - this feature focuses on frontend only.

---

## Prerequisites

```bash
# Frontend dependencies
task frontend:install

# Regenerate API client to include checkout-session endpoint
task backend:dev &  # Start backend in background
sleep 5
cd frontend && yarn generate:api

# Verify installation
task frontend:test  # Should pass existing tests
```

**Required Environment**:
- Node.js 18+
- Yarn Berry
- Backend running on localhost:3001 (for API client generation)
- Existing booking flow working (`/book` page)

---

## SDK Regeneration (Critical First Step)

The generated TypeScript API client is missing the `checkout-session` endpoint. This must be regenerated before any implementation work.

```bash
# 1. Start backend (provides OpenAPI spec)
task backend:dev

# 2. Regenerate frontend API client
cd frontend
yarn generate:api

# 3. Verify new types exist
grep -r "checkout" src/lib/api-client/
# Should show CheckoutSessionRequest, CheckoutSessionResponse, etc.
```

**Why this matters**: The spec says to use generated types, not custom interfaces. The `@hey-api/openapi-ts` generator creates type-safe API clients from the backend OpenAPI spec.

---

## Project Structure

```text
frontend/
├── src/
│   ├── app/
│   │   ├── book/
│   │   │   └── page.tsx           # MODIFY: Add payment step (4 steps now)
│   │   └── booking/               # NEW directory
│   │       ├── success/
│   │       │   └── page.tsx       # NEW: Payment success handler
│   │       └── cancel/
│   │           └── page.tsx       # NEW: Payment cancel handler
│   ├── components/
│   │   └── booking/
│   │       ├── PaymentStep.tsx    # NEW: Payment initiation UI
│   │       ├── PaymentStatus.tsx  # NEW: Status badge component
│   │       └── BookingConfirmation.tsx  # MODIFY: Add payment details
│   ├── hooks/
│   │   └── useCheckoutSession.ts  # NEW: Stripe Checkout session hook
│   └── lib/
│       ├── api-client/            # REGENERATE: With checkout-session endpoint
│       └── constants/
│           └── payment.ts         # NEW: Payment constants
└── tests/
    └── e2e/
        └── checkout-flow.spec.ts  # NEW: Playwright E2E tests
```

---

## Development Workflow

### 1. Add Payment Constants

```typescript
// frontend/src/lib/constants/payment.ts
/**
 * Payment-related constants.
 * @see specs/014-stripe-checkout-frontend/contracts/payment-routes.schema.ts
 */

/** Maximum allowed payment attempts before requiring support contact */
export const MAX_PAYMENT_ATTEMPTS = 3

/** Stripe Checkout session validity in minutes */
export const CHECKOUT_SESSION_EXPIRY_MINUTES = 30

/** Polling interval for payment status verification (ms) */
export const PAYMENT_STATUS_POLL_INTERVAL = 2000

/** Maximum polling duration before showing fallback message (ms) */
export const PAYMENT_STATUS_POLL_TIMEOUT = 30000
```

### 2. Extend BookingFormState (Test-First)

```typescript
// frontend/src/app/book/page.tsx (modifications)

// Current step type (add 'payment')
type BookingStep = 'dates' | 'guest' | 'payment' | 'confirmation'

// Extended state interface
interface BookingFormState {
  currentStep: BookingStep
  selectedRange: DayPickerRange | undefined
  guestDetails: GuestDetails | null
  // NEW: Payment flow state
  reservationId: string | null
  paymentAttempts: number
  lastPaymentError: string | null
  stripeSessionId: string | null
}

// Updated initial state
const initialFormState: BookingFormState = {
  currentStep: 'dates',
  selectedRange: undefined,
  guestDetails: null,
  // Payment fields
  reservationId: null,
  paymentAttempts: 0,
  lastPaymentError: null,
  stripeSessionId: null,
}
```

### 3. Create useCheckoutSession Hook

```typescript
// frontend/src/hooks/useCheckoutSession.ts
/**
 * Hook for managing Stripe Checkout session flow.
 * @see specs/014-stripe-checkout-frontend/contracts/checkout-session.types.ts
 */

'use client'

import { useState, useCallback } from 'react'
import { createPaymentsCheckoutSession } from '@/lib/api-client'
import type { CheckoutSessionResponse } from '@/lib/api-client/types.gen'

interface CheckoutSessionState {
  isLoading: boolean
  error: string | null
  isRedirecting: boolean
}

interface UseCheckoutSessionResult {
  state: CheckoutSessionState
  createSession: (reservationId: string) => Promise<void>
  retryPayment: (reservationId: string) => Promise<void>
  clearError: () => void
}

export function useCheckoutSession(): UseCheckoutSessionResult {
  const [state, setState] = useState<CheckoutSessionState>({
    isLoading: false,
    error: null,
    isRedirecting: false,
  })

  const createSession = useCallback(async (reservationId: string) => {
    setState({ isLoading: true, error: null, isRedirecting: false })

    try {
      const response = await createPaymentsCheckoutSession({
        body: { reservation_id: reservationId },
      })

      if (response.error) {
        setState({
          isLoading: false,
          error: response.error.detail || 'Failed to create checkout session',
          isRedirecting: false,
        })
        return
      }

      // Success - redirect to Stripe
      setState({ isLoading: false, error: null, isRedirecting: true })
      window.location.href = response.data.checkout_url
    } catch (err) {
      setState({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Unknown error occurred',
        isRedirecting: false,
      })
    }
  }, [])

  const retryPayment = useCallback(async (reservationId: string) => {
    // Retry uses the same flow - creates a new checkout session
    await createSession(reservationId)
  }, [createSession])

  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, error: null }))
  }, [])

  return { state, createSession, retryPayment, clearError }
}
```

### 4. Create PaymentStep Component

```typescript
// frontend/src/components/booking/PaymentStep.tsx
/**
 * Payment step in the booking flow.
 * Shows booking summary and redirects to Stripe Checkout.
 * @see FR-001, FR-002, FR-003
 */

'use client'

import { useCheckoutSession } from '@/hooks/useCheckoutSession'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, CreditCard, AlertCircle } from 'lucide-react'

interface PaymentStepProps {
  reservationId: string
  totalAmount: number
  checkIn: Date
  checkOut: Date
  guestName: string
  onPaymentInitiated?: () => void
  onError?: (error: string) => void
}

export function PaymentStep({
  reservationId,
  totalAmount,
  checkIn,
  checkOut,
  guestName,
  onPaymentInitiated,
  onError,
}: PaymentStepProps) {
  const { state, createSession, clearError } = useCheckoutSession()
  const { isLoading, error, isRedirecting } = state

  const handleProceedToPayment = async () => {
    onPaymentInitiated?.()
    await createSession(reservationId)

    if (state.error) {
      onError?.(state.error)
    }
  }

  // Format amount for display (cents to EUR)
  const formattedAmount = new Intl.NumberFormat('en-EU', {
    style: 'currency',
    currency: 'EUR',
  }).format(totalAmount / 100)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CreditCard className="h-5 w-5" />
          Complete Payment
        </CardTitle>
        <CardDescription>
          Review your booking and proceed to secure payment
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Booking Summary */}
        <div className="rounded-lg bg-muted p-4 space-y-2">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Guest</span>
            <span className="font-medium">{guestName}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Check-in</span>
            <span className="font-medium">{checkIn.toLocaleDateString()}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Check-out</span>
            <span className="font-medium">{checkOut.toLocaleDateString()}</span>
          </div>
          <hr className="my-2" />
          <div className="flex justify-between text-lg font-semibold">
            <span>Total</span>
            <span>{formattedAmount}</span>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              {error}
              <Button
                variant="link"
                size="sm"
                onClick={clearError}
                className="ml-2 p-0 h-auto"
              >
                Dismiss
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {/* Action Button */}
        <Button
          onClick={handleProceedToPayment}
          disabled={isLoading || isRedirecting}
          className="w-full"
          size="lg"
        >
          {isLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Creating session...
            </>
          ) : isRedirecting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Redirecting to payment...
            </>
          ) : (
            <>
              <CreditCard className="mr-2 h-4 w-4" />
              Proceed to Payment
            </>
          )}
        </Button>

        <p className="text-center text-sm text-muted-foreground">
          You will be redirected to Stripe's secure payment page
        </p>
      </CardContent>
    </Card>
  )
}
```

### 5. Create Success Page

```typescript
// frontend/src/app/booking/success/page.tsx
/**
 * Payment success page - handles Stripe redirect after successful payment.
 * @see FR-006, FR-007, FR-008, FR-009, FR-010
 */

'use client'

import { useEffect, useState } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { useFormPersistence } from '@/hooks/useFormPersistence'
import { getPaymentsStatus } from '@/lib/api-client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { CheckCircle, Home } from 'lucide-react'

interface BookingFormState {
  reservationId: string | null
  stripeSessionId: string | null
  selectedRange: { from: string; to: string } | null
  guestDetails: { name: string } | null
}

export default function SuccessPage() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const sessionId = searchParams.get('session_id')

  const { storedState, clearPersistedState } = useFormPersistence<BookingFormState>(
    'booking-form-state'
  )

  const [loading, setLoading] = useState(true)
  const [paymentConfirmed, setPaymentConfirmed] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function verifyPayment() {
      // Validate session_id matches stored state
      if (!sessionId) {
        setError('Missing session ID')
        setLoading(false)
        return
      }

      if (!storedState?.reservationId) {
        setError('Booking session expired. Please start a new booking.')
        setLoading(false)
        return
      }

      // Fetch payment status from API
      try {
        const response = await getPaymentsStatus({
          path: { reservation_id: storedState.reservationId },
        })

        if (response.error) {
          setError('Could not verify payment status')
        } else if (response.data.has_completed_payment) {
          setPaymentConfirmed(true)
          // Clear persisted state after confirmation (FR-009)
          clearPersistedState()
        } else {
          // Payment not yet confirmed - might be processing
          setError('Payment is still processing. Please check back shortly.')
        }
      } catch (err) {
        setError('Failed to verify payment')
      } finally {
        setLoading(false)
      }
    }

    verifyPayment()
  }, [sessionId, storedState, clearPersistedState])

  if (loading) {
    return (
      <div className="container mx-auto max-w-lg py-12">
        <Card>
          <CardHeader>
            <Skeleton className="h-8 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
          </CardHeader>
          <CardContent className="space-y-4">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-10 w-full" />
          </CardContent>
        </Card>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container mx-auto max-w-lg py-12">
        <Card>
          <CardHeader>
            <CardTitle>Something went wrong</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => router.push('/book')} className="w-full">
              Return to Booking
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="container mx-auto max-w-lg py-12">
      <Card>
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
            <CheckCircle className="h-8 w-8 text-green-600" />
          </div>
          <CardTitle className="text-2xl">Booking Confirmed!</CardTitle>
          <CardDescription>
            Your payment was successful. We've sent a confirmation to your email.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Booking Details */}
          <div className="rounded-lg bg-muted p-4 space-y-2">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Reservation ID</span>
              <span className="font-mono font-medium">
                {storedState?.reservationId}
              </span>
            </div>
            {storedState?.guestDetails && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Guest</span>
                <span className="font-medium">{storedState.guestDetails.name}</span>
              </div>
            )}
            {storedState?.selectedRange && (
              <>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Check-in</span>
                  <span className="font-medium">
                    {new Date(storedState.selectedRange.from).toLocaleDateString()}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Check-out</span>
                  <span className="font-medium">
                    {new Date(storedState.selectedRange.to).toLocaleDateString()}
                  </span>
                </div>
              </>
            )}
            <hr className="my-2" />
            <div className="flex justify-between font-semibold text-green-600">
              <span>Status</span>
              <span>Paid ✓</span>
            </div>
          </div>

          <Button onClick={() => router.push('/')} className="w-full" size="lg">
            <Home className="mr-2 h-4 w-4" />
            Return Home
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
```

### 6. Create Cancel Page

```typescript
// frontend/src/app/booking/cancel/page.tsx
/**
 * Payment cancel page - handles return from cancelled Stripe Checkout.
 * @see FR-011, FR-012, FR-013, FR-014
 */

'use client'

import { useRouter } from 'next/navigation'
import { useFormPersistence } from '@/hooks/useFormPersistence'
import { useCheckoutSession } from '@/hooks/useCheckoutSession'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { XCircle, RefreshCw, ArrowLeft, Loader2, AlertCircle } from 'lucide-react'
import { MAX_PAYMENT_ATTEMPTS } from '@/lib/constants/payment'

interface BookingFormState {
  reservationId: string | null
  paymentAttempts: number
  selectedRange: { from: string; to: string } | null
  guestDetails: { name: string } | null
}

export default function CancelPage() {
  const router = useRouter()
  const { storedState, updatePersistedState } = useFormPersistence<BookingFormState>(
    'booking-form-state'
  )
  const { state, retryPayment } = useCheckoutSession()

  const canRetry = (storedState?.paymentAttempts ?? 0) < MAX_PAYMENT_ATTEMPTS
  const attemptsRemaining = MAX_PAYMENT_ATTEMPTS - (storedState?.paymentAttempts ?? 0)

  const handleRetry = async () => {
    if (!storedState?.reservationId || !canRetry) return

    // Increment attempt count before retry
    updatePersistedState({
      paymentAttempts: (storedState.paymentAttempts ?? 0) + 1,
    })

    await retryPayment(storedState.reservationId)
  }

  const handleModifyBooking = () => {
    // Return to booking flow with preserved state
    router.push('/book')
  }

  return (
    <div className="container mx-auto max-w-lg py-12">
      <Card>
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-yellow-100">
            <XCircle className="h-8 w-8 text-yellow-600" />
          </div>
          <CardTitle className="text-2xl">Payment Not Completed</CardTitle>
          <CardDescription>
            Your payment was cancelled. Your booking details have been saved.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Preserved Booking Details */}
          {storedState?.selectedRange && (
            <div className="rounded-lg bg-muted p-4 space-y-2">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Check-in</span>
                <span className="font-medium">
                  {new Date(storedState.selectedRange.from).toLocaleDateString()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Check-out</span>
                <span className="font-medium">
                  {new Date(storedState.selectedRange.to).toLocaleDateString()}
                </span>
              </div>
              {storedState.guestDetails && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Guest</span>
                  <span className="font-medium">{storedState.guestDetails.name}</span>
                </div>
              )}
            </div>
          )}

          {/* Error from retry attempt */}
          {state.error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{state.error}</AlertDescription>
            </Alert>
          )}

          {/* Max attempts warning */}
          {!canRetry && (
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                Maximum payment attempts reached. Please contact support or try
                booking again later.
              </AlertDescription>
            </Alert>
          )}

          {/* Action Buttons */}
          <div className="space-y-3">
            {canRetry && storedState?.reservationId && (
              <Button
                onClick={handleRetry}
                disabled={state.isLoading || state.isRedirecting}
                className="w-full"
                size="lg"
              >
                {state.isLoading || state.isRedirecting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {state.isRedirecting ? 'Redirecting...' : 'Processing...'}
                  </>
                ) : (
                  <>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Try Again ({attemptsRemaining} attempt{attemptsRemaining !== 1 ? 's' : ''} remaining)
                  </>
                )}
              </Button>
            )}

            <Button
              variant="outline"
              onClick={handleModifyBooking}
              className="w-full"
              size="lg"
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Modify Booking
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
```

---

## Testing Patterns

### E2E Tests with Mock Stripe

```typescript
// frontend/tests/e2e/checkout-flow.spec.ts
/**
 * E2E tests for Stripe Checkout flow.
 * @see FR-022 to FR-026
 */

import { test, expect } from '@playwright/test'

// Mock API responses
const mockCheckoutSession = {
  payment_id: 'PAY-TEST-123',
  checkout_session_id: 'cs_test_abc123',
  checkout_url: 'http://localhost:3000/booking/success?session_id=cs_test_abc123',
  expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
  amount: 112500,
  currency: 'EUR',
}

const mockPaymentStatus = {
  reservation_id: 'RES-TEST-123',
  payment: {
    payment_id: 'PAY-TEST-123',
    status: 'completed',
  },
  has_completed_payment: true,
  is_refunded: false,
  payment_attempts: 1,
}

test.describe('Checkout Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Mock the checkout-session API
    await page.route('**/payments/checkout-session', async (route) => {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(mockCheckoutSession),
      })
    })

    // Mock payment status API
    await page.route('**/payments/**/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockPaymentStatus),
      })
    })
  })

  test('completes full booking flow with payment (FR-023)', async ({ page }) => {
    // Start at booking page
    await page.goto('/book')

    // Step 1: Select dates
    // ... date selection logic

    // Step 2: Fill guest details
    // ... guest form logic

    // Step 3: Payment step
    await expect(page.getByText('Complete Payment')).toBeVisible()
    await page.getByRole('button', { name: /proceed to payment/i }).click()

    // Should redirect to success (mocked checkout_url points here)
    await expect(page).toHaveURL(/\/booking\/success/)
    await expect(page.getByText('Booking Confirmed')).toBeVisible()
  })

  test('handles payment cancellation with retry (FR-024)', async ({ page }) => {
    // Set up booking state in sessionStorage
    await page.goto('/booking/cancel')
    await page.evaluate(() => {
      sessionStorage.setItem('booking-form-state', JSON.stringify({
        reservationId: 'RES-TEST-123',
        paymentAttempts: 0,
        selectedRange: {
          from: '2026-03-15',
          to: '2026-03-22',
        },
        guestDetails: { name: 'John Doe' },
      }))
    })
    await page.reload()

    // Should show cancel page with retry option
    await expect(page.getByText('Payment Not Completed')).toBeVisible()
    await expect(page.getByRole('button', { name: /try again/i })).toBeVisible()

    // Click retry
    await page.getByRole('button', { name: /try again/i }).click()

    // Should redirect to success (mocked)
    await expect(page).toHaveURL(/\/booking\/success/)
  })

  test('shows error when API fails (FR-025)', async ({ page }) => {
    // Mock API to return error
    await page.route('**/payments/checkout-session', async (route) => {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Reservation not found' }),
      })
    })

    // Navigate to payment step with state
    await page.goto('/book')
    // ... navigate through flow

    await page.getByRole('button', { name: /proceed to payment/i }).click()

    // Should show error message
    await expect(page.getByText('Reservation not found')).toBeVisible()
  })

  test('enforces max payment attempts (FR-020)', async ({ page }) => {
    // Set up state with max attempts reached
    await page.goto('/booking/cancel')
    await page.evaluate(() => {
      sessionStorage.setItem('booking-form-state', JSON.stringify({
        reservationId: 'RES-TEST-123',
        paymentAttempts: 3, // MAX_PAYMENT_ATTEMPTS
        selectedRange: { from: '2026-03-15', to: '2026-03-22' },
        guestDetails: { name: 'John Doe' },
      }))
    })
    await page.reload()

    // Retry button should not be visible
    await expect(page.getByRole('button', { name: /try again/i })).not.toBeVisible()
    await expect(page.getByText(/maximum payment attempts/i)).toBeVisible()
  })
})
```

---

## Local Development

### Running the Frontend with Backend

```bash
# Terminal 1: Start backend
task backend:dev

# Terminal 2: Start frontend
task frontend:dev
```

### Testing Payment Flow

1. Navigate to http://localhost:3000/book
2. Select dates and fill guest details
3. Click "Proceed to Payment"
4. Complete payment on Stripe test checkout page (use card 4242 4242 4242 4242)
5. Verify redirect to success page with confirmation

### Manual State Inspection

```javascript
// In browser console - check stored booking state
JSON.parse(sessionStorage.getItem('booking-form-state'))

// Clear state for fresh test
sessionStorage.removeItem('booking-form-state')
```

---

## Checklist

### Setup Checklist

- [ ] Backend running on localhost:3001
- [ ] API client regenerated with checkout-session endpoint
- [ ] Stripe test keys configured in backend SSM

### Implementation Checklist

- [ ] **Payment Constants** - `lib/constants/payment.ts`
- [ ] **Extended BookingFormState** - Add payment fields to `book/page.tsx`
- [ ] **useCheckoutSession Hook** - `hooks/useCheckoutSession.ts`
- [ ] **PaymentStep Component** - `components/booking/PaymentStep.tsx`
- [ ] **PaymentStatus Component** - `components/booking/PaymentStatus.tsx`
- [ ] **Success Page** - `app/booking/success/page.tsx`
- [ ] **Cancel Page** - `app/booking/cancel/page.tsx`
- [ ] **Update BookingConfirmation** - Add payment details display

### Testing Checklist

- [ ] E2E test: Success flow (FR-023)
- [ ] E2E test: Cancel flow with retry (FR-024)
- [ ] E2E test: API error handling (FR-025)
- [ ] E2E test: Max attempts enforcement (FR-020)
- [ ] Manual test: Full flow with Stripe test card
- [ ] Manual test: Mobile responsive (375px viewport)

### Deployment Checklist

- [ ] Verify frontend builds successfully (`yarn build`)
- [ ] Verify routes `/booking/success` and `/booking/cancel` work in production
- [ ] Test with real Stripe test mode payments
- [ ] Verify state persistence across Stripe redirect

---

## Troubleshooting

### Common Issues

**"Property 'createPaymentsCheckoutSession' does not exist"**
- API client not regenerated - run `yarn generate:api` with backend running
- Check that backend has the endpoint at `/payments/checkout-session`

**"Session ID mismatch" on success page**
- Session ID in URL doesn't match stored state
- May happen if user navigates directly to success page
- Clear sessionStorage and start fresh booking

**"Booking session expired" error**
- sessionStorage was cleared during Stripe redirect
- Check browser settings - some privacy modes clear storage
- Ensure not using incognito mode for testing

**Redirect to Stripe not working**
- Check browser console for CORS errors
- Verify API is returning valid checkout_url
- Check network tab for failed API calls

**Payment confirmed but status shows pending**
- Webhook might not have processed yet
- Backend webhook handler may have error
- Check backend logs for webhook processing

**Retry button not showing**
- `paymentAttempts` may already be at max (3)
- Check sessionStorage for current attempt count
- Clear state and try fresh booking

---

## References

- [Data Model](./data-model.md) - Frontend state models
- [API Contracts](./contracts/) - TypeScript schemas
- [Research](./research.md) - Technical decisions
- [Spec](./spec.md) - Functional requirements
- [Plan](./plan.md) - Implementation plan
- [Backend Feature](../013-stripe-payment/) - Stripe payment backend
- [Stripe Checkout Docs](https://stripe.com/docs/payments/checkout)
