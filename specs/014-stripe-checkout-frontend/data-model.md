# Data Model: Stripe Checkout Frontend Integration

**Phase**: 1 | **Date**: 2026-01-04 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

## Overview

This document defines frontend-specific data models for the Stripe Checkout Frontend Integration feature. Models follow these conventions:

- **Extend existing types** where appropriate (BookingFormState)
- **Use TypeScript strict mode** for all interfaces
- **Generated types** from backend OpenAPI spec via `@hey-api/openapi-ts`
- **UI state models** separate from API response types
- **sessionStorage serialization** support for Date objects

> **Note**: Backend API types (CheckoutSessionRequest, CheckoutSessionResponse, PaymentStatusResponse, etc.) are **generated** from the OpenAPI spec.
> This document focuses on **frontend-specific** state management types that are NOT generated.

---

## Generated API Types (from Backend)

After running `yarn generate:api`, these types will be available in `frontend/src/lib/api-client/`:

| Type | Source | Purpose |
|------|--------|---------|
| `CheckoutSessionRequest` | Generated | Request to create Stripe Checkout session |
| `CheckoutSessionResponse` | Generated | Stripe Checkout URL and session details |
| `PaymentStatusResponse` | Generated | Payment status for a reservation |
| `PaymentHistoryResponse` | Generated | Full payment history with attempts |
| `PaymentRetryRequest` | Generated | Request to retry failed payment |
| `RefundRequest` | Generated | Refund initiation (admin only) |
| `RefundResponse` | Generated | Refund result |
| `Payment` | Generated | Payment record with Stripe IDs |

### Key Generated Types (for reference)

```typescript
// From backend/api/models/payments.py → Generated SDK

interface CheckoutSessionResponse {
  payment_id: string
  checkout_session_id: string
  checkout_url: string          // Redirect user here
  expires_at: string            // ISO datetime
  amount: number                // EUR cents
  currency: string              // "EUR"
  attempt_number?: number       // 1-3
}

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

## Frontend State Models

### BookingStep (Extended)

**File**: `frontend/src/app/book/page.tsx`
**Action**: MODIFY - Add 'payment' step

```typescript
// Current (3 steps)
type BookingStep = 'dates' | 'guest' | 'confirmation'

// New (4 steps)
type BookingStep = 'dates' | 'guest' | 'payment' | 'confirmation'
```

**Flow Change**:
```
Before: dates → guest → confirmation
After:  dates → guest → payment → confirmation
```

---

### BookingFormState (Extended)

**File**: `frontend/src/app/book/page.tsx`
**Action**: MODIFY - Add payment-related fields for persistence during Stripe redirect

```typescript
import type { DateRange as DayPickerRange } from 'react-day-picker'
import type { GuestDetails } from '@/lib/schemas/booking-form.schema'

interface BookingFormState {
  // Existing fields (unchanged)
  currentStep: BookingStep
  selectedRange: DayPickerRange | undefined
  guestDetails: GuestDetails | null

  // NEW: Payment flow state (persist across Stripe redirect)
  reservationId: string | null       // Created before redirect to Stripe
  paymentAttempts: number            // Track retry count (max 3)
  lastPaymentError: string | null    // Display error message on return
  stripeSessionId: string | null     // For correlation on return from Stripe
}
```

**Initial State**:
```typescript
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

**Persistence Notes**:
- Uses existing `useFormPersistence` hook with `serializeWithDates` / `deserializeWithDates`
- sessionStorage key: `'booking-form-state'` (unchanged)
- State survives Stripe redirect (same-origin navigation)
- State cleared on successful payment confirmation

---

### PaymentDisplayStatus

**File**: `frontend/src/components/booking/PaymentStatus.tsx` (NEW)
**Purpose**: UI-friendly payment status for display

```typescript
/**
 * Payment status for UI display.
 * Maps backend TransactionStatus to user-friendly states.
 */
type PaymentDisplayStatus =
  | 'pending'      // Awaiting payment
  | 'processing'   // Returned from Stripe, verifying
  | 'paid'         // Payment confirmed
  | 'failed'       // Payment declined/errored
  | 'refunded'     // Payment refunded

/**
 * Configuration for each status display.
 */
interface PaymentStatusConfig {
  status: PaymentDisplayStatus
  label: string
  variant: 'default' | 'secondary' | 'destructive' | 'outline'
  description: string
  showRetry: boolean
  showComplete: boolean
}

const PAYMENT_STATUS_CONFIG: Record<PaymentDisplayStatus, PaymentStatusConfig> = {
  pending: {
    status: 'pending',
    label: 'Payment Required',
    variant: 'secondary',
    description: 'Complete payment to confirm your booking',
    showRetry: false,
    showComplete: true,
  },
  processing: {
    status: 'processing',
    label: 'Processing...',
    variant: 'outline',
    description: 'Verifying your payment',
    showRetry: false,
    showComplete: false,
  },
  paid: {
    status: 'paid',
    label: 'Paid',
    variant: 'default',
    description: 'Your booking is confirmed',
    showRetry: false,
    showComplete: false,
  },
  failed: {
    status: 'failed',
    label: 'Payment Failed',
    variant: 'destructive',
    description: 'Your payment could not be processed',
    showRetry: true,
    showComplete: false,
  },
  refunded: {
    status: 'refunded',
    label: 'Refunded',
    variant: 'outline',
    description: 'Your payment has been refunded',
    showRetry: false,
    showComplete: false,
  },
}
```

---

### CheckoutSessionState

**File**: `frontend/src/hooks/useCheckoutSession.ts` (NEW)
**Purpose**: Hook state for managing Stripe Checkout flow

```typescript
/**
 * State for the checkout session creation process.
 */
interface CheckoutSessionState {
  /** Whether a checkout session is being created */
  isLoading: boolean
  /** Error message if session creation failed */
  error: string | null
  /** Created session data (before redirect) */
  session: CheckoutSessionResponse | null
}

/**
 * Result of the useCheckoutSession hook.
 */
interface UseCheckoutSessionResult {
  /** Current state */
  state: CheckoutSessionState
  /** Create a new checkout session and redirect to Stripe */
  createSession: (reservationId: string) => Promise<void>
  /** Retry payment for a reservation */
  retryPayment: (reservationId: string) => Promise<void>
  /** Reset error state */
  clearError: () => void
}
```

**Hook Implementation Notes**:
```typescript
// Usage in PaymentStep component
const { state, createSession, retryPayment, clearError } = useCheckoutSession()

// Create session triggers:
// 1. API call to POST /payments/checkout-session
// 2. Store session info in BookingFormState
// 3. Redirect to session.checkout_url
```

---

### SuccessPageParams

**File**: `frontend/src/app/booking/success/page.tsx` (NEW)
**Purpose**: Query parameters from Stripe redirect

```typescript
/**
 * Query parameters on the success page after Stripe redirect.
 * Stripe adds session_id automatically via {CHECKOUT_SESSION_ID} template.
 */
interface SuccessPageSearchParams {
  session_id?: string  // Stripe Checkout Session ID (cs_xxx)
}
```

**Usage**:
```typescript
export default function SuccessPage({
  searchParams,
}: {
  searchParams: SuccessPageSearchParams
}) {
  const sessionId = searchParams.session_id
  // Use sessionId to correlate with stored stripeSessionId
  // Fetch payment status via GET /payments/{reservation_id}
}
```

---

### CancelPageState

**File**: `frontend/src/app/booking/cancel/page.tsx` (NEW)
**Purpose**: State for cancelled payment handling

```typescript
/**
 * State derived from sessionStorage on cancel page.
 * User returns from Stripe without completing payment.
 */
interface CancelPageState {
  /** Reservation that was being paid for */
  reservationId: string | null
  /** Number of payment attempts so far */
  paymentAttempts: number
  /** Whether retry is allowed (< 3 attempts) */
  canRetry: boolean
  /** Original booking details for display */
  bookingDates: {
    checkIn: Date
    checkOut: Date
  } | null
  guestName: string | null
}
```

---

## URL Route Query Parameters

### `/booking/success`

| Parameter | Type | Source | Description |
|-----------|------|--------|-------------|
| `session_id` | string | Stripe | Checkout Session ID for verification |

**Example**: `/booking/success?session_id=cs_test_abc123def456`

### `/booking/cancel`

No query parameters. State restored from sessionStorage.

**Example**: `/booking/cancel`

---

## Model Relationships (Frontend)

```
┌─────────────────────────────┐
│     BookingFormState        │
│     (sessionStorage)        │
├─────────────────────────────┤
│ currentStep: BookingStep    │
│ selectedRange               │
│ guestDetails                │
│ reservationId ──────────────┼──────► Backend Reservation
│ paymentAttempts             │
│ lastPaymentError            │
│ stripeSessionId ────────────┼──────► Stripe Checkout Session
└─────────────────────────────┘
              │
              │ persists across
              ▼
┌─────────────────────────────┐
│      Stripe Redirect        │
│  checkout.stripe.com/c/pay  │
└─────────────────────────────┘
              │
              │ returns to
              ▼
┌─────────────────────────────┐
│    /booking/success         │
│    ?session_id=cs_xxx       │
│                             │
│  Correlates with:           │
│  - stripeSessionId (storage)│
│  - reservationId (storage)  │
└─────────────────────────────┘
```

---

## Validation Rules

### Payment Step Entry

| Condition | Rule | Error |
|-----------|------|-------|
| Dates selected | `selectedRange` has `from` and `to` | "Please select dates first" |
| Guest details filled | `guestDetails` is not null | "Please fill guest details first" |
| Reservation created | `reservationId` is not null | (Internal - create before payment) |

### Retry Validation

| Condition | Rule | Error |
|-----------|------|-------|
| Max attempts | `paymentAttempts < 3` | "Maximum payment attempts reached. Please contact support." |
| Reservation valid | Fetch reservation, check status | "Reservation expired or already paid" |

### Success Page Validation

| Condition | Rule | Action |
|-----------|------|--------|
| session_id present | Query param exists | If missing, redirect to /book |
| session_id matches | Matches `stripeSessionId` in storage | If mismatch, show warning |
| Payment confirmed | API returns `has_completed_payment: true` | Show confirmation |
| Payment pending | API returns `has_completed_payment: false` | Show "processing" with polling |

---

## Type Mapping (Backend → Frontend)

| Backend Type | Frontend Type | Notes |
|--------------|---------------|-------|
| `TransactionStatus.pending` | `PaymentDisplayStatus.pending` | Direct map |
| `TransactionStatus.completed` | `PaymentDisplayStatus.paid` | Rename for clarity |
| `TransactionStatus.failed` | `PaymentDisplayStatus.failed` | Direct map |
| `TransactionStatus.refunded` | `PaymentDisplayStatus.refunded` | Direct map |
| (intermediate) | `PaymentDisplayStatus.processing` | Frontend-only state |

---

## Storage Schema

### sessionStorage: `booking-form-state`

```json
{
  "currentStep": "payment",
  "selectedRange": {
    "from": "2026-03-15T00:00:00.000Z",
    "to": "2026-03-22T00:00:00.000Z"
  },
  "guestDetails": {
    "firstName": "John",
    "lastName": "Doe",
    "email": "john@example.com",
    "phone": "+34 612 345 678",
    "guestCount": 2,
    "specialRequests": ""
  },
  "reservationId": "RES-2026-ABC123",
  "paymentAttempts": 0,
  "lastPaymentError": null,
  "stripeSessionId": "cs_test_abc123def456"
}
```

**Serialization**: Uses `serializeWithDates()` / `deserializeWithDates()` from `useFormPersistence` for Date handling.

---

## Constants

```typescript
// frontend/src/lib/constants/payment.ts

/** Maximum allowed payment attempts before requiring support contact */
export const MAX_PAYMENT_ATTEMPTS = 3

/** Stripe Checkout session validity in minutes */
export const CHECKOUT_SESSION_EXPIRY_MINUTES = 30

/** Polling interval for payment status verification (ms) */
export const PAYMENT_STATUS_POLL_INTERVAL = 2000

/** Maximum polling duration before showing fallback message (ms) */
export const PAYMENT_STATUS_POLL_TIMEOUT = 30000
```
