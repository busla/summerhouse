# Data Model: Booking Authentication Step

**Feature Branch**: `015-booking-auth-step`
**Date**: 2025-01-05
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Overview

This feature introduces a dedicated authentication step in the booking flow. Data model changes are primarily in the **frontend** - the backend `Customer` entity already supports all required fields.

---

## 1. Backend Entities (No Changes)

### 1.1 Customer (Existing)

**Location:** `backend/shared/src/shared/models/customer.py`

The existing `Customer` model fully supports this feature:

| Field | Type | Description | Used By Auth Step |
|-------|------|-------------|-------------------|
| `customer_id` | `str` (UUID) | Primary key | ✅ Returned after creation |
| `email` | `EmailStr` | Verified email | ✅ From JWT claims |
| `cognito_sub` | `str \| None` | Cognito user ID | ✅ Auto-set by API |
| `name` | `str \| None` | Full name | ✅ From auth form |
| `phone` | `str \| None` | Phone number | ✅ From auth form |
| `preferred_language` | `str` | `en` or `es` | ✅ Default `en` |
| `email_verified` | `bool` | Verification status | ✅ Set true by API |
| `first_verified_at` | `datetime \| None` | First verification | ✅ Set by API |
| `total_bookings` | `int` | Booking count | N/A |
| `created_at` | `datetime` | Creation time | N/A |
| `updated_at` | `datetime` | Update time | N/A |

**API Endpoint:** `POST /customers/me`
- Creates customer with authenticated user's email (from JWT)
- Returns existing customer if already exists (idempotent)
- Sets `email_verified=true` and `first_verified_at=now()`

---

## 2. Frontend Data Structures

### 2.1 BookingFormState (Modified)

**Location:** `frontend/src/app/book/page.tsx`

**Current:**
```typescript
type BookingStep = 'dates' | 'guest' | 'payment' | 'confirmation'

interface BookingFormState {
  currentStep: BookingStep
  selectedRange: DayPickerRange | undefined
  guestDetails: GuestDetails | null
  reservationId: string | null
  paymentAttempts: number
  lastPaymentError: string | null
  stripeSessionId: string | null
}
```

**New (with auth step):**
```typescript
type BookingStep = 'dates' | 'auth' | 'guest' | 'payment' | 'confirmation'

interface BookingFormState {
  currentStep: BookingStep
  selectedRange: DayPickerRange | undefined

  // NEW: Auth step fields (persisted)
  customerName: string
  customerEmail: string
  customerPhone: string
  authStep: AuthStep
  customerId: string | null  // After customer created

  // SIMPLIFIED: Guest step only needs count + requests
  guestDetails: SimplifiedGuestDetails | null

  // Payment fields (unchanged)
  reservationId: string | null
  paymentAttempts: number
  lastPaymentError: string | null
  stripeSessionId: string | null
}
```

### 2.2 AuthStep State Machine

**Location:** `frontend/src/hooks/useAuthenticatedUser.ts` (existing)

```typescript
type AuthStep =
  | 'anonymous'      // Initial: show name/email/phone form
  | 'sending_otp'    // OTP being sent (loading state)
  | 'awaiting_otp'   // Show OTP input
  | 'verifying'      // Verifying OTP (loading state)
  | 'authenticated'  // Success: proceed to next step
```

**State Transitions:**
```
anonymous → [Click "Verify Email"] → sending_otp
sending_otp → [OTP sent] → awaiting_otp
sending_otp → [Error] → anonymous (with error)
awaiting_otp → [Enter code + click "Confirm"] → verifying
verifying → [Success] → authenticated
verifying → [Wrong code] → awaiting_otp (with error)
awaiting_otp → [Click "Resend"] → sending_otp
```

### 2.3 SimplifiedGuestDetails (New)

**Location:** `frontend/src/lib/schemas/booking-form.schema.ts`

After moving name/email/phone to auth step:

```typescript
interface SimplifiedGuestDetails {
  guestCount: number       // 1-4 guests
  specialRequests?: string // Optional, max 500 chars
}
```

### 2.4 AuthStepFormData (New)

**Location:** `frontend/src/lib/schemas/auth-step.schema.ts` (new file)

```typescript
interface AuthStepFormData {
  name: string   // 2-100 chars, letters/spaces/accents
  email: string  // Valid email format
  phone: string  // 7-20 chars, digits/spaces/+/-/()
}

interface OtpFormData {
  code: string   // Exactly 6 digits
}
```

### 2.5 AuthenticatedUser (Existing)

**Location:** `frontend/src/hooks/useAuthenticatedUser.ts`

```typescript
interface AuthenticatedUser {
  email: string  // From Cognito ID token
  name?: string  // From Cognito ID token (if set)
  sub: string    // Cognito user pool subject ID
}
```

---

## 3. Schema Definitions

### 3.1 auth-step.schema.ts (New File)

```typescript
import { z } from 'zod'

// Form validation for auth step fields
export const authStepSchema = z.object({
  name: z
    .string()
    .min(2, 'Name must be at least 2 characters')
    .max(100, 'Name must be at most 100 characters')
    .regex(/^[a-zA-ZÀ-ÿ\s'-]+$/, 'Name contains invalid characters'),

  email: z
    .string()
    .email('Please enter a valid email address')
    .max(255, 'Email must be less than 255 characters'),

  phone: z
    .string()
    .min(7, 'Phone number must be at least 7 characters')
    .max(20, 'Phone number must be at most 20 characters')
    .regex(/^[+\d\s()-]+$/, 'Phone number contains invalid characters'),
})

// OTP code validation
export const otpSchema = z.object({
  code: z
    .string()
    .length(6, 'Code must be 6 digits')
    .regex(/^\d{6}$/, 'Code must contain only numbers'),
})

// Type exports
export type AuthStepFormData = z.infer<typeof authStepSchema>
export type OtpFormData = z.infer<typeof otpSchema>
```

### 3.2 booking-form.schema.ts (Modified)

**Changes:**
1. Add `simplifiedGuestDetailsSchema` for guest step
2. Keep existing `guestDetailsSchema` for backward compatibility (reservation creation still needs all fields)

```typescript
// NEW: Simplified schema for guest step (post-auth)
export const simplifiedGuestDetailsSchema = z.object({
  guestCount: z
    .number()
    .int('Guest count must be a whole number')
    .min(MIN_GUESTS, `At least ${MIN_GUESTS} guest required`)
    .max(MAX_GUESTS, `Maximum ${MAX_GUESTS} guests allowed`),

  specialRequests: z
    .string()
    .max(500, 'Special requests must be less than 500 characters')
    .optional(),
})

export type SimplifiedGuestDetails = z.infer<typeof simplifiedGuestDetailsSchema>
```

---

## 4. Storage Strategy

### 4.1 Session Storage (Form Persistence)

**Key:** `booking-form-state`

**What's Persisted:**
- `currentStep` - Resume at correct step after refresh
- `selectedRange` - Check-in/check-out dates
- `customerName`, `customerEmail`, `customerPhone` - Auth form values
- `authStep` - Auth state (anonymous/awaiting_otp/authenticated)
- `customerId` - After customer profile created
- `guestDetails` - Guest count and special requests
- `reservationId`, `paymentAttempts`, etc. - Payment state

**Serialization:**
- Use `serializeWithDates` / `deserializeWithDates` for `selectedRange`
- Standard JSON for all other fields

**Lifecycle:**
- Created when user first enters booking flow
- Updated on every form change
- Cleared on successful payment (by success page)
- Automatically clears on tab close (sessionStorage)

### 4.2 Cognito Token Storage

**Managed by:** Amplify v6 (automatic)

**Location:** `localStorage` with key pattern:
```
CognitoIdentityServiceProvider.{clientId}.{username}.idToken
CognitoIdentityServiceProvider.{clientId}.{username}.accessToken
CognitoIdentityServiceProvider.{clientId}.{username}.refreshToken
CognitoIdentityServiceProvider.{clientId}.LastAuthUser
```

**Note:** The `window.__MOCK_AUTH__` bypass is only for E2E tests.

---

## 5. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           BookPage                                   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              BookingFormState (sessionStorage)                │   │
│  │  currentStep: 'dates' | 'auth' | 'guest' | 'payment'         │   │
│  │  selectedRange: { from: Date, to: Date }                     │   │
│  │  customerName: string                                         │   │
│  │  customerEmail: string                                        │   │
│  │  customerPhone: string                                        │   │
│  │  authStep: AuthStep                                           │   │
│  │  customerId: string | null                                    │   │
│  │  guestDetails: { guestCount, specialRequests }               │   │
│  │  reservationId: string | null                                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
     ┌────────────────────┼────────────────────┐
     │                    │                    │
     ▼                    ▼                    ▼
┌──────────┐      ┌─────────────┐      ┌─────────────┐
│DatePicker│      │  AuthStep   │      │GuestDetails │
│          │      │             │      │   Form      │
│selectedRange    │name, email, │      │             │
│          │      │phone, OTP   │      │guestCount,  │
└──────────┘      │             │      │specialReqs  │
                  │  ↓          │      └─────────────┘
                  │ Cognito     │
                  │ EMAIL_OTP   │
                  │  ↓          │
                  │ POST        │
                  │ /customers  │
                  │ /me         │
                  └─────────────┘
                        │
                        ▼
              ┌─────────────────┐
              │   DynamoDB      │
              │   customers     │
              │   table         │
              └─────────────────┘
```

---

## 6. Entity Relationships

```
┌─────────────────┐         ┌─────────────────┐
│    Customer     │         │   Reservation   │
├─────────────────┤         ├─────────────────┤
│ customer_id (PK)│◄────────│ customer_id (FK)│
│ email           │         │ reservation_id  │
│ cognito_sub     │         │ check_in        │
│ name            │         │ check_out       │
│ phone           │         │ status          │
│ email_verified  │         │ ...             │
└─────────────────┘         └─────────────────┘
        │
        │ 1:N
        ▼
┌─────────────────┐
│ Cognito User    │
├─────────────────┤
│ sub (PK)        │
│ email           │
│ email_verified  │
│ ...             │
└─────────────────┘
```

**Notes:**
- Customer `cognito_sub` links to Cognito user pool
- Customer `customer_id` links to reservations
- Backend API creates this linkage when `POST /customers/me` is called

---

## 7. Validation Rules

### 7.1 Auth Step Form

| Field | Rule | Error Message |
|-------|------|---------------|
| name | Required, 2-100 chars | "Name must be at least 2 characters" |
| name | Pattern: `[a-zA-ZÀ-ÿ\s'-]+` | "Name contains invalid characters" |
| email | Required, valid email | "Please enter a valid email address" |
| phone | Required, 7-20 chars | "Phone number must be at least 7 characters" |
| phone | Pattern: `[+\d\s()-]+` | "Phone number contains invalid characters" |

### 7.2 OTP Input

| Field | Rule | Error Message |
|-------|------|---------------|
| code | Exactly 6 chars | "Code must be 6 digits" |
| code | Pattern: `\d{6}` | "Code must contain only numbers" |

### 7.3 Guest Details (Simplified)

| Field | Rule | Error Message |
|-------|------|---------------|
| guestCount | Integer 1-4 | "Maximum 4 guests allowed" |
| specialRequests | Max 500 chars, optional | "Special requests must be less than 500 characters" |

---

## 8. Error Categorization

**Location:** `useAuthenticatedUser.ts` (existing)

```typescript
type ErrorType = 'network' | 'auth' | 'validation' | 'rate_limit' | null
```

| Type | Trigger | User Message | Recovery Action |
|------|---------|--------------|-----------------|
| `network` | API/Cognito timeout | "Connection error. Please check your internet." | "Retry" button |
| `auth` | Invalid OTP, expired session | "Invalid code. Please try again." | Stay on OTP input |
| `validation` | Malformed input | Field-specific error | Fix input |
| `rate_limit` | Too many attempts | "Too many attempts. Please wait." | Disabled state + timer |

---

## 9. Migration Notes

### 9.1 Form State Migration

When user refreshes page with old `BookingFormState` shape:

1. Check if `currentStep` is `'guest'` (old flow)
2. If `guestDetails` contains `name`, `email`, `phone` → migrate to new shape
3. Set `customerName`, `customerEmail`, `customerPhone` from migrated values
4. Set `authStep` based on whether user was authenticated

**Implementation:** Handle in `deserializeWithDates` or with version field.

### 9.2 Backward Compatibility

- Old sessions without auth data → start from dates step
- No data loss - just restart flow with new structure
- Existing reservations unaffected

---

## 10. Test Data

### 10.1 Valid Auth Form Data

```typescript
const validAuthData = {
  name: "María García-López",
  email: "maria@example.com",
  phone: "+34 612 345 678",
}
```

### 10.2 Valid OTP

```typescript
const validOtp = { code: "123456" }
```

### 10.3 Valid Guest Details (Simplified)

```typescript
const validGuestDetails = {
  guestCount: 2,
  specialRequests: "Late check-in around 10pm please",
}
```

### 10.4 E2E Test User

**Credentials stored in SSM:**
- `/booking/e2e/test-user-email` → Test user email
- `/booking/e2e/test-user-password` → Test user password (SecureString)

**Auth method:** `USER_PASSWORD_AUTH` (not EMAIL_OTP) for automated tests
