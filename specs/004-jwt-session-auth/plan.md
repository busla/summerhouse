# Implementation Plan: JWT Session Authentication Flow

**Branch**: `004-jwt-session-auth` | **Date**: 2025-12-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-jwt-session-auth/spec.md`

## Summary

Implement JWT token delivery from backend to frontend after successful EMAIL_OTP verification, enabling authenticated AgentCore requests. The core gap in the current implementation is that `verify_cognito_otp` returns guest info but not Cognito tokens, leaving the frontend unable to make authenticated requests.

**Technical approach**: Modify the `verify_cognito_otp` tool to return Cognito tokens in its response, which flow through the AgentCore SSE stream to the frontend. The frontend extracts tokens from tool results, stores them in localStorage, and includes them in subsequent AgentCore requests via the `Authorization: Bearer` header.

## Technical Context

**Language/Version**: Python 3.13+ (backend), TypeScript 5.x strict mode (frontend)
**Primary Dependencies**: strands-agents, bedrock-agentcore, boto3 (cognito-idp), pyjwt (backend); @aws-sdk/client-bedrock-agentcore, @aws-sdk/credential-providers, Vercel AI SDK v6, @ai-sdk/react (frontend)
**Storage**: DynamoDB (guests table), localStorage (browser session)
**Testing**: pytest (backend), vitest (frontend unit), playwright (E2E)
**Target Platform**: AWS AgentCore Runtime, S3/CloudFront (frontend)
**Project Type**: Web application (frontend + backend)
**Performance Goals**: Auth flow completion <90s (excluding email), token refresh <500ms, zero double-auth prompts
**Constraints**: Must use AdminInitiateAuth (not hosted UI), tokens must persist across page refresh, zero data leakage between users
**Scale/Scope**: Single property, <100 concurrent users

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Pre-Design | Post-Design |
|-----------|--------|------------|-------------|
| I. Test-First Development | ✅ PASS | Will write tests before implementation | Tests defined in quickstart.md |
| II. Simplicity & YAGNI | ✅ PASS | Minimal changes to existing flow | Only 3 files modified, no new abstractions |
| III. Type Safety | ✅ PASS | TypeScript/Pydantic strict mode | TokenDeliveryEvent type-discriminated |
| IV. Observability | ✅ PASS | Correlation IDs in place | Logging added to token delivery |
| V. Incremental Delivery | ✅ PASS | Independently testable stories | 5 user stories can ship separately |
| VI. Technology Stack | ✅ PASS | Uses prescribed tech | No new dependencies beyond pyjwt |
| VI. UI Component Development | ✅ PASS | No new UI components | Auth handled in hooks, not UI |

**Post-Design Check**: ✅ All principles still satisfied. Design adds minimal complexity.

## Project Structure

### Documentation (this feature)

```text
specs/004-jwt-session-auth/
├── plan.md              # This file
├── research.md          # Phase 0 output - token delivery mechanism research
├── data-model.md        # Phase 1 output - AuthSession, TokenDeliveryEvent
├── quickstart.md        # Phase 1 output - integration guide
├── contracts/           # Phase 1 output - tool response schemas
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   └── auth.py              # AuthSession, TokenDeliveryEvent models
│   ├── services/
│   │   └── auth_service.py      # AuthService with token return
│   └── tools/
│       └── auth.py              # verify_cognito_otp with token delivery
└── tests/
    ├── unit/
    │   └── tools/
    │       └── test_auth.py     # Tool response format tests
    └── integration/
        └── test_auth_flow.py    # Full OTP → token flow tests

frontend/
├── src/
│   ├── lib/
│   │   ├── auth.ts              # Session storage, token handling
│   │   └── agentcore-transport.ts # Add auth header support
│   ├── hooks/
│   │   └── useAgentChat.ts      # Token extraction from tool results
│   └── types/
│       └── index.ts             # AuthSession, TokenDeliveryEvent types
└── tests/
    ├── unit/
    │   └── lib/
    │       └── auth.test.ts     # Session storage tests
    └── e2e/
        └── auth-flow.spec.ts    # Full auth E2E test
```

**Structure Decision**: Web application structure with existing `backend/` and `frontend/` directories. Changes are additive to existing files - no new directories needed.

## Complexity Tracking

> **No violations - feature uses straightforward tool-to-frontend data flow**

The implementation follows the existing Strands → SSE → Frontend pattern already in use for other tool responses. No new architectural patterns or abstractions required.
