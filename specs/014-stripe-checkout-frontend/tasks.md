# Tasks: Stripe Checkout Frontend Integration

**Feature**: 014-stripe-checkout-frontend | **Generated**: 2026-01-04
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Data Model**: [data-model.md](./data-model.md)

## Summary

This document defines implementation tasks for the Stripe Checkout frontend integration, organized by user story priority (P1-P4). Tasks are sequenced to deliver complete, testable user value at each priority level.

**Key Dependencies**:
- Backend 013-stripe-payment feature (already complete)
- Existing `/book` page with dates and guest details flow
- Generated API client needs regeneration to include checkout-session endpoint

---

## Prerequisites

Before starting implementation:

```bash
# 1. Ensure backend is running (provides OpenAPI spec)
task backend:dev

# 2. Regenerate frontend API client (CRITICAL - missing checkout-session endpoint)
cd frontend && yarn generate:api

# 3. Verify new types exist
grep -r "checkout" frontend/src/lib/api-client/
# Should show: CheckoutSessionRequest, CheckoutSessionResponse, etc.

# 4. Run existing tests to ensure baseline
task frontend:test
```

---

## Phase P1: Complete Payment via Stripe Checkout

**User Story**: A guest has filled out their booking details and is ready to pay. They click "Proceed to Payment" and are redirected to Stripe's hosted checkout page. After completing payment, they see a confirmation.

**Acceptance Criteria**:
- FR-001 through FR-010 (Checkout Flow + Success Flow)
- SC-001: Full flow under 4 minutes
- SC-002: 95% successful Stripe redirects

### Task P1.1: Regenerate API Client

**File**: `frontend/src/lib/api-client/` (regenerated)
**Type**: Setup
**Dependencies**: Backend running on localhost:3001

```bash
# While backend is running on :3001
cd frontend
yarn generate:api
```

**Verification**:
```bash
grep -r "CheckoutSessionResponse" frontend/src/lib/api-client/
# Should find type definitions
```

**Contract Reference**: Types will match `contracts/checkout-session.types.ts` after generation.

---

### Task P1.2: Add Payment Constants

**File**: `frontend/src/lib/constants/payment.ts` (NEW)
**Type**: Foundation
**Dependencies**: None

**Contract Reference**: `contracts/payment-routes.schema.ts` lines 18-28

```typescript
/**
 * Payment-related constants.
 * @see specs/014-stripe-checkout-frontend/contracts/payment-routes.schema.ts
 * @see FR-020 (max attempts), FR-010 (status polling)
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

**Verification**: TypeScript compiles without errors.

---

### Task P1.3: Extend BookingFormState with Payment Fields

**File**: `frontend/src/app/book/page.tsx` (MODIFY)
**Type**: Foundation
**Dependencies**: P1.2

**Contract Reference**: `data-model.md` "BookingFormState (Extended)" section

**Changes**:
1. Add `'payment'` to `BookingStep` type
2. Add payment fields to `BookingFormState` interface
3. Update `initialFormState` with payment defaults

```typescript
// Add to existing BookingStep type
type BookingStep = 'dates' | 'guest' | 'payment' | 'confirmation'

// Extend BookingFormState interface
interface BookingFormState {
  // Existing fields (unchanged)
  currentStep: BookingStep
  selectedRange: DayPickerRange | undefined
  guestDetails: GuestDetails | null

  // NEW: Payment flow state
  reservationId: string | null
  paymentAttempts: number
  lastPaymentError: string | null
  stripeSessionId: string | null
}

// Update initialFormState
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

**Verification**: Existing booking flow still works (dates → guest), TypeScript compiles.

---

### Task P1.4: Create useCheckoutSession Hook

**File**: `frontend/src/hooks/useCheckoutSession.ts` (NEW)
**Type**: Core Logic
**Dependencies**: P1.1 (regenerated API client), P1.2 (constants)

**Contract Reference**: `contracts/checkout-session.types.ts` lines 41-97

**Implementation Notes**:
- Use generated `createPaymentsCheckoutSession` function from API client
- Handle loading, error, and redirecting states
- Redirect via `window.location.href` to checkout_url
- Expose `createSession`, `retryPayment`, and `clearError` methods

**Test First** (Vitest):
```typescript
// frontend/tests/unit/hooks/useCheckoutSession.test.ts
describe('useCheckoutSession', () => {
  it('should start with initial state', () => { /* ... */ })
  it('should set isLoading during session creation', () => { /* ... */ })
  it('should capture error on API failure', () => { /* ... */ })
  it('should redirect to checkout_url on success', () => { /* ... */ })
})
```

**Verification**: Unit tests pass, hook can be imported without errors.

---

### Task P1.5: Create PaymentStep Component

**File**: `frontend/src/components/booking/PaymentStep.tsx` (NEW)
**Type**: UI Component
**Dependencies**: P1.4 (useCheckoutSession hook)

**Contract Reference**: `contracts/checkout-session.types.ts` lines 138-148 (PaymentStepProps)

**Requirements** (FR-001, FR-002, FR-003, FR-017, FR-021):
- Display booking summary (dates, guest, total amount in EUR)
- "Proceed to Payment" button that calls `createSession`
- Loading state during session creation
- "Redirecting to payment..." state after success
- Error display with dismiss option

**Components Used**: Card, Button, Alert (all from existing shadcn/ui)

**Verification**: Component renders with mock props, button triggers session creation.

---

### Task P1.6: Create Success Page Route

**File**: `frontend/src/app/booking/success/page.tsx` (NEW)
**Type**: Route/Page
**Dependencies**: P1.1 (API client), P1.3 (form state)

**Contract Reference**: `contracts/payment-routes.schema.ts` lines 42-57 (SuccessPageParams)

**Requirements** (FR-006, FR-007, FR-008, FR-009, FR-010):
- Extract `session_id` from URL search params
- Validate session_id format using Zod schema from contracts
- Correlate with stored `stripeSessionId` in sessionStorage
- Call `GET /payments/{reservation_id}/status` to verify payment
- Display confirmation: reservation ID, dates, guest name, amount paid
- Show "Paid" status badge
- Clear sessionStorage after confirmation (FR-009)
- Handle missing/invalid session_id gracefully

**Verification**: Page loads at `/booking/success?session_id=cs_test_xxx`, displays confirmation.

---

### Task P1.7: Integrate PaymentStep into Booking Flow

**File**: `frontend/src/app/book/page.tsx` (MODIFY)
**Type**: Integration
**Dependencies**: P1.3, P1.5, P1.6

**Changes**:
1. Import PaymentStep component
2. After guest details submission, create reservation (pending status)
3. Store `reservationId` in form state
4. Show PaymentStep when `currentStep === 'payment'`
5. Update step navigation: guest → payment (not directly to confirmation)

**Flow Change**:
```
Before: handleGuestSubmit → create reservation → show confirmation
After:  handleGuestSubmit → create reservation → store reservationId → show PaymentStep
        PaymentStep → create checkout session → redirect to Stripe
        Return from Stripe → /booking/success → verify payment → show confirmation
```

**Verification**: Complete flow from dates → guest → payment → Stripe redirect works.

---

### Task P1.8: E2E Test - Success Flow

**File**: `frontend/tests/e2e/checkout-flow.spec.ts` (NEW)
**Type**: Test
**Dependencies**: P1.7 (integrated flow)

**Requirements** (FR-022, FR-023, FR-026):
- Test uses **real Stripe test mode** - actually redirects to Stripe test pages
- Use test card: 4242 4242 4242 4242
- Complete full flow: `/book` → dates → guest → payment → Stripe → `/booking/success`
- Verify confirmation displays reservation ID, dates, payment status

**Test Strategy**:
```typescript
test('completes full booking flow with real Stripe payment', async ({ page }) => {
  // 1. Start booking flow
  await page.goto('/book')

  // 2. Select dates (use calendar component)
  // 3. Fill guest details form
  // 4. Arrive at payment step
  await expect(page.getByText('Complete Payment')).toBeVisible()

  // 5. Click proceed - will redirect to real Stripe test checkout
  await page.getByRole('button', { name: /proceed to payment/i }).click()

  // 6. On Stripe Checkout page, fill test card
  await page.waitForURL(/checkout\.stripe\.com/)
  await page.fill('[placeholder="Card number"]', '4242424242424242')
  await page.fill('[placeholder="MM / YY"]', '12/30')
  await page.fill('[placeholder="CVC"]', '123')
  await page.fill('[placeholder="ZIP"]', '12345')
  await page.click('button[type="submit"]')

  // 7. Redirected to success page
  await page.waitForURL(/\/booking\/success/)
  await expect(page.getByText('Booking Confirmed')).toBeVisible()
  await expect(page.getByText(/RES-/)).toBeVisible() // Reservation ID
})
```

**Note**: Tests may need increased timeout for Stripe redirects (~30s).

**Verification**: `yarn playwright test checkout-flow.spec.ts` passes.

---

### Task P1.9: Handle Reservation Expiry During Payment

**File**: `frontend/src/hooks/useCheckoutSession.ts` (MODIFY)
**Type**: Edge Case
**Dependencies**: P1.4

**Edge Case Reference**: spec.md "What happens if reservation expires during payment?"

**Requirements**:
- Backend returns 400/410 error if reservation expired when creating checkout session
- Hook must detect expiry error and set specific error state
- PaymentStep displays "Reservation expired. Please start a new booking." message
- "Start New Booking" button clears sessionStorage and navigates to `/book`

**Test First** (Vitest):
```typescript
// frontend/tests/unit/hooks/useCheckoutSession.test.ts
it('should handle reservation expiry error', async () => {
  // Mock API to return 410 Gone with expiry message
  // Verify error state is set with isExpired flag
})
```

**Verification**: Unit test passes, error message displayed on expiry.

---

## Phase P2: Handle Payment Cancellation

**User Story**: A guest decides not to complete payment on Stripe. They can return to the booking flow, see their preserved details, and retry payment.

**Acceptance Criteria**:
- FR-011 through FR-014 (Cancel/Failure Flow)
- SC-003: 90% of abandoning users can successfully retry

### Task P2.1: Create Cancel Page Route

**File**: `frontend/src/app/booking/cancel/page.tsx` (NEW)
**Type**: Route/Page
**Dependencies**: P1.3 (form state), P1.4 (useCheckoutSession)

**Contract Reference**: `contracts/payment-routes.schema.ts` lines 68-78 (CancelPageParams)

**Requirements** (FR-011, FR-012, FR-013, FR-014):
- Restore form state from sessionStorage (dates, guest details preserved)
- Display message: "Payment was not completed"
- Show preserved booking details
- Show "Try Again" button if `paymentAttempts < MAX_PAYMENT_ATTEMPTS`
- "Try Again" creates new checkout session via `retryPayment`
- "Modify Booking" button returns to `/book` with state preserved

**Verification**: Page loads at `/booking/cancel`, shows preserved details and retry option.

---

### Task P2.2: E2E Test - Cancel Flow

**File**: `frontend/tests/e2e/checkout-flow.spec.ts` (MODIFY)
**Type**: Test
**Dependencies**: P2.1

**Requirements** (FR-024):
- Test Stripe cancel button/back navigation
- Verify return to `/booking/cancel`
- Verify booking details preserved
- Verify retry creates new session and redirects again

```typescript
test('handles payment cancellation with retry', async ({ page }) => {
  // 1. Start booking flow through to payment step
  // 2. Click proceed to payment (redirects to Stripe)
  // 3. On Stripe page, click back/cancel
  await page.waitForURL(/checkout\.stripe\.com/)
  await page.click('[aria-label="Back"]') // Stripe's back button

  // 4. Should return to cancel page
  await page.waitForURL(/\/booking\/cancel/)
  await expect(page.getByText('Payment Not Completed')).toBeVisible()

  // 5. Verify preserved details shown
  await expect(page.getByText(/Check-in/)).toBeVisible()

  // 6. Click retry
  await page.getByRole('button', { name: /try again/i }).click()

  // 7. Should redirect to Stripe again
  await page.waitForURL(/checkout\.stripe\.com/)
})
```

**Verification**: E2E test passes with real Stripe cancel flow.

---

## Phase P3: Payment Status Display

**User Story**: A guest wants to check if their payment went through. They see clear visual indication of payment status with appropriate messaging.

**Acceptance Criteria**:
- FR-015 through FR-017 (Payment Status Display)
- SC-006: Status displayed within 5 seconds of return

### Task P3.1: Create PaymentStatusBadge Component

**File**: `frontend/src/components/booking/PaymentStatusBadge.tsx` (NEW)
**Type**: UI Component
**Dependencies**: None (can be built in parallel with P1)

**Contract Reference**: `contracts/checkout-session.types.ts` lines 155-162, `contracts/payment-routes.schema.ts` lines 90-161

**Requirements** (FR-015, FR-017):
- Display status badge: Pending, Processing, Paid, Failed, Refunded
- Use variant colors from PAYMENT_STATUS_CONFIG
- Show amount in EUR when provided
- Used by: BookingConfirmation, Success page, Cancel page

```typescript
interface PaymentStatusBadgeProps {
  status: 'pending' | 'processing' | 'paid' | 'failed' | 'refunded'
  amount?: number  // EUR cents
  currency?: string // default: 'EUR'
}
```

**Verification**: Component renders all status variants correctly.

---

### Task P3.2: Create usePaymentStatus Hook

**File**: `frontend/src/hooks/usePaymentStatus.ts` (NEW)
**Type**: Core Logic
**Dependencies**: P1.1 (API client), P1.2 (constants)

**Contract Reference**: `contracts/checkout-session.types.ts` lines 54-64, 104-128

**Requirements** (FR-010):
- Fetch payment status via `GET /payments/{reservation_id}/status`
- Support polling with configurable interval (PAYMENT_STATUS_POLL_INTERVAL)
- Stop polling after timeout (PAYMENT_STATUS_POLL_TIMEOUT) or when confirmed
- Expose `fetchStatus`, `startPolling`, `stopPolling` methods

**Use Case**: Success page polls for confirmation if webhook hasn't processed yet.

**Verification**: Hook fetches status, polling starts/stops correctly.

---

### Task P3.3: Enhance BookingConfirmation Component

**File**: `frontend/src/components/booking/BookingConfirmation.tsx` (MODIFY)
**Type**: Enhancement
**Dependencies**: P3.1 (PaymentStatusBadge)

**Contract Reference**: `contracts/checkout-session.types.ts` lines 187-202 (BookingConfirmationProps)

**Requirements** (FR-007, FR-008, FR-015):
- Add PaymentStatusBadge showing payment status
- Display amount paid when status is 'paid'
- Show "Complete Payment" button if status is 'pending'
- Show "Retry Payment" button if status is 'failed'

**Verification**: Component shows appropriate UI for each payment status.

---

### Task P3.4: Integrate Status Polling in Success Page

**File**: `frontend/src/app/booking/success/page.tsx` (MODIFY)
**Type**: Enhancement
**Dependencies**: P3.2 (usePaymentStatus), P1.6 (success page)

**Requirements** (FR-010, Edge Case: webhook delay):
- On page load, immediately fetch status
- If status is not 'paid', start polling
- Show "Processing..." state during polling
- Stop polling when confirmed or timeout reached
- On timeout, show message: "Taking longer than expected. Check back shortly."

**Verification**: Page handles webhook delay gracefully with polling.

---

### Task P3.5: E2E Test - Webhook Delay Polling

**File**: `frontend/tests/e2e/checkout-flow.spec.ts` (MODIFY)
**Type**: Test
**Dependencies**: P3.4

**Edge Case Reference**: spec.md "What happens if Stripe redirects back but webhook hasn't processed yet?"

**Requirements** (Edge Case validation):
```typescript
test('handles delayed webhook with polling', async ({ page }) => {
  // Mock initial status response as 'processing'
  let callCount = 0
  await page.route('**/payments/*/status', async (route) => {
    callCount++
    if (callCount < 3) {
      // First two calls return processing
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'processing' }),
      })
    } else {
      // Third call returns paid
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'paid', amount: 50000 }),
      })
    }
  })

  // Navigate to success page with valid session_id
  await page.goto('/booking/success?session_id=cs_test_xxx')

  // Should show "Processing..." initially
  await expect(page.getByText(/processing/i)).toBeVisible()

  // Wait for polling to complete and show confirmation
  await expect(page.getByText('Booking Confirmed')).toBeVisible({ timeout: 10000 })
})
```

**Verification**: E2E test passes with mocked delayed webhook response.

---

## Phase P4: Payment Retry After Failure

**User Story**: A guest's card was declined. They can retry with a different card without losing their reservation, up to 3 attempts.

**Acceptance Criteria**:
- FR-018 through FR-021 (Error Handling)
- SC-008: Users with 3+ failed attempts see appropriate messaging

### Task P4.1: Create PaymentRetryButton Component

**File**: `frontend/src/components/booking/PaymentRetryButton.tsx` (NEW)
**Type**: UI Component
**Dependencies**: P1.4 (useCheckoutSession), P1.2 (MAX_PAYMENT_ATTEMPTS)

**Contract Reference**: `contracts/checkout-session.types.ts` lines 169-180 (PaymentRetryButtonProps)

**Requirements** (FR-014, FR-020):
- Display retry button with attempts remaining count
- Disable when `attemptCount >= MAX_PAYMENT_ATTEMPTS`
- Call `onMaxAttemptsReached` callback when max reached
- Show loading state during retry

**Verification**: Button disables at max attempts, shows correct count.

---

### Task P4.2: Implement Retry Attempt Tracking

**File**: `frontend/src/app/booking/cancel/page.tsx` (MODIFY)
**Type**: Enhancement
**Dependencies**: P2.1, P4.1

**Requirements** (FR-020):
- Increment `paymentAttempts` in sessionStorage before each retry
- Check attempts before allowing retry
- When max reached, hide retry button and show support message:
  "Maximum payment attempts reached. Please contact support or try booking again later."

**Verification**: After 3 failed attempts, retry button hidden, message shown.

---

### Task P4.3: E2E Test - Max Attempts

**File**: `frontend/tests/e2e/checkout-flow.spec.ts` (MODIFY)
**Type**: Test
**Dependencies**: P4.2

**Requirements** (FR-020, SC-008):
```typescript
test('enforces max payment attempts', async ({ page }) => {
  // Set up state with max attempts reached
  await page.goto('/booking/cancel')
  await page.evaluate(() => {
    sessionStorage.setItem('booking-form-state', JSON.stringify({
      reservationId: 'RES-TEST-123',
      paymentAttempts: 3, // MAX_PAYMENT_ATTEMPTS
      selectedRange: { from: '2026-03-15', to: '2026-03-22' },
      guestDetails: { firstName: 'John', lastName: 'Doe' },
    }))
  })
  await page.reload()

  // Retry button should not be visible
  await expect(page.getByRole('button', { name: /try again/i })).not.toBeVisible()
  await expect(page.getByText(/maximum payment attempts/i)).toBeVisible()
})
```

**Verification**: E2E test passes.

---

### Task P4.4: E2E Test - Error Handling

**File**: `frontend/tests/e2e/checkout-flow.spec.ts` (MODIFY)
**Type**: Test
**Dependencies**: P1.7

**Requirements** (FR-018, FR-019, FR-025):
```typescript
test('handles API error gracefully', async ({ page }) => {
  // Mock checkout-session API to fail
  await page.route('**/payments/checkout-session', async (route) => {
    await route.fulfill({
      status: 400,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Reservation not found' }),
    })
  })

  // Navigate through booking flow to payment step
  // ... (setup code)

  // Click proceed to payment
  await page.getByRole('button', { name: /proceed to payment/i }).click()

  // Should show error message (not crash)
  await expect(page.getByText('Reservation not found')).toBeVisible()

  // Dismiss button should work
  await page.getByRole('button', { name: /dismiss/i }).click()
  await expect(page.getByText('Reservation not found')).not.toBeVisible()
})
```

**Verification**: E2E test passes.

---

### Task P4.5: E2E Test - Mobile Viewport

**File**: `frontend/tests/e2e/checkout-flow.spec.ts` (MODIFY)
**Type**: Test
**Dependencies**: P1.7

**Success Criteria Reference**: SC-007 "Mobile users can complete payment flow (375px viewport)"

**Requirements**:
```typescript
test.describe('mobile viewport', () => {
  test.use({ viewport: { width: 375, height: 667 } }) // iPhone SE

  test('completes checkout flow on mobile', async ({ page }) => {
    // Navigate through booking flow on mobile viewport
    await page.goto('/book')

    // Verify key elements are visible and interactive
    await expect(page.getByRole('button', { name: /select dates/i })).toBeVisible()

    // Complete date selection (calendar should be usable)
    // Complete guest details (form should be scrollable)
    // Proceed to payment (button should be tappable)

    // Verify no horizontal overflow
    const body = page.locator('body')
    const bodyWidth = await body.evaluate(el => el.scrollWidth)
    const viewportWidth = 375
    expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 1) // Allow 1px tolerance
  })
})
```

**Verification**: E2E test passes on 375px viewport without horizontal scroll.

---

## Task Dependency Graph

```
P1.1 (Regenerate SDK)
  │
  ├──► P1.4 (useCheckoutSession Hook)
  │      │
  │      └──► P1.5 (PaymentStep) ──► P1.7 (Integration)
  │                                       │
P1.2 (Constants)                          │
  │                                       │
  └──► P1.3 (BookingFormState) ──────────┘
         │                                │
         └──► P1.6 (Success Page) ◄──────┘
               │
               └──► P1.8 (E2E Success)

P2.1 (Cancel Page) ──► P2.2 (E2E Cancel)
  │
  └─── depends on P1.3, P1.4

P3.1 (PaymentStatusBadge) ──► P3.3 (BookingConfirmation)
                                    │
P3.2 (usePaymentStatus) ──────────┬─┘
                                  │
                                  └──► P3.4 (Success Page Polling)

P4.1 (PaymentRetryButton) ──► P4.2 (Retry Tracking)
                                    │
                                    └──► P4.3 (E2E Max Attempts)

P4.4 (E2E Error Handling) ── depends on P1.7
```

---

## Parallel Execution Opportunities

Tasks that can be worked on simultaneously:

**Parallel Group 1** (Foundation):
- P1.2 (Constants)
- P3.1 (PaymentStatusBadge)

**Parallel Group 2** (After P1.1):
- P1.4 (useCheckoutSession)
- P3.2 (usePaymentStatus)

**Parallel Group 3** (After P1.7):
- P2.1 (Cancel Page)
- P3.4 (Success Page Polling)
- P4.1 (PaymentRetryButton)

**Parallel Group 4** (Tests - after respective implementations):
- P1.8 (E2E Success)
- P2.2 (E2E Cancel)
- P4.3 (E2E Max Attempts)
- P4.4 (E2E Error)

---

## Completion Checklist

### P1 - Complete Payment (Core)
- [ ] P1.1: API client regenerated
- [ ] P1.2: Payment constants added
- [ ] P1.3: BookingFormState extended
- [ ] P1.4: useCheckoutSession hook created
- [ ] P1.5: PaymentStep component created
- [ ] P1.6: Success page route created
- [ ] P1.7: PaymentStep integrated into booking flow
- [ ] P1.8: E2E success flow test passes

### P2 - Handle Cancellation
- [ ] P2.1: Cancel page route created
- [ ] P2.2: E2E cancel flow test passes

### P3 - Payment Status Display
- [ ] P3.1: PaymentStatusBadge component created
- [ ] P3.2: usePaymentStatus hook created
- [ ] P3.3: BookingConfirmation enhanced
- [ ] P3.4: Success page polling implemented

### P4 - Payment Retry
- [ ] P4.1: PaymentRetryButton component created
- [ ] P4.2: Retry tracking implemented
- [ ] P4.3: E2E max attempts test passes
- [ ] P4.4: E2E error handling test passes

---

## Estimated Task Distribution

| Phase | Tasks | Core | Tests | Estimated Effort |
|-------|-------|------|-------|------------------|
| P1 | 8 | 7 | 1 | ~60% of feature |
| P2 | 2 | 1 | 1 | ~15% of feature |
| P3 | 4 | 4 | 0 | ~15% of feature |
| P4 | 4 | 2 | 2 | ~10% of feature |

**Total**: 18 tasks

---

## References

- [Spec](./spec.md) - User stories and acceptance criteria
- [Plan](./plan.md) - Technical context and structure
- [Data Model](./data-model.md) - State interfaces and type mappings
- [Contracts](./contracts/) - TypeScript schemas and validation
- [Research](./research.md) - Key technical decisions
- [Quickstart](./quickstart.md) - Development workflow and examples
