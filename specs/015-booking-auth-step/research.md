# Research: Booking Authentication Step

**Feature Branch**: `015-booking-auth-step`
**Date**: 2025-01-05
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Executive Summary

This research documents findings from investigating the existing OTP authentication flow, shadcn/ui component availability, and form persistence patterns. All critical questions are resolved with actionable recommendations.

---

## 1. OTP Authentication Flow - Bug Analysis

### 1.1 Critical Bugs Requiring Fix

| Bug | Severity | Location | Impact |
|-----|----------|----------|--------|
| OTP code not cleared between attempts | Medium | GuestDetailsForm.tsx:75-76 | Stale codes confuse users |
| Retry resets to anonymous during OTP | High | useAuthenticatedUser.ts:370-380 | Wrong UX for network errors |
| Missing AuthErrorBoundary component | High | Test references non-existent file | Runtime error protection missing |
| pendingEmail not updated on resend | Medium | GuestDetailsForm.tsx:386-400 | Wrong email receives OTP |

### 1.2 Bug Details

#### Bug 1: OTP Code Not Cleared (GuestDetailsForm.tsx:75-76)

**Current Code:**
```typescript
const [otpCode, setOtpCode] = useState('')
// otpCode is NEVER cleared after failed verification or "Resend code"
```

**Problem:** After entering an invalid code, clicking "Resend code" leaves the old code visible.

**Fix:** Clear `otpCode` when:
1. User clicks "Resend code"
2. OTP verification fails
3. Error type is `expired`

---

#### Bug 2: Retry Resets to Anonymous During OTP (useAuthenticatedUser.ts:370-380)

**Current Code:**
```typescript
const retry = useCallback(() => {
  // ...
  if (currentErrorType === 'network') {
    setStep('anonymous')  // BUG: Wrong for OTP state!
  }
}, [errorType])
```

**Problem:** If network error occurs during OTP verification, clicking retry kicks user back to email entry instead of retrying OTP submission.

**Fix:** Track previous step and restore to that instead of always resetting to `anonymous`:
```typescript
const retry = useCallback(() => {
  setError(null)
  setErrorType(null)
  // Stay in current step for retry, don't reset to anonymous
}, [])
```

---

#### Bug 3: Missing AuthErrorBoundary Component

**Current State:** Test file imports `AuthErrorBoundary` but component doesn't exist.

**Fix:** Either:
1. Create `frontend/src/components/booking/AuthErrorBoundary.tsx` component
2. Or remove from tests if error boundary not needed

**Recommendation:** Skip for MVP - the new AuthStep component will handle its own errors.

---

#### Bug 4: pendingEmail Not Updated on Resend (GuestDetailsForm.tsx:386-400)

**Current Code:**
```typescript
// Set when verify button clicked
setPendingEmail(email)

// Used in resend button - but pendingEmail may be stale
const email = pendingEmail || form.getValues('email')
```

**Problem:** If user changes form email after OTP sent, resend uses old email.

**Fix:** The new AuthStep will own the email field, making this moot. No fix needed in old code.

---

### 1.3 Architecture Issues

| Issue | Description | Resolution |
|-------|-------------|------------|
| Race condition on mount | Session check races with auth events | Defer to AuthStep - simpler lifecycle |
| No resend limit tracking | Cognito limits resends (~3) but UI doesn't know | Add counter in AuthStep component |
| Email verification state | Unclear if EMAIL_OTP auto-verifies email attribute | Confirmed via Amplify docs: EMAIL_OTP verifies email |

---

## 2. shadcn/ui input-otp Component

### 2.1 Installation Status

**Status:** NOT INSTALLED

**Verified Locations:**
- `frontend/src/components/ui/` - No `input-otp.tsx` present
- `frontend/package.json` - No `input-otp` dependency

**Available UI Components (12):**
button, calendar, card, dialog, badge, alert, label, form, select, input, textarea, skeleton

### 2.2 Current OTP Implementation

**Location:** `GuestDetailsForm.tsx:404-420`

```typescript
<Input
  id="otp-code"
  type="text"
  inputMode="numeric"
  pattern="[0-9]*"
  placeholder="Enter 6-digit code"
  value={otpCode}
  onChange={(e) => setOtpCode(e.target.value)}
  disabled={step === 'verifying'}
  autoComplete="one-time-code"
/>
```

**Limitations:**
- Single text field (not 6 separate boxes per FR-008)
- No auto-advance between digits
- No visual separation
- No built-in accessibility

### 2.3 Installation Command

```bash
cd frontend
npx shadcn@latest add input-otp
```

**Expected Dependencies:** `input-otp` (will be auto-installed)

**Expected File:** `frontend/src/components/ui/input-otp.tsx`

### 2.4 Usage Pattern

```typescript
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSlot,
} from "@/components/ui/input-otp"

<InputOTP maxLength={6} value={code} onChange={setCode}>
  <InputOTPGroup>
    <InputOTPSlot index={0} />
    <InputOTPSlot index={1} />
    <InputOTPSlot index={2} />
    <InputOTPSlot index={3} />
    <InputOTPSlot index={4} />
    <InputOTPSlot index={5} />
  </InputOTPGroup>
</InputOTP>
```

---

## 3. Form Persistence Pattern

### 3.1 Current Mechanism

**Hook:** `frontend/src/hooks/useFormPersistence.ts`

**Storage:** `sessionStorage` (clears on tab close - appropriate for sensitive data)

**Key Features:**
- Generic interface with custom serialization support
- SSR-safe with `typeof window` guards
- `serializeWithDates()` / `deserializeWithDates()` for Date objects
- Returns `[value, setValue, clear]` tuple

### 3.2 Current BookingFormState

```typescript
interface BookingFormState {
  currentStep: BookingStep           // 'dates' | 'guest' | 'payment' | 'confirmation'
  selectedRange: DayPickerRange | undefined
  guestDetails: GuestDetails | null
  reservationId: string | null
  paymentAttempts: number
  lastPaymentError: string | null
  stripeSessionId: string | null
}
```

### 3.3 Proposed Extension for Auth Step

```typescript
interface BookingFormState {
  currentStep: BookingStep           // NOW: 'dates' | 'auth' | 'guest' | 'payment' | 'confirmation'
  selectedRange: DayPickerRange | undefined

  // NEW: Auth step fields
  authStep: AuthStep                 // 'anonymous' | 'sending_otp' | 'awaiting_otp' | 'verifying' | 'authenticated'
  customerName: string               // From auth form
  customerEmail: string              // Being verified
  customerPhone: string              // From auth form
  authenticatedUser: AuthenticatedUser | null

  // MODIFIED: guestDetails now excludes name/email/phone (moved to auth)
  guestDetails: {
    guestCount: number
    specialRequests?: string
  } | null

  // Existing payment fields
  reservationId: string | null
  paymentAttempts: number
  lastPaymentError: string | null
  stripeSessionId: string | null
}
```

**Changes Summary:**
1. Add `'auth'` to `BookingStep` type
2. Add auth-specific fields: `authStep`, `customerName`, `customerEmail`, `customerPhone`, `authenticatedUser`
3. Simplify `guestDetails` to exclude auth-owned fields

### 3.4 Serialization

No custom serialization needed for new fields - all are primitive types or simple objects. Continue using `serializeWithDates` / `deserializeWithDates` for the `selectedRange` field.

---

## 4. E2E Testing Strategy

### 4.1 Two-Pronged Approach (from Clarifications)

| Scenario | Strategy | Coverage |
|----------|----------|----------|
| Unauthenticated flow | Test UI up to OTP submission | Form validation, "Verify Email" triggers OTP UI |
| Authenticated bypass | Use `auth.fixture.ts` with password auth | User Story 3: skip auth step |

### 4.2 Existing Auth Fixture Capabilities

**File:** `frontend/tests/e2e/fixtures/auth.fixture.ts`

**Features:**
- SSM-stored test credentials (`/booking/e2e/test-user-*`)
- `USER_PASSWORD_AUTH` flow via Cognito SDK (not EMAIL_OTP)
- `authenticatedPage` fixture with injected JWT tokens
- `window.__MOCK_AUTH__` bypass for Amplify

**Usage:**
```typescript
import { test } from '../fixtures/auth.fixture'

test('authenticated user skips auth step', async ({ authenticatedPage }) => {
  await authenticatedPage.goto('/book')
  // Select dates, click Continue
  // Should skip auth step and go directly to guest details
})
```

### 4.3 Test File Structure

```
frontend/tests/e2e/
├── fixtures/auth.fixture.ts       # Existing
├── direct-booking.spec.ts         # Update for new step
└── auth-step.spec.ts              # NEW: Auth step specific tests
```

---

## 5. Component Architecture Decision

### 5.1 New Component: AuthStep

**Path:** `frontend/src/components/booking/AuthStep.tsx`

**Responsibilities:**
1. Collect name, email, phone
2. Initiate EMAIL_OTP flow
3. Display OTP input (6 boxes via input-otp)
4. Verify OTP and create customer profile
5. Handle all auth errors with appropriate UI

**Props:**
```typescript
interface AuthStepProps {
  defaultValues?: {
    name: string
    email: string
    phone: string
  }
  onAuthenticated: (user: AuthenticatedUser, customerProfile: Customer) => void
  onBack: () => void
  onChange?: (values: { name: string; email: string; phone: string }) => void
}
```

### 5.2 GuestDetailsForm Simplification

**Remove:**
- Email/name/phone fields (moved to AuthStep)
- All OTP-related UI and state
- `useAuthenticatedUser` integration

**Keep:**
- Guest count selector (1-4)
- Special requests textarea
- Form validation via react-hook-form

### 5.3 BookPage Step Flow Update

```
Current:  dates → guest → payment → confirmation
New:      dates → auth → guest → payment → confirmation
```

**Step indicator update:** 4 steps instead of current 4 (confirmation is implied by success page)

---

## 6. Zod Schema Design

### 6.1 New: auth-step.schema.ts

```typescript
import { z } from 'zod'

export const authStepSchema = z.object({
  name: z
    .string()
    .min(2, 'Name must be at least 2 characters')
    .max(100, 'Name must be at most 100 characters')
    .regex(/^[a-zA-ZÀ-ÿ\s'-]+$/, 'Name contains invalid characters'),

  email: z
    .string()
    .email('Please enter a valid email address'),

  phone: z
    .string()
    .min(7, 'Phone number must be at least 7 characters')
    .max(20, 'Phone number must be at most 20 characters')
    .regex(/^[+\d\s()-]+$/, 'Phone number contains invalid characters'),
})

export type AuthStepFormData = z.infer<typeof authStepSchema>

export const otpSchema = z.object({
  code: z
    .string()
    .length(6, 'Code must be 6 digits')
    .regex(/^\d{6}$/, 'Code must contain only numbers'),
})

export type OtpFormData = z.infer<typeof otpSchema>
```

### 6.2 Updated: booking-form.schema.ts

Remove `name`, `email`, `phone` from `GuestDetails`:

```typescript
export const guestDetailsSchema = z.object({
  guestCount: z
    .number()
    .min(MIN_GUESTS, `Minimum ${MIN_GUESTS} guest required`)
    .max(MAX_GUESTS, `Maximum ${MAX_GUESTS} guests allowed`),

  specialRequests: z
    .string()
    .max(MAX_SPECIAL_REQUESTS_LENGTH, `Maximum ${MAX_SPECIAL_REQUESTS_LENGTH} characters`)
    .optional(),
})
```

---

## 7. API Integration

### 7.1 Customer Creation

**Endpoint:** `POST /customers/me`

**Request:**
```json
{
  "name": "string",
  "phone": "string",
  "preferred_language": "en"
}
```

**Note:** Email comes from JWT claims (Authorization header), not request body.

**Response (201 Created or 200 OK if exists):**
```json
{
  "customer_id": "uuid",
  "email": "string",
  "name": "string",
  "phone": "string",
  "email_verified": true,
  ...
}
```

**Handle 409 Conflict:** Customer already exists - proceed without error (FR-020).

### 7.2 Generated Client Usage

```typescript
import { customersClient } from '@/lib/api'

const response = await customersClient.postCustomersMe({
  body: {
    name: formData.name,
    phone: formData.phone,
    preferred_language: 'en',
  },
  headers: {
    Authorization: `Bearer ${idToken}`,
  },
})
```

---

## 8. Implementation Priority

Based on bug severity and feature requirements:

| Priority | Task | Rationale |
|----------|------|-----------|
| P1 | Install input-otp component | Prerequisite for FR-008 |
| P1 | Create auth-step.schema.ts | Foundation for form validation |
| P1 | Create AuthStep component | Core deliverable |
| P2 | Update BookPage step flow | Integration point |
| P2 | Simplify GuestDetailsForm | Remove moved functionality |
| P3 | Fix useAuthenticatedUser bugs | May be obsoleted by new design |
| P3 | Update E2E tests | Validation after implementation |

---

## 9. Open Questions - Resolved

| Question | Resolution | Source |
|----------|------------|--------|
| How to handle existing OTP bugs? | New AuthStep replaces buggy code path | Architecture decision |
| Should useAuthenticatedUser be refactored? | Minimal fixes only; AuthStep uses it internally | YAGNI principle |
| Form field migration strategy? | Name/email/phone move to auth step; guest step keeps count/requests | Data model analysis |
| E2E testing for EMAIL_OTP on live site? | Two-pronged approach per spec clarifications | Clarification session |

---

## 10. References

- [Amplify v6 Auth Documentation](https://docs.amplify.aws/gen2/build-a-backend/auth/)
- [shadcn/ui input-otp](https://ui.shadcn.com/docs/components/input-otp)
- [Cognito EMAIL_OTP Flow](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-authentication-flow.html)
- Spec clarifications: `spec.md#clarifications`
