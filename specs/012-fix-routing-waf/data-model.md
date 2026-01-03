# Data Model: Fix Next.js Routing and WAF 403 Errors

**Feature Branch**: `012-fix-routing-waf`
**Created**: 2026-01-03
**Status**: Draft

## Overview

This feature requires minimal new data modeling. The form persistence uses existing Zod schemas from `booking-form.schema.ts`. This document defines the sessionStorage state shape.

## Form Persistence State

### Storage Key

```
booking-form-state
```

### State Shape

```typescript
/**
 * Persisted booking form state in sessionStorage.
 * Reuses existing types from booking-form.schema.ts.
 */
interface PersistedBookingFormState {
  /** Step 1: Selected date range */
  dates?: {
    from: string  // ISO 8601 date string (e.g., "2026-02-15")
    to: string    // ISO 8601 date string (e.g., "2026-02-20")
  }

  /** Step 2: Guest details (partial - user may be mid-form) */
  guestDetails?: Partial<{
    name: string
    email: string
    phone: string
    guestCount: number
    specialRequests: string
  }>

  /** Current step for resuming flow */
  currentStep: 'dates' | 'guest' | 'confirmation'
}
```

### Serialization Format

**Storage**: Browser sessionStorage (cleared when tab closes)
**Format**: JSON string

**Date Handling**: Dates are stored as ISO strings, not Date objects, because:
1. `JSON.stringify` converts Dates to strings automatically
2. Explicit ISO format ensures consistent parsing on restore
3. Avoids timezone issues with `toLocaleDateString()`

**Example Stored Value**:

```json
{
  "dates": {
    "from": "2026-02-15",
    "to": "2026-02-20"
  },
  "guestDetails": {
    "name": "John Smith",
    "email": "john@example.com",
    "guestCount": 2
  },
  "currentStep": "guest"
}
```

## Lifecycle

| Event | Action |
|-------|--------|
| User selects dates | Store dates + set step to 'dates' |
| User fills guest form | Store partial guest details as they type |
| User navigates between steps | Update currentStep |
| Booking submitted successfully | Clear entire storage key |
| User clicks "Start New Booking" | Clear entire storage key |
| Tab/window closes | Auto-cleared (sessionStorage behavior) |

## Existing Types Used

This feature reuses types from `frontend/src/lib/schemas/booking-form.schema.ts`:

- `GuestDetails` - Guest form fields (name, email, phone, guestCount, specialRequests)
- `DateRange` - Check-in/check-out dates (but stored as ISO strings, not Date objects)

## No API Changes

This feature does not modify any API contracts. All persistence is client-side only.

## No Database Changes

This feature does not modify any DynamoDB tables. The form persistence is browser-side only.
