# Research: Stripe Checkout Frontend Integration

**Feature**: 014-stripe-checkout-frontend
**Date**: 2026-01-04
**Purpose**: Resolve all NEEDS CLARIFICATION items from plan.md

## Research Questions

### RQ-001: SDK Regeneration for Checkout Session Endpoint

**Question**: Is the `checkout-session` endpoint present in the backend OpenAPI spec? Why is it missing from the generated SDK?

**Investigation**:
1. Backend has the endpoint at `POST /payments/checkout-session` (confirmed in `backend/api/src/api/routes/payments.py:53-119`)
2. Generated SDK at `frontend/src/lib/api-client/sdk.gen.ts` does NOT contain this endpoint
3. SDK generation config in `frontend/openapi-ts.config.ts` fetches from `localhost:3001/openapi.json`

**Root Cause**: The SDK was last generated before the 013-stripe-payment feature was merged. The backend has the endpoints, but the frontend SDK hasn't been regenerated.

**Resolution**: Run `yarn generate:api` while backend is running on port 3001 to regenerate the SDK with all payment endpoints.

**Constitution Compliance**: ✅ This follows constitution principle VI (Frontend API Integration) - regenerating client when OpenAPI spec changes.

---

### RQ-002: Route URL Discrepancy (spec vs backend)

**Question**: The spec lists `/book/success` and `/book/cancel` but backend defines `/booking/success` and `/booking/cancel`. Which is correct?

**Investigation**:
- Backend code at `backend/api/src/api/routes/payments.py:68-69`:
  ```python
  success_url = f"{base_url}/booking/success?session_id={{CHECKOUT_SESSION_ID}}"
  cancel_url = f"{base_url}/booking/cancel"
  ```
- Current frontend structure has `/book` page (existing booking flow)
- Backend uses `FRONTEND_URL` environment variable for redirect base URL

**Resolution**: Use backend-defined routes (`/booking/*`) since:
1. Backend is already deployed and generating these URLs for Stripe
2. Changing backend URLs would require redeployment and could break existing checkout sessions
3. Frontend must match what Stripe will redirect to

**Impact on Implementation**:
- Create new routes at `/app/booking/success/page.tsx` and `/app/booking/cancel/page.tsx`
- These are separate from the `/app/book/page.tsx` booking flow
- The `/booking/` routes are Stripe redirect handlers, not part of the main booking wizard

---

### RQ-003: Existing shadcn/ui Components Available

**Question**: What shadcn/ui components are already installed and can be used?

**Available Components** (from `frontend/src/components/ui/`):
| Component | Status | Use Case in Feature |
|-----------|--------|---------------------|
| `alert.tsx` | ✅ Installed | Error messages, payment failure alerts |
| `badge.tsx` | ✅ Installed | Payment status badges (Pending, Paid, Failed) |
| `button.tsx` | ✅ Installed | Actions (Proceed to Payment, Retry, etc.) |
| `calendar.tsx` | ✅ Installed | N/A (dates already selected) |
| `card.tsx` | ✅ Installed | Payment step container, status cards |
| `dialog.tsx` | ✅ Installed | Confirmation dialogs if needed |
| `form.tsx` | ✅ Installed | N/A (no form inputs for payment step) |
| `input.tsx` | ✅ Installed | N/A |
| `label.tsx` | ✅ Installed | N/A |
| `select.tsx` | ✅ Installed | N/A |
| `skeleton.tsx` | ✅ Installed | Loading states |
| `textarea.tsx` | ✅ Installed | N/A |

**New Components Needed**: None - all required UI can be built with existing components.

---

### RQ-004: Form State Persistence Strategy

**Question**: How should booking form state be preserved during Stripe redirect?

**Investigation**:
1. Existing `useFormPersistence` hook at `frontend/src/hooks/useFormPersistence.ts`
2. Currently persists `BookingFormState` with key `'booking-form-state'`
3. Uses sessionStorage with custom serialization for dates

**Current State Shape** (from `/book/page.tsx`):
```typescript
interface BookingFormState {
  currentStep: BookingStep
  selectedRange: DayPickerRange | undefined
  guestDetails: GuestDetails | null
}
```

**Enhanced State Shape for Payment Flow**:
```typescript
interface BookingFormState {
  currentStep: BookingStep  // Add 'payment' step
  selectedRange: DayPickerRange | undefined
  guestDetails: GuestDetails | null
  // NEW: Payment-related state
  reservationId: string | null      // Created before redirect to Stripe
  paymentAttempts: number           // Track retry count (max 3)
  lastPaymentError: string | null   // Display on return from failed payment
  stripeSessionId: string | null    // For correlation on return
}
```

**Resolution**: Extend existing `useFormPersistence` hook with payment fields. State survives Stripe redirect because sessionStorage persists across navigations.

---

### RQ-005: Backend API Contract Summary

**Question**: What endpoints are available and what are their contracts?

**Endpoints from 013-stripe-payment**:

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/payments/checkout-session` | POST | JWT | Create Stripe Checkout session |
| `/payments/{reservation_id}` | GET | JWT | Get payment status |
| `/payments/{reservation_id}/history` | GET | JWT | Full payment history |
| `/payments/{reservation_id}/retry` | POST | JWT | Retry failed payment |
| `/payments/refund/{payment_id}` | POST | JWT | Initiate refund (out of scope for frontend) |

**Key Types**:

```typescript
// Request
interface CheckoutSessionRequest {
  reservation_id: string
  success_url?: string | null  // Optional - backend defaults to FRONTEND_URL/booking/success
  cancel_url?: string | null   // Optional - backend defaults to FRONTEND_URL/booking/cancel
}

// Response
interface CheckoutSessionResponse {
  payment_id: string
  checkout_session_id: string
  checkout_url: string          // Redirect user here
  expires_at: string            // ISO datetime
  amount: number                // EUR cents
  currency: string              // "EUR"
  attempt_number?: number       // 1-3
}

// Status Response
interface PaymentStatusResponse {
  reservation_id: string
  payment: Payment | null
  has_completed_payment: boolean
  is_refunded: boolean
  refund_amount: number | null
  payment_attempts: number
}
```

---

### RQ-006: E2E Testing Strategy with Stripe

**Question**: How to test Stripe Checkout flow in Playwright without real Stripe interaction?

**Options Considered**:

1. **Mock Stripe redirect at network level** - Intercept navigation to checkout.stripe.com
2. **Use Stripe test mode with real redirect** - Actually redirect to Stripe test mode
3. **Mock API responses only** - Don't test actual Stripe redirect

**Recommendation**: Option 1 (Mock Stripe redirect)

**Rationale**:
- Stripe Checkout is hosted by Stripe - we can't control it
- Testing with real Stripe adds flakiness and external dependency
- We want to test OUR code: the redirect initiation and return handling

**Testing Approach**:
```typescript
// Mock the checkout-session API to return a mock URL
await page.route('**/payments/checkout-session', async route => {
  await route.fulfill({
    json: {
      checkout_url: 'http://localhost:3000/booking/success?session_id=mock_session',
      payment_id: 'PAY-TEST-123',
      // ...
    }
  })
})

// Or intercept the actual redirect
await page.route('https://checkout.stripe.com/**', async route => {
  // Redirect back to success URL
  await page.goto('/booking/success?session_id=mock_session')
})
```

**Test Scenarios**:
1. Success flow: Mock API → Mock redirect → Success page
2. Cancel flow: Mock API → Simulate back button → Cancel page
3. Error flow: Mock API returns error → Error display
4. Retry flow: Return with error → Click retry → Mock new session

---

### RQ-007: Booking Flow Step Modification

**Question**: How to add payment step to existing 3-step flow?

**Current Flow** (in `/app/book/page.tsx`):
```
dates → guest → confirmation
```

**New Flow Required**:
```
dates → guest → payment → confirmation
```

**Implementation Approach**:
1. Add `'payment'` to `BookingStep` type
2. After guest details submission:
   - Create reservation (status: 'pending')
   - Create checkout session
   - Store `reservationId` and `stripeSessionId` in form state
   - Redirect to Stripe Checkout
3. On return from Stripe:
   - Success: Fetch reservation with payment status, show confirmation
   - Cancel: Return to payment step with retry option

**Key Change**: Currently `handleGuestSubmit` creates reservation and immediately shows confirmation. New flow:
1. `handleGuestSubmit` → creates reservation → shows payment step
2. Payment step → calls checkout-session API → redirects to Stripe
3. `/booking/success` → verifies payment → shows confirmation

---

## Constitution Re-Check (Post-Research)

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First Development | ✅ PASS | E2E tests with Playwright mocking strategy defined |
| II. Simplicity & YAGNI | ✅ PASS | Using existing hooks, components; minimal new code |
| III. Type Safety | ✅ PASS | Using generated API client types |
| VI. Technology Stack - UI Components | ✅ PASS | All UI from existing shadcn/ui components |
| VI. Technology Stack - Frontend API Integration | ✅ PASS | Regenerate SDK before implementation |

## Summary

All research questions resolved. Key findings:

1. **SDK Regeneration**: Required before any implementation work
2. **Routes**: Use `/booking/success` and `/booking/cancel` (backend-defined)
3. **Components**: All shadcn/ui components already available
4. **State Persistence**: Extend existing `useFormPersistence` hook
5. **Testing**: Mock Stripe redirect at network level in Playwright
6. **Flow**: Add payment step between guest details and confirmation

No blockers identified. Ready for Phase 1 design artifacts.
