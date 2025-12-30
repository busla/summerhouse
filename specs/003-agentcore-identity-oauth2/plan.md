# Implementation Plan: AgentCore Identity OAuth2 Login

**Branch**: `003-agentcore-identity-oauth2` | **Date**: 2025-12-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-agentcore-identity-oauth2/spec.md`

## Summary

Implement passwordless authentication using AWS Cognito EMAIL_OTP flow integrated with AgentCore Identity for the Strands booking agent. The agent will authenticate guests via email-based one-time passwords, with OAuth2 user identity verification via AgentCore's two-stage callback flow. Frontend uses `@aws-amplify/ui-react` Authenticator component for the OTP UI experience.

**Key Architecture**: AgentCore handles OAuth2 complexity (PKCE, state, code exchange) internally. The application only tracks `session_id` ↔ `guest_email` mapping to verify user identity via `CompleteResourceTokenAuth`.

## Technical Context

**Language/Version**: Python 3.13+ (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: bedrock-agentcore, boto3, strands-agents, pyjwt, @aws-amplify/ui-react, @aws-amplify/auth
**Storage**: DynamoDB (OAuth2 sessions table with TTL), AWS Cognito (user identity)
**Testing**: pytest with moto for Cognito mocking, Vitest for frontend
**Target Platform**: AWS AgentCore Runtime (backend), S3 + CloudFront (frontend)
**Project Type**: Web application (frontend + backend)
**Performance Goals**: OTP delivery <60s (95th percentile), OAuth2 callback <2s, authentication flow <90s total
**Constraints**: Cognito Essentials tier required (paid), 3 OTP attempts max, 5-minute OTP expiry, 10-minute session timeout
**Scale/Scope**: Single apartment booking, 100 concurrent conversations

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First Development | ✅ PASS | Unit tests for AuthService, integration tests with moto, contract tests for API endpoints |
| II. Simplicity & YAGNI | ✅ PASS | Uses existing AgentCore SDK decorators, no custom OAuth2 implementation |
| III. Type Safety | ✅ PASS | Pydantic strict mode for all models, TypeScript strict for frontend |
| IV. Observability | ✅ PASS | Structured logging for auth events, correlation IDs via conversation_id |
| V. Incremental Delivery | ✅ PASS | 5 user stories with independent test scenarios |
| VI. Technology Stack | ✅ PASS | Strands agent framework, terraform-aws-agentcore module, @aws-amplify/ui-react for OTP UI. **T079x ai-elements research** validates component selection per Constitution VI.II requirement. |

**UI Component Research (Constitution VI.II)**:
- **T079x Prerequisite**: ai-elements catalogue research required before UI component decisions
- Researched `@aws-amplify/ui-react` Authenticator component per clarification session
- Component supports passwordless EMAIL_OTP flow natively
- Decision: Use Amplify Authenticator (aligns with Constitution Principle VI: official AWS SDKs, reduces custom code)

## Project Structure

### Documentation (this feature)

```text
specs/003-agentcore-identity-oauth2/
├── plan.md              # This file
├── spec.md              # Feature specification with clarifications
├── research.md          # Phase 0 research decisions
├── data-model.md        # Entity definitions, DynamoDB schema
├── quickstart.md        # Implementation guide
├── checklists/          # Testing checklists
│   └── requirements.md
└── contracts/
    ├── auth-api.yaml    # OpenAPI for OAuth2 callback endpoints
    └── auth-tools.json  # Strands @tool definitions
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── guest.py           # Extended with cognito_sub field
│   │   ├── oauth2_session.py  # NEW: OAuth2Session, OAuth2SessionStatus
│   │   ├── auth.py            # NEW: CognitoAuthState, AuthResult, WorkloadToken
│   │   └── errors.py          # Extended with auth error codes
│   ├── services/
│   │   ├── auth_service.py    # NEW: Cognito passwordless auth
│   │   ├── identity_client.py # NEW: AgentCore Identity wrapper
│   │   └── dynamodb.py        # Extended with OAuth2 session methods
│   ├── tools/
│   │   └── auth.py            # NEW: initiate_cognito_login, verify_cognito_otp, get_authenticated_guest
│   ├── api/
│   │   └── auth.py            # NEW: OAuth2 callback endpoint
│   └── agent/
│       └── booking_agent.py   # Register auth tools
└── tests/
    ├── unit/
    │   └── test_auth_service.py
    ├── integration/
    │   └── test_cognito_flow.py
    └── contract/
        └── test_auth_api.py

frontend/
├── src/
│   ├── components/
│   │   └── AuthProvider.tsx   # NEW: Amplify Authenticator wrapper
│   ├── lib/
│   │   └── auth.ts            # NEW: Auth context and hooks
│   └── app/
│       └── layout.tsx         # Wrap with AuthProvider
└── tests/
    └── unit/
        └── auth.test.tsx

infrastructure/
├── modules/
│   ├── cognito-passwordless/  # NEW: Cognito Essentials tier module
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── gateway-v2/            # NEW: FastAPI Lambda + API Gateway HTTP API
│       ├── main.tf            # Lambda + API Gateway + CloudFront origin
│       ├── variables.tf
│       └── outputs.tf
└── main.tf                    # Include modules, oauth2-sessions table, CloudFront /api routing
```

**Structure Decision**: Web application (frontend + backend) with existing Feature 001 structure. New authentication layer added as services/tools/API endpoints. Infrastructure extends existing Cognito module to Essentials tier.

## Complexity Tracking

> No constitution violations requiring justification.

## Phase 0 Research Summary

See [research.md](./research.md) for detailed decision log:

1. **AgentCore Identity Client**: Use `IdentityClient` from `bedrock_agentcore.services.identity` with `@requires_access_token` decorator
2. **Decorator Pattern**: `@requires_access_token` for protected tools with automatic token injection
3. **Cognito Passwordless**: `USER_AUTH` flow with `EMAIL_OTP` as `PreferredChallenge`
4. **Session Binding (SIMPLIFIED)**: DynamoDB table stores only `session_id` ↔ `guest_email` mapping for user identity verification. AgentCore handles state/PKCE internally via two-stage callback.
5. **PKCE (CORRECTED)**: AgentCore handles PKCE internally. Application does NOT generate or store `code_verifier`.
6. **Two-Stage Callback Flow**: Cognito → AgentCore (code exchange) → App callback (receives `session_id`, calls `CompleteResourceTokenAuth`)
7. **Provider Configuration**: Cognito registered as OAuth2 resource provider in AgentCore Identity

## Phase 1 Design Artifacts

- **Data Model**: [data-model.md](./data-model.md) - OAuth2Session, Guest extension, WorkloadToken
- **API Contracts**: [contracts/auth-api.yaml](./contracts/auth-api.yaml) - OAuth2 callback endpoints
- **Tool Definitions**: [contracts/auth-tools.json](./contracts/auth-tools.json) - Strands @tool schemas
- **Quickstart**: [quickstart.md](./quickstart.md) - Step-by-step implementation guide

## Implementation Dependencies

**From Feature 001 (agent-booking-platform)**:
- DynamoDB guests table (add cognito-sub-index GSI)
- Cognito User Pool (upgrade to Essentials tier)
- DynamoDB service singleton pattern
- ToolError standard error format
- Strands agent tool registration

**New Infrastructure**:
- DynamoDB oauth2-sessions table with TTL
- Cognito User Pool Essentials tier upgrade
- Cognito User Pool Client OAuth2 configuration
- AgentCore Identity credential provider (managed by `terraform-aws-agentcore` module, outputs wired to dependent modules)
- `infrastructure/modules/gateway-v2` Terraform module (FastAPI Lambda + API Gateway HTTP API)
- CloudFront origin for API Gateway with `/api` path routing

## Next Steps

Run `/speckit.tasks` to generate detailed task breakdown from this plan.
