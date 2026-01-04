# Implementation Plan: Stripe Payment Integration

**Branch**: `013-stripe-payment` | **Date**: 2026-01-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/013-stripe-payment/spec.md`

## Summary

Integrate Stripe Checkout for payment processing to replace the existing mock payment provider. The implementation adds REST API endpoints for creating Stripe Checkout sessions, processing webhooks, handling payment status queries, and processing refunds. Stripe API keys are stored securely in AWS SSM Parameter Store (SecureString). The agent is explicitly **out of scope** - this feature focuses solely on backend API endpoints.

## Technical Context

**Language/Version**: Python 3.13+ (backend only - no frontend changes required)
**Primary Dependencies**: FastAPI, stripe (Python SDK), boto3 (SSM), Pydantic v2 (strict mode)
**Storage**: DynamoDB (`booking-{env}-payments` table with GSI for reservation lookups)
**Testing**: pytest + moto (AWS mocking) + stripe-mock (Stripe API mocking)
**Target Platform**: AWS Lambda (via API Gateway REST API)
**Project Type**: web (backend API only - agent tools out of scope)
**Performance Goals**: Payment session creation <1s, webhook processing <5s (SC-007)
**Constraints**: EUR only (no currency conversion), 30-min session expiry, 24-hour availability hold
**Scale/Scope**: 50 concurrent payment sessions (SC-006)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First Development | ✅ PASS | Tests written for Stripe integration before implementation |
| II. Simplicity & YAGNI | ✅ PASS | Direct Stripe SDK usage, no custom payment abstraction |
| III. Type Safety | ✅ PASS | Pydantic v2 strict models for all Stripe-related data |
| IV. Observability | ✅ PASS | Structured logging with correlation IDs, webhook event logging |
| V. Incremental Delivery | ✅ PASS | P1→P4 priority enables incremental implementation |
| VI. Technology Stack | ✅ PASS | FastAPI, Pydantic, DynamoDB, Lambda - no new frameworks |

**Technology Stack Alignment:**
- ✅ Frontend Agent Development: N/A (agent out of scope)
- ✅ UI Component Development: N/A (no UI changes - Stripe Checkout is hosted)
- ✅ Frontend API Integration: N/A (no frontend API client changes)
- ✅ Backend Agent Development: N/A (agent tools out of scope per spec)
- ✅ Infrastructure: Uses terraform-aws-modules patterns, SSM Parameter Store

## Project Structure

### Documentation (this feature)

```text
specs/013-stripe-payment/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── checkout-session.yaml
│   ├── payment-status.yaml
│   ├── payment-retry.yaml
│   ├── refund.yaml
│   └── webhook.yaml
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── shared/src/shared/
│   ├── models/
│   │   ├── payment.py           # MODIFY: Add Stripe-specific fields
│   │   └── stripe_webhook.py    # NEW: StripeWebhookEvent model
│   └── services/
│       ├── payment_service.py   # MODIFY: Add StripePaymentProvider
│       └── ssm_service.py       # NEW: SSM Parameter Store retrieval
├── api/src/api/
│   ├── routes/
│   │   ├── payments.py          # MODIFY: Add checkout-session, refund endpoints
│   │   └── webhooks.py          # NEW: Stripe webhook handler
│   └── models/
│       └── payments.py          # MODIFY: Add Stripe request/response models
└── tests/
    ├── unit/
    │   ├── test_stripe_service.py     # NEW: Stripe service unit tests
    │   └── test_stripe_webhooks.py    # NEW: Webhook handler tests
    └── integration/
        └── test_payment_flow.py       # NEW: End-to-end payment flow tests

infrastructure/
└── modules/gateway-v2/
    └── main.tf                        # MODIFY: Add SSM read permissions
```

**Structure Decision**: Web application structure (Option 2) - backend-only changes. This feature modifies existing payment routes and services, adds webhook handling, and extends infrastructure for SSM access. No frontend code changes required since Stripe Checkout provides the hosted payment UI.

## Complexity Tracking

> **No violations - Constitution Check passed without exceptions**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *None* | — | — |
