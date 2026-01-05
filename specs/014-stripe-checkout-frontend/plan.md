# Implementation Plan: Stripe Checkout Frontend Integration

**Branch**: `014-stripe-checkout-frontend` | **Date**: 2026-01-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/014-stripe-checkout-frontend/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Implement the complete frontend checkout and payment flow by integrating with the existing Stripe payment backend (013-stripe-payment). The feature adds a payment step to the existing booking flow, redirects users to Stripe Checkout, and handles success/cancel return URLs with appropriate confirmation and retry UI.

## Technical Context

**Language/Version**: TypeScript 5.x (strict mode)
**Primary Dependencies**: Next.js 14+ (App Router), React, @hey-api/openapi-ts (generated client), shadcn/ui, Playwright
**Storage**: sessionStorage (form state persistence during Stripe redirect)
**Testing**: Vitest (unit), Playwright (E2E with real Stripe test mode)
**Target Platform**: Web (static export via S3 + CloudFront), mobile responsive (375px+)
**Project Type**: Web application (frontend only - backend already complete)
**Performance Goals**: Payment flow completion under 4 minutes, 95% successful Stripe redirects
**Constraints**: Must use generated API client (not custom fetch), must use shadcn/ui components
**Scale/Scope**: Single property booking, EUR currency only, max 3 payment retries

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First Development | ✅ PASS | E2E Playwright tests required (FR-022 to FR-026) |
| II. Simplicity & YAGNI | ✅ PASS | Using Stripe Checkout (hosted) - no custom payment UI |
| III. Type Safety | ✅ PASS | Generated API client provides type-safe models |
| VI. Technology Stack - UI Components | ✅ PASS | Will use shadcn/ui for all components |
| VI. Technology Stack - Frontend API Integration | ⚠️ NEEDS RESEARCH | Generated SDK missing `checkout-session` endpoint - verify OpenAPI spec and regeneration |

## Project Structure

### Documentation (this feature)

```text
specs/014-stripe-checkout-frontend/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── app/
│   │   ├── book/
│   │   │   └── page.tsx           # Enhanced with payment step
│   │   └── booking/
│   │       ├── success/
│   │       │   └── page.tsx       # NEW: Payment success handler
│   │       └── cancel/
│   │           └── page.tsx       # NEW: Payment cancel handler
│   ├── components/
│   │   └── booking/
│   │       ├── PaymentStep.tsx    # NEW: Payment initiation UI
│   │       ├── PaymentStatus.tsx  # NEW: Status badge component
│   │       └── BookingConfirmation.tsx  # Enhanced with payment details
│   ├── hooks/
│   │   └── useCheckoutSession.ts  # NEW: Stripe Checkout session hook
│   └── lib/
│       └── api-client/            # Regenerated with checkout-session endpoint
└── tests/
    └── e2e/
        └── checkout-flow.spec.ts  # NEW: Playwright E2E tests
```

**Structure Decision**: Frontend-only feature extending existing `/book` page with payment step and new `/booking/success` and `/booking/cancel` routes (matching backend-defined URLs).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |

## Key Discoveries

### Route URL Discrepancy
The spec (spec.md) lists routes as `/book/success` and `/book/cancel`, but the backend (payments.py:68-69) defines:
- Success: `${FRONTEND_URL}/booking/success?session_id={CHECKOUT_SESSION_ID}`
- Cancel: `${FRONTEND_URL}/booking/cancel`

**Resolution**: Use backend-defined routes (`/booking/*`) since Stripe will redirect to these URLs.

### SDK Regeneration Required
The generated TypeScript API client (`frontend/src/lib/api-client/sdk.gen.ts`) is missing the `checkout-session` endpoint. The backend has:
- `POST /payments/checkout-session` - Creates Stripe Checkout session
- `GET /payments/{reservation_id}` - Gets payment status
- `GET /payments/{reservation_id}/history` - Full payment history
- `POST /payments/{reservation_id}/retry` - Retry failed payment

**Resolution**: Regenerate SDK from OpenAPI spec before implementation.

### Existing Booking Flow
Current `/book` page has 3 steps: dates → guest → confirmation. This needs to become 4 steps: dates → guest → **payment** → confirmation. The current flow creates a confirmed reservation immediately - new flow creates a pending reservation, redirects to Stripe, then confirms upon successful payment webhook.
