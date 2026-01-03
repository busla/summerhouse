# Implementation Plan: Amplify Authentication Refactor

**Branch**: `010-amplify-auth-refactor` | **Date**: 2026-01-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/010-amplify-auth-refactor/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Consolidate three overlapping authentication implementations (specs 003, 004, 005) into a single, simple architecture where:
- **Frontend (Amplify)** handles all authentication UI and token management via EMAIL_OTP
- **API Gateway** validates JWT tokens using Cognito authorizer (already configured)
- **Backend (FastAPI)** trusts API Gateway validation, extracts `sub` claim for customer identity

**Key Constraint**: Agent code SHALL NOT be modified (out of scope for future rewrite).

## Technical Context

**Language/Version**: TypeScript 5.x strict mode (frontend), Python 3.13+ (backend)
**Primary Dependencies**: AWS Amplify v6 (@aws-amplify/auth, @aws-amplify/ui-react), FastAPI, Pydantic v2, boto3
**Storage**: DynamoDB (`booking-{env}-guests` table with `cognito_sub` as identifier)
**Testing**: Vitest + Playwright (frontend), pytest + moto (backend)
**Target Platform**: Web (Next.js 14+ static export via S3/CloudFront, FastAPI on Lambda)
**Project Type**: Web application (frontend + backend)
**Performance Goals**: OTP delivery <30s (95%), session load <500ms, auth overhead <100ms
**Constraints**: EMAIL_OTP only (passwordless), max 3 OTP attempts, 5-minute expiration
**Scale/Scope**: Single property booking, refactoring existing flows

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Test-First Development | ✅ PASS | Unit tests for auth hooks, integration tests for OTP flow |
| Simplicity & YAGNI | ✅ PASS | Consolidating 3 implementations into 1; removing unused AgentCore patterns |
| Type Safety | ✅ PASS | Strict TypeScript, Pydantic strict mode |
| Observability | ✅ PASS | Structured logging for auth events, correlation IDs |
| Incremental Delivery | ✅ PASS | Can deploy frontend auth changes independently |
| Technology Stack | ✅ PASS | Using Amplify v6, existing Cognito infra, FastAPI |
| ai-elements Gate | ⬜ N/A | No AI chat components in this feature |
| Strands Agent Gate | ⬜ N/A | Agent code explicitly out of scope |

**All gates pass. Proceeding to Phase 0.**

## Project Structure

### Documentation (this feature)

```text
specs/010-amplify-auth-refactor/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
# Web application structure (frontend + backend)
backend/
├── shared/src/shared/
│   ├── models/
│   │   └── customer.py       # Customer model with cognito_sub
│   └── services/
│       └── customer.py       # Customer CRUD by cognito_sub
├── api/src/api/
│   ├── routes/
│   │   └── customers.py      # GET/PUT customer by sub claim
│   └── middleware/
│       └── auth.py           # Extract sub claim from JWT
└── tests/
    ├── unit/
    │   └── test_customer_service.py
    └── integration/
        └── test_customer_routes.py

frontend/
├── src/
│   ├── components/
│   │   └── booking/
│   │       └── GuestDetailsForm.tsx  # Modified: auth-aware form
│   ├── lib/
│   │   └── auth.ts           # Existing: already has Amplify utilities
│   └── hooks/
│       └── useAuthenticatedUser.ts   # New: hook for auth state in forms
└── tests/
    ├── unit/
    │   └── GuestDetailsForm.test.tsx
    └── e2e/
        └── auth-flow.spec.ts
```

**Structure Decision**: Web application pattern with existing frontend/backend separation. Frontend modifications focus on `GuestDetailsForm.tsx` and hooks. Backend adds customer service layer. No infrastructure changes needed - Cognito already configured with EMAIL_OTP.

## Complexity Tracking

> **No violations to justify** - This feature simplifies the codebase by removing complexity.

| Simplification | Previous State | New State |
|----------------|----------------|-----------|
| Auth implementations | 3 overlapping (003, 004, 005) | 1 unified |
| Agent auth code | Complex OAuth2/JWT delivery | Removed (out of scope) |
| Session management | DynamoDB + localStorage + AgentCore vault | Amplify-managed only |
| JWT validation | Backend PyJWT verification | API Gateway handles it |

## Phase 0: Research

### Research Questions

1. **Amplify v6 EMAIL_OTP API**: What is the exact API for `signUp`, `signIn`, `confirmSignIn` with EMAIL_OTP in Amplify v6?
2. **JWT Claims Access**: How does FastAPI extract JWT claims when API Gateway has already validated the token?
3. **Cognito Sub Format**: What is the format of the `sub` claim from Cognito? (UUID format confirmation)
4. **Session Refresh**: How does Amplify handle token refresh automatically?
5. **Error Handling**: What errors does Amplify throw for invalid OTP, expired OTP, rate limiting?

### Existing Code Analysis

**Frontend (`frontend/src/lib/auth.ts`)** - Already implemented:
- `useAuth()` hook provides `isAuthenticated`, `email`, `userId`
- `ensureValidIdToken()` retrieves ID token from session
- Uses `fetchAuthSession()` and `getCurrentUser()` from Amplify

**Infrastructure (`infrastructure/modules/cognito-passwordless/main.tf`)** - Already configured:
- Cognito User Pool with ESSENTIALS tier (required for native EMAIL_OTP)
- `allowed_first_auth_factors = ["PASSWORD", "EMAIL_OTP"]`
- Public client for frontend/Amplify with ALLOW_USER_AUTH flow
- Identity Pool for IAM-based auth

**Backend** - Needs implementation:
- No customer service exists that queries by `cognito_sub`
- No middleware extracts `sub` claim from JWT headers
- Guests table exists but uses `guest_id`, not `cognito_sub`

## Phase 1: Design Artifacts

### Data Model Changes

See `data-model.md` for:
- Customer entity with `cognito_sub` as primary identifier
- Mapping between Cognito user and DynamoDB customer record
- Session state (managed by Amplify, not stored in application)

### API Contracts

See `contracts/` for:
- `GET /api/customers/me` - Get current customer by JWT sub claim
- `PUT /api/customers/me` - Update current customer profile

### Quickstart Guide

See `quickstart.md` for:
- Frontend: Modifying GuestDetailsForm for auth-aware behavior
- Backend: Adding customer service and routes
- Testing: Auth flow E2E tests
