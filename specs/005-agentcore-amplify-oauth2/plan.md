# Implementation Plan: AgentCore Identity OAuth2 with Amplify EMAIL_OTP

**Branch**: `005-agentcore-amplify-oauth2` | **Date**: 2025-12-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-agentcore-amplify-oauth2/spec.md`

## Summary

Replace agent-initiated EMAIL_OTP authentication (spec 004) with the standard AgentCore Identity OAuth2 flow. When a user attempts to make a reservation, the agent tool decorated with `@requires_access_token` triggers AgentCore to return an authorization URL. The user authenticates on a custom Amplify Authenticator page (EMAIL_OTP only), then a callback page completes session binding via `CompleteResourceTokenAuth`.

**Key architectural shift**: Moving from agent-initiated (backend calls `AdminInitiateAuth`) to user-initiated OAuth2 (user clicks authorization URL, authenticates on Amplify page).

## Technical Context

**Language/Version**: Python 3.13+ (backend), TypeScript 5.x strict mode (frontend)
**Primary Dependencies**:
  - Backend: `strands-agents`, `bedrock-agentcore` (Identity SDK with `@requires_access_token`), `boto3`
  - Frontend: `@aws-amplify/ui-react`, `@aws-amplify/auth`, `@aws-sdk/client-bedrock-agentcore`
**Storage**: N/A (AgentCore Identity manages token vault; Cognito manages users)
**Testing**: pytest (backend), Vitest (frontend unit), Playwright (E2E)
**Target Platform**: AWS (AgentCore Runtime, Cognito, S3+CloudFront static site)
**Project Type**: Web application (frontend + backend)
**Performance Goals**: OAuth2 flow completion < 2 minutes (excluding email delivery), session binding success rate > 99%
**Constraints**: Authorization URLs expire in 10 minutes, OTP delivery within 60 seconds
**Scale/Scope**: Single property booking platform, ~100 concurrent users

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First Development | ✅ PASS | Tests will be written before implementation |
| II. Simplicity & YAGNI | ✅ PASS | OAuth2 flow is the standard AgentCore pattern; no custom auth mechanisms |
| III. Type Safety | ✅ PASS | Strict TypeScript + Python type hints enforced |
| IV. Observability | ✅ PASS | Will use structured logging for auth events |
| V. Incremental Delivery | ✅ PASS | Phased: Infrastructure → Backend → Frontend → Callback |
| VI. Technology Stack - Frontend | ✅ PASS | Uses Vercel AI SDK, will check ai-elements for UI components |
| VI. Technology Stack - Backend | ✅ PASS | Uses Strands agent framework with `@requires_access_token` |
| VI. Technology Stack - Infrastructure | ✅ PASS | Uses `terraform-aws-agentcore` module for OAuth2 providers |
| VI. UI Component Research | ✅ PASS | research.md confirms ai-elements not applicable (auth UX, not AI chat); using Amplify UI instead |

**Pre-Design Gate**: PASS (all checks complete)

## Project Structure

### Documentation (this feature)

```text
specs/005-agentcore-amplify-oauth2/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── auth-callback.md # CompleteResourceTokenAuth API contract
│   └── tool-responses.md # Updated @requires_access_token responses
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── agent/
│   │   └── prompts/           # System prompt updates for OAuth2 flow
│   ├── tools/
│   │   ├── auth.py            # Remove agent-initiated auth tools (initiate_cognito_login, verify_cognito_otp)
│   │   └── reservation.py     # Add @requires_access_token decorator
│   ├── models/
│   │   └── auth.py            # Update auth models for OAuth2 flow
│   └── services/
│       └── auth_service.py    # Remove AdminInitiateAuth code
└── tests/
    ├── unit/
    │   └── tools/
    │       └── test_reservation_auth.py
    └── integration/

frontend/
├── src/
│   ├── app/
│   │   ├── auth/
│   │   │   └── callback/
│   │   │       └── page.tsx   # NEW: OAuth2 callback page
│   │   └── login/
│   │       └── page.tsx       # NEW: Amplify EMAIL_OTP auth page
│   ├── components/
│   │   └── auth/
│   │       └── AuthCallback.tsx # CompleteResourceTokenAuth client component
│   └── lib/
│       ├── amplify-config.ts  # Amplify Auth configuration (EMAIL_OTP only)
│       └── agentcore-auth.ts  # CompleteResourceTokenAuth SDK wrapper
└── tests/
    ├── unit/
    │   └── lib/
    │       └── agentcore-auth.test.ts
    └── e2e/
        └── oauth-flow.spec.ts

infrastructure/
├── main.tf                    # Add OAuth2 credential provider + workload identity
└── modules/
    └── (uses terraform-aws-agentcore identity module)
```

**Structure Decision**: Web application pattern. Backend updates agent tools to use `@requires_access_token`. Frontend adds new `/auth/callback` route for session binding and `/login` route for Amplify EMAIL_OTP authentication page.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |

No constitution violations. The OAuth2 flow is the standard AgentCore pattern and aligns with all constitution principles.

## Phase Dependencies

```text
Phase 0: Research
├── AgentCore Identity @requires_access_token patterns
├── Amplify EMAIL_OTP Hosted UI configuration
├── CompleteResourceTokenAuth SDK usage
└── ai-elements UI component catalogue research

Phase 1: Design & Contracts
├── data-model.md (OAuth2 entities: CredentialProvider, WorkloadIdentity, AuthorizationSession)
├── contracts/ (tool responses, callback API)
└── quickstart.md (local development setup)

Phase 2: Tasks (/speckit.tasks)
└── Implementation tasks with dependencies
```

## Key Implementation Decisions

### 1. OAuth2 Flow Architecture

```text
User → Agent → Protected Tool (@requires_access_token)
                    ↓
              No token? → AgentCore returns auth URL via on_auth_url callback
                    ↓
              Agent streams URL to user
                    ↓
User clicks URL → Custom Amplify Authenticator (EMAIL_OTP only)
                    ↓
              User enters email → Receives OTP → Confirms
                    ↓
              Amplify stores tokens → Redirects to callback URL
                    ↓
Callback page → Extracts session_uri from URL
                    ↓
              Calls CompleteResourceTokenAuth(session_uri, cognito_token)
                    ↓
              AgentCore binds session → Redirects to chat
                    ↓
User continues chat → Agent tool now has valid token
```

### 2. Cognito Configuration Changes

- Current: `AdminInitiateAuth` with `EMAIL_OTP` challenge (agent-initiated)
- New: Custom Amplify Authenticator with `USER_AUTH` flow, `EMAIL_OTP` as preferred challenge (user-initiated)
- User Pool Client needs: callback URLs, `ALLOW_USER_AUTH` flow (no Hosted UI domain required)

### 3. Code Removal (Simplification)

The following will be REMOVED as they're incompatible with OAuth2 flow:
- `backend/src/tools/auth.py`: `initiate_cognito_login`, `verify_cognito_otp` tools
- `backend/src/services/auth_service.py`: `AdminInitiateAuth` related code
- Frontend token storage via SSE stream (replaced by Amplify storage + AgentCore vault)

### 4. New Components

| Component | Location | Purpose |
|-----------|----------|---------|
| OAuth2 Credential Provider | Terraform | Stores Cognito client credentials + discovery URL |
| Workload Identity | Terraform | Allowed callback URLs for session binding |
| Auth callback page | `/app/auth/callback/page.tsx` | Calls `CompleteResourceTokenAuth` |
| Login page | `/app/login/page.tsx` | Amplify EMAIL_OTP UI |
| `@requires_access_token` decorator | `backend/src/tools/reservation.py` | Triggers OAuth2 flow on protected tools |

## Research Questions (Phase 0)

1. **Amplify EMAIL_OTP Configuration**: How to configure Amplify UI to show ONLY email input + OTP (no username/password)?
2. **Cognito Hosted UI Customization**: Can Hosted UI be configured for EMAIL_OTP-only, or do we need custom Amplify UI?
3. **CompleteResourceTokenAuth SDK**: Exact parameters and error handling for `@aws-sdk/client-bedrock-agentcore`
4. **Session URI Format**: How is `session_uri` passed in the authorization URL? (query param vs state)
5. **ai-elements Catalogue**: Does ai-elements have authentication/OTP components we should use?
