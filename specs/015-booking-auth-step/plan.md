# Implementation Plan: Booking Authentication Step

**Branch**: `015-booking-auth-step` | **Date**: 2025-01-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/015-booking-auth-step/spec.md`

## Summary

Add a dedicated "Verify Identity" authentication step to the booking flow between date selection and guest details. The step collects name, email, and phone number, then verifies email via Cognito EMAIL_OTP flow using Amplify. Upon successful verification, a customer profile is created via the FastAPI API. Existing broken OTP implementation will be fixed and extracted into this new dedicated step.

## Technical Context

**Language/Version**: TypeScript 5.7 (frontend), Python 3.13 (backend)
**Primary Dependencies**: Next.js 14, aws-amplify 6.15, react-hook-form 7.69, shadcn/ui, FastAPI 0.115
**Storage**: DynamoDB (via backend API), sessionStorage (form persistence via `useFormPersistence` hook)
**Testing**: Vitest + React Testing Library (unit), Playwright 1.49 (E2E)
**Target Platform**: Web browser (responsive), deployed to S3+CloudFront
**Project Type**: Web application (frontend + backend)
**Performance Goals**: OTP verification <3s, form interactions <100ms
**Constraints**: Cognito EMAIL_OTP flow only, no password-based auth, max 4 guests
**Scale/Scope**: Single property booking, ~100 bookings/month

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First Development | ✅ PASS | Tests will be written before implementation; E2E tests explicitly required in FR-019 |
| II. Simplicity & YAGNI | ✅ PASS | Extracting existing OTP code, not building new abstraction; reusing `useAuthenticatedUser` hook |
| III. Type Safety | ✅ PASS | TypeScript strict mode, Zod validation for form fields, Pydantic on backend |
| IV. Observability | ✅ PASS | Auth logging already exists in `useAuthenticatedUser` via `authLogger` |
| V. Incremental Delivery | ✅ PASS | 3 user stories with clear priorities (P1→P2→P3) |
| VI. Technology Stack | ✅ PASS | Using Amplify (existing), shadcn/ui (FR-008), generated API client (existing) |
| VI.a UI Component Development | ✅ PASS | FR-008 specifies shadcn/ui `input-otp` component (needs installation) |
| VI.b Frontend API Integration | ✅ PASS | Using existing generated client for `POST /customers/me` |

**Gate Result**: ✅ ALL PASS - Proceed to Phase 0

## Project Structure

### Documentation (this feature)

```text
specs/015-booking-auth-step/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (minimal - using existing API)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── api/src/api/
│   └── routes/customers.py    # Existing POST /customers/me endpoint
└── shared/src/shared/
    └── models/customer.py     # Customer entity

frontend/
├── src/
│   ├── app/book/page.tsx           # Main booking flow (modify)
│   ├── components/
│   │   ├── booking/
│   │   │   ├── AuthStep.tsx        # NEW: Authentication step component
│   │   │   ├── GuestDetailsForm.tsx # Simplify (remove embedded auth)
│   │   │   └── ...
│   │   └── ui/
│   │       └── input-otp.tsx       # NEW: shadcn/ui input-otp
│   ├── hooks/
│   │   ├── useAuthenticatedUser.ts # Fix bugs, enhance
│   │   └── useFormPersistence.ts   # Existing (extend state shape)
│   └── lib/
│       └── schemas/
│           └── auth-step.schema.ts # NEW: Zod schema for auth form
└── tests/
    ├── e2e/
    │   ├── direct-booking.spec.ts  # Update for new auth step
    │   └── auth-step.spec.ts       # NEW: Auth step specific tests
    └── unit/
        ├── components/booking/AuthStep.test.tsx  # NEW
        └── hooks/useAuthenticatedUser.test.ts    # Update
```

**Structure Decision**: Web application pattern with frontend/backend separation. New auth step component added to existing booking flow structure.

## Complexity Tracking

No constitution violations requiring justification.

---

## Phase 0: Research - COMPLETE ✅

**Output**: [research.md](./research.md)

**Key Findings**:
1. **OTP Bugs Identified**: 4 critical bugs in existing implementation
   - OTP code not cleared between attempts (GuestDetailsForm.tsx:75-76)
   - Retry resets to anonymous during OTP (useAuthenticatedUser.ts:370-380)
   - Missing AuthErrorBoundary component
   - pendingEmail not updated on resend (GuestDetailsForm.tsx:386-400)

2. **shadcn/ui input-otp**: NOT installed - requires `npx shadcn@latest add input-otp`

3. **Form Persistence**: `useFormPersistence` hook supports extension for auth fields

4. **E2E Testing Strategy**: Two-pronged approach
   - Unauthenticated: Test UI up to OTP submission
   - Authenticated: Use existing password auth fixture to bypass

---

## Phase 1: Design - COMPLETE ✅

### Outputs Generated

| Document | Description |
|----------|-------------|
| [data-model.md](./data-model.md) | Frontend data structures, schema definitions, state machine |
| [contracts/README.md](./contracts/README.md) | Existing API usage (no new endpoints needed) |
| [quickstart.md](./quickstart.md) | Step-by-step implementation guide |

### Key Design Decisions

1. **No Backend Changes**: Existing `POST /customers/me` endpoint fully supports requirements
2. **BookingStep Extended**: `'dates' | 'auth' | 'guest' | 'payment' | 'confirmation'`
3. **New Schema File**: `auth-step.schema.ts` for name/email/phone/OTP validation
4. **Simplified GuestDetails**: Only `guestCount` and `specialRequests` (auth fields moved)
5. **AuthStep State Machine**: Reuses `useAuthenticatedUser` hook with minimal fixes

---

## Next Steps

Run `/speckit.tasks` to generate the implementation task breakdown.
