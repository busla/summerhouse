# Tasks: AgentCore Identity OAuth2 Login

**Feature**: 003-agentcore-identity-oauth2 | **Generated**: 2025-12-29 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

---

## Phase 1: Setup & Configuration

**Goal**: Establish dependencies, environment configuration, and project structure for authentication feature.

### Setup Tasks

- [x] [T001] [P0] Add `bedrock-agentcore`, `boto3-stubs[cognito-idp]`, and `pyjwt` to `backend/pyproject.toml`
- [x] [T002] [P0] Add auth-related environment variables to `backend/.env.example`:
  - `AGENTCORE_IDENTITY_PROVIDER_NAME`
  - `OAUTH2_CALLBACK_URL`
  - `DYNAMODB_OAUTH2_SESSIONS_TABLE`
- [x] [T003] [P0] Create placeholder directories for new modules:
  - `backend/src/models/` (auth.py, oauth2_session.py)
  - `backend/src/services/` (auth_service.py, identity_client.py)
  - `backend/src/tools/` (auth.py)
  - `backend/src/api/` (auth.py)
- [x] [T004] [P0] Extend `backend/src/models/errors.py` with auth error codes:
  - `AUTH_REQUIRED`, `INVALID_OTP`, `OTP_EXPIRED`, `MAX_ATTEMPTS_EXCEEDED`
  - `EMAIL_DELIVERY_FAILED`, `SESSION_EXPIRED`, `AUTH_CANCELLED`, `USER_MISMATCH`

---

## Phase 2: Infrastructure (Blocking)

**Goal**: Deploy Terraform infrastructure required before backend implementation.

**Dependencies**: Must complete before Phase 3 starts.

### Dependency Graph (Cycle-Free)

```
Phase 2A (Independent - No interdependencies):
┌─────────────────────┐    ┌─────────────────┐
│ cognito-passwordless│    │ dynamodb        │
│ - user_pool_id      │    │ - oauth2-sessions│
│ - client_id         │    │   table_name    │
└─────────────────────┘    └─────────────────┘
                                  │
                                  ▼
Phase 2B (depends on dynamodb):
                           ┌──────────────────────┐
                           │ gateway-v2           │
                           │ - api_gateway_url    │
                           │ - lambda_arn         │
                           │ (receives:           │
                           │  dynamodb.sessions_  │
                           │  table_name)         │
                           └──────────────────────┘
         │                          │
         └──────────────────────────┘
                        ▼
Phase 2C (depends on 2A + 2B):
                ┌─────────────────────┐
                │ terraform-aws-      │
                │ agentcore           │
                │ - identity_provider │
                │ - cognito provider  │
                │   registration      │
                │ - oauth_callback    │
                │ (receives:          │
                │  - cognito.pool_id  │
                │  - cognito.client_id│
                │  - gateway_v2.url   │
                │  - cloudfront.domain│
                │  - dynamodb.sessions│
                │    _table_name)     │
                └─────────────────────┘
```

**Key Insight**: The gateway-v2 module receives `dynamodb.oauth2_sessions_table_name` as input (FastAPI Lambda env var). The terraform-aws-agentcore module receives callback URLs (CloudFront domain + gateway-v2 URL) for Cognito identity registration, and sets `oauth2_sessions_table_name` on AgentCore Runtime. No Phase 2D needed—FastAPI Lambda only needs dynamodb table name (available in 2B).

### Phase 2A: Independent Resources

#### Cognito Configuration

- [x] [T010] [P0] Create `infrastructure/modules/cognito-passwordless/` Terraform module:
  - [x] [T010a] Create `variables.tf` with `user_pool_tier`, `allowed_first_auth_factors`, `environment`
  - [x] [T010b] Create `main.tf` with Cognito User Pool (Essentials tier), User Pool Client (OAuth2 + PKCE)
  - [x] [T010c] Create `outputs.tf` exposing `user_pool_id`, `user_pool_arn`, `client_id`, `domain`
  - **Note**: `oauth2_callback_url` NOT needed here - Cognito redirects to AgentCore first, then AgentCore redirects to app
- [x] [T011] [P0] Update `infrastructure/main.tf` to include `cognito-passwordless` module
- [x] [T012] [P0] Configure Cognito User Pool with `AllowedFirstAuthFactors = ["EMAIL_OTP"]`

#### DynamoDB Tables (in infrastructure/modules/dynamodb)

- [x] [T013] [P0] Add `booking-{env}-oauth2-sessions` table to `infrastructure/modules/dynamodb/`:
  - PK: `session_id` (only key needed - AgentCore provides session_id in callback)
  - TTL: `expires_at` (10-minute auto-expiry)
  - ~~GSI: `state-index` on `state`~~ **REMOVED**: AgentCore handles state internally
- [x] [T014] [P0] Add `cognito-sub-index` GSI to existing `booking-{env}-guests` table
- [x] [T015] [P0] Add `cognito_sub` attribute to guests table schema

### Phase 2B: Gateway-v2 Module (depends on dynamodb)

#### FastAPI Lambda + API Gateway

- [x] [T016] [P0] Create `infrastructure/modules/gateway-v2/` Terraform module:
  - [x] [T016a] Create `variables.tf` with `app_path`, `handler`, `oauth2_sessions_table_name` (from dynamodb module)
  - [x] [T016b] Create `main.tf` using `terraform-aws-modules/lambda/aws` (>=8.1.2)
  - [x] [T016c] Configure API Gateway HTTP API with `$default` stage (no stage prefix)
  - [x] [T016d] Use `source_path` with `pip_requirements` for declarative packaging
  - [x] [T016e] Create `outputs.tf` exposing `api_gateway_url`, `lambda_arn`, `lambda_function_name`
  - [x] [T016f] Set `DYNAMODB_OAUTH2_SESSIONS_TABLE` env var from `var.oauth2_sessions_table_name` input
  - **Note**: Lambda receives dynamodb table name at creation (from Phase 2A). No AgentCore outputs needed.
- [x] [T017] [P0] Update CloudFront distribution to add API Gateway as origin with `/api` path routing

### Phase 2C: AgentCore Module (depends on 2A + 2B)

- [x] [T022] [P0] Wire Phase 2A + 2B outputs to `terraform-aws-agentcore` module inputs:
  - [x] [T022a] Pass `module.cognito.user_pool_id` and `client_id` for Cognito provider registration
  - [x] [T022b] Pass `module.gateway_v2.oauth2_callback_url` as allowed OAuth2 callback URL
  - [ ] [T022c] Pass CloudFront custom domain as additional allowed OAuth2 callback URL
  - [x] [T022d] Pass `module.dynamodb.oauth2_sessions_table_name` for AgentCore Runtime env var (via gateway_v2)
  - **Note**: terraform-aws-agentcore registers callback URLs in AgentCore Cognito identity and sets session table name on AgentCore Runtime

### ~~Phase 2D: Lambda Environment Update~~ **REMOVED**

~~T023 removed~~ - FastAPI Lambda only needs `DYNAMODB_OAUTH2_SESSIONS_TABLE` env var, which is set in Phase 2B (T016f) from dynamodb module output. The `AGENTCORE_IDENTITY_PROVIDER_NAME` and `OAUTH2_CALLBACK_URL` env vars are only needed by AgentCore Runtime (not FastAPI Lambda), and are set internally by the terraform-aws-agentcore module.

### Pre-Implementation Research

- [ ] [T009] [P0] Verify `terraform-aws-agentcore` module accepts required inputs:
  - [ ] [T009a] Confirm module accepts `cognito_user_pool_id` and `cognito_client_id` for Cognito provider registration
  - [ ] [T009b] Confirm module accepts `allowed_callback_urls` list for OAuth2 callback URL registration
  - [ ] [T009c] Confirm module accepts `oauth2_sessions_table_name` for AgentCore Runtime env var
  - [ ] [T009d] If inputs missing, raise issue or extend module before Phase 2C

### Terraform Validation

- [x] [T018] [P0] Run `task tf:plan:dev` and verify all infrastructure changes (single apply - Terraform resolves dependencies automatically)
- [x] [T019] [P0] Run `task tf:apply:dev` to deploy infrastructure
- [x] [T020] [P0] Verify Cognito User Pool is Essentials tier with EMAIL_OTP enabled
- [x] [T021] [P0] Verify OAuth2 sessions table created with TTL in dynamodb module

---

## Phase 3: Passwordless EMAIL_OTP Authentication (US1 + US2)

**Goal**: Implement Cognito USER_AUTH flow with EMAIL_OTP for guest sign-in and registration.

**User Stories**:
- US1: Guest Initiates Passwordless Authentication (P1)
- US2: New Guest Registration with Passwordless (P1)

**Independent Test**: Start agent conversation → provide email → receive OTP → enter code → authenticated.

### Models

- [x] [T030] [P1] [US1] Create `backend/src/models/auth.py`:
  - [x] [T030a] Define `CognitoAuthChallenge` enum (`EMAIL_OTP`)
  - [x] [T030b] Define `CognitoAuthState` model (session, challenge, username, attempts, otp_sent_at)
  - [x] [T030c] Define `AuthResult` model (success, guest, error_code, message)
- [x] [T031] [P1] [US1] Extend `backend/src/models/guest.py`:
  - Add `cognito_sub: str | None` field with description

### TDD Gate (Constitution Principle I)

- [x] [T032z] [P1] **TDD GATE**: All tests in T032 and T033 MUST be written and RED (failing) before any implementation in T034-T038 begins
  - Tests define expected behavior BEFORE implementation
  - Implementation PRs require corresponding test coverage

### Tests (Test-First)

- [x] [T032] [P1] [US1] Create `backend/tests/unit/test_auth_service.py`:
  - [x] [T032a] Test `initiate_passwordless_auth` returns `CognitoAuthState` with session token
  - [x] [T032b] Test `verify_otp` success returns `AuthResult` with guest
  - [x] [T032c] Test `verify_otp` with invalid code returns `INVALID_OTP` error
  - [x] [T032d] Test `verify_otp` with expired code returns `OTP_EXPIRED` error
  - [x] [T032e] Test `get_or_create_guest` creates new guest for unknown email
  - [x] [T032f] Test `get_or_create_guest` binds cognito_sub to existing guest
- [x] [T033] [P1] [US2] Create `backend/tests/integration/test_auth_acceptance.py`:
  - [x] [T033a] Test full EMAIL_OTP flow with moto mock (note: moto may not fully support EMAIL_OTP)
  - [x] [T033b] Test new user registration creates verified guest
  - [x] [T033c] Test returning user sign-in with existing cognito_sub

### Auth Service Implementation

- [x] [T034] [P1] [US1] Create `backend/src/services/auth_service.py`:
  - [x] [T034a] Implement `AuthService.__init__` with boto3 cognito-idp client
  - [x] [T034b] Implement `initiate_passwordless_auth(email)` → `CognitoAuthState`
  - [x] [T034c] Implement `verify_otp(email, otp_code, session)` → `AuthResult`
  - [x] [T034d] Implement `get_or_create_guest(cognito_sub, email)` → `Guest`
  - [x] [T034e] Implement `decode_id_token(id_token)` → `dict` (JWT decoding)
  - [x] [T034f] [FR-013] Enforce 5-minute OTP expiry via `otp_sent_at` timestamp check in `verify_otp()`
  - [x] [T034g] [FR-014] Enforce max 3 OTP attempts via `CognitoAuthState.attempts` counter, return `MAX_ATTEMPTS_EXCEEDED` error

### DynamoDB Service Extension

- [x] [T035] [P1] [US1] Extend `backend/src/services/dynamodb.py`:
  - [x] [T035a] Add `get_guest_by_cognito_sub(cognito_sub)` method
  - [x] [T035b] Add `update_guest_cognito_sub(guest_id, cognito_sub)` method for cognito_sub binding

### Auth Tools

- [x] [T036] [P1] [US1] Create `backend/src/tools/auth.py`:
  - [x] [T036a] Implement `initiate_cognito_login(email)` tool with @tool decorator
  - [x] [T036b] Implement `verify_cognito_otp(email, otp_code, session_token)` tool
  - [x] [T036c] Use `_get_auth_service()` singleton pattern (per CLAUDE.md)
  - [x] [T036d] Return `ToolError` format for all error conditions

### Tool Tests

- [x] [T037] [P1] [US1] Create `backend/tests/unit/test_auth_tools.py`:
  - [x] [T037a] Test `initiate_cognito_login` returns success with session_token
  - [x] [T037b] Test `initiate_cognito_login` returns EMAIL_DELIVERY_FAILED on exception
  - [x] [T037c] Test `verify_cognito_otp` returns guest_id on success
  - [x] [T037d] Test `verify_cognito_otp` returns INVALID_OTP error code

### Agent Integration

- [x] [T038] [P1] [US1] Update `backend/src/tools/__init__.py`:
  - Import and register `initiate_cognito_login`, `verify_cognito_otp` tools in ALL_TOOLS

### Bug Fix: Cognito `prevent_user_existence_errors` Detection (2025-12-29)

**Issue**: Cognito's `prevent_user_existence_errors = "ENABLED"` (security best practice) masks non-existent users by still returning EMAIL_OTP challenge but with PASSWORD_SRP/PASSWORD in `AvailableChallenges`. This caused silent failures for new user registration.

**Solution**:
- [x] [T042a] [P1] Detect non-existent users by checking `AvailableChallenges` for PASSWORD options
- [x] [T042b] [P1] Auto-create user via `AdminCreateUser` when PASSWORD options detected, then retry auth
- [x] [T042c] [P1] Handle race condition where `UsernameExistsException` is thrown during create
- [x] [T042d] [P1] Add IAM permissions (`cognito-idp:AdminCreateUser`, `AdminGetUser`, `AdminUpdateUserAttributes`) to AgentCore runtime role in `main.tf`

### Acceptance Tests

- [x] [T039] [P1] [US1] Verify: Cognito sends EMAIL_OTP within 60 seconds of `initiate_cognito_login`
- [x] [T040] [P1] [US1] Verify: OTP codes expire after 5 minutes (implemented via `OTP_VALIDITY_MINUTES = 5`)
- [x] [T041] [P1] [US1] Verify: Max 3 OTP attempts per session (implemented via `MAX_OTP_ATTEMPTS = 3`)
- [x] [T042] [P1] [US2] Verify: New email creates Cognito user with `email_verified=true` after OTP (fixed via T042a-d)

---

## Phase 4: Agent Workload Token (US3)

**Goal**: Implement agent workload identity for AgentCore API access.

**User Story**: US3: Agent Obtains Workload Access Token (P1)

**Independent Test**: Initialize agent → call `get_workload_access_token()` → verify valid JWT returned.

### Models

- [x] [T050] [P1] [US3] Add `WorkloadToken` model to `backend/src/models/auth.py`:
  - Fields: access_token, token_type, expires_at, workload_name, user_id
  - Property: `is_expired` (with 30-second buffer)

### Tests (Test-First)

- [x] [T051] [P1] [US3] Create `backend/tests/unit/test_identity_client.py`:
  - [x] [T051a] Test `get_workload_token()` returns `WorkloadToken` (anonymous agent token)
  - [x] [T051b] Test token refresh when `is_expired` returns true
  - [x] [T051c] Test `get_workload_token(user_id=X)` returns user-delegated token (same function, optional parameter)

### Identity Client Implementation

- [x] [T052] [P1] [US3] Create `backend/src/services/identity_client.py`:
  - [x] [T052a] Implement `IdentityClient.__init__` with AgentCore SDK IdentityClient
  - [x] [T052b] Implement `get_workload_token(user_token=None, user_id=None)` → `WorkloadToken`
    - Single function with optional parameters for user-delegated access
    - No `user_token`/`user_id` = anonymous agent token
    - With `user_token` = user-delegated via JWT
    - With `user_id` = user-delegated via user ID

### Integration

- [x] [T053] [P1] [US3] Verify agent can obtain workload token on initialization
- [x] [T054] [P1] [US3] Verify workload token auto-refreshes when near expiration (via cache check)

---

## Phase 5: Three-Legged OAuth2 Flow (US4 + US5)

**Goal**: Implement full OAuth2 3LO flow with session binding for callback handling.

**User Stories**:
- US4: Three-Legged OAuth2 Flow for Cognito (P2)
- US5: Session Binding for OAuth2 Callbacks (P2)

**Independent Test**: Request auth → receive auth URL → complete Cognito login → AgentCore callback → app callback receives `session_id` → `CompleteResourceTokenAuth` verifies user.

### Models (SIMPLIFIED)

- [x] [T060] [P2] [US4] Create `backend/src/models/oauth2_session.py`:
  - [x] [T060a] Define `OAuth2SessionStatus` enum (PENDING, COMPLETED, EXPIRED, FAILED)
  - [x] [T060b] Define `OAuth2Session` model (session_id, conversation_id, guest_email, status, created_at, expires_at)
    - **NOTE**: AgentCore handles state/PKCE internally - app only stores user identity correlation
  - [x] [T060c] Define `OAuth2SessionCreate` model (session_id, conversation_id, guest_email)

### TDD Gate (Constitution Principle I)

- [x] [T061z] [P2] **TDD GATE**: All tests in T061, T062, and T067 MUST be written and RED (failing) before any implementation in T063-T069 begins
  - Tests define expected behavior BEFORE implementation
  - Contract tests (T067) define API surface before implementation

### Tests (Test-First) - SIMPLIFIED

- [x] [T061] [P2] [US4] Create `backend/tests/unit/test_oauth2_session.py`:
  - [x] [T061a] Test `create_oauth2_session` stores session with correct fields
  - [x] [T061b] Test `complete_oauth2` with matching user updates status to COMPLETED
  - [x] [T061c] Test `get_session(session_id)` returns correct session
- [x] [T062] [P2] [US5] Create `backend/tests/unit/test_user_verification.py`:
  - [x] [T062a] Test concurrent sessions are correctly isolated by session_id
  - [x] [T062b] Test `CompleteResourceTokenAuth` with mismatched user_identifier returns error
  - [x] [T062c] Test callback correctly correlates session_id to guest_email

### DynamoDB Service Extension (SIMPLIFIED)

- [x] [T063] [P2] [US4] Extend `backend/src/services/dynamodb.py`:
  - [x] [T063a] Add `create_oauth2_session(session)` method
  - [x] [T063b] Add `get_oauth2_session(session_id)` method
  - [x] [T063c] Add `update_oauth2_session_status(session_id, status)` method
  - ~~[ ] [T063d] Add `get_oauth2_session_by_state(state)` method~~ **REMOVED**: AgentCore handles state

### Identity Client Extension (CORRECTED)

- [x] [T064] [P2] [US4] Extend `backend/src/services/identity_client.py`:
  - [ ] [T064a] Implement `initiate_oauth2(conversation_id, guest_email, callback_url)` → stores session, returns auth_url (DEFERRED - uses @requires_access_token decorator instead)
  - [x] [T064b] Implement `complete_oauth2(session_id, guest_email)` → calls `CompleteResourceTokenAuth(session_uri, user_identifier)`
  - [x] [T064c] Session lookup delegated to DynamoDB service (no separate method needed)

### Auth Tools Extension

- [x] [T065] [P2] [US4] Extend `backend/src/tools/auth.py`:
  - [x] [T065a] Implement `stream_auth_url_to_client(auth_url)` callback function
  - [x] [T065b] Implement `get_authenticated_guest()` tool with `@requires_access_token` decorator
  - [x] [T065c] Configure decorator with provider_name, scopes, auth_flow, on_auth_url, callback_url

### OAuth2 Callback API

- [x] [T066] [P2] [US4] Create `backend/src/api/auth.py`:
  - [x] [T066a] Create FastAPI router with `/auth` prefix
  - [x] [T066b] Implement `GET /auth/callback` endpoint - receives `session_id` from AgentCore redirect (NOT raw OAuth2 `code`/`state`), looks up guest_email, calls `CompleteResourceTokenAuth`
  - [x] [T066c] Implement `GET /auth/session/{session_id}` endpoint (getSessionStatus)
  - [x] [T066d] Handle OAuth2 error parameters (error, error_description)
  - [x] [T066e] Redirect to frontend with auth status query params

### Contract Tests

- [x] [T067] [P2] [US4] Create `backend/tests/contract/test_auth_api.py`:
  - [x] [T067a] Test `/auth/callback` with valid `session_id` returns 302 redirect
  - [x] [T067b] Test `/auth/callback` with invalid `session_id` returns 400 error
  - [x] [T067c] Test `/auth/callback` with error parameter redirects with error message
  - [x] [T067d] Test `/auth/session/{session_id}` returns session status JSON
  - [x] [T067e] Test `/auth/session/{session_id}` with unknown ID returns 404

### API Router Registration

- [x] [T068] [P2] [US4] Register auth router in FastAPI app:
  - Update `backend/src/api_app.py` to include auth router

### Agent Integration

- [x] [T069] [P2] [US4] Register `get_authenticated_guest` in tools/__init__.py:
  - Added to ALL_TOOLS list for agent tool registration

### Acceptance Tests

- [ ] [T070] [P2] [US4] Verify: Authorization URL contains valid OAuth2 parameters (client_id, redirect_uri, scope) - Note: state/code_challenge are handled internally by AgentCore
- [ ] [T071] [P2] [US4] Verify: OAuth2 callback processing completes in under 2 seconds
- [ ] [T072] [P2] [US5] Verify: Concurrent auth flows bind to correct sessions
- [ ] [T073] [P2] [US5] Verify: Invalid `session_id` parameter returns appropriate error

---

## Phase 6: Frontend Authentication (Optional)

**Goal**: Integrate Amplify Authenticator component for OTP flow UI.

**Note**: This phase is optional for MVP. The agent can handle auth flow via conversation.

### Research (Constitution Principle VI: Official AWS SDKs)

- [ ] [T079x] [P3] Research ai-elements catalogue for authentication UI components:
  - [ ] [T079xa] Search ai-elements catalogue for existing OAuth2/OTP authentication components
  - [ ] [T079xb] Evaluate if ai-elements provides EMAIL_OTP flow UI vs `@aws-amplify/ui-react`
  - [ ] [T079xc] Document decision: use ai-elements component OR justify Amplify (no suitable ai-elements component exists)
- [ ] [T079] [P3] Research `@aws-amplify/ui-react` Authenticator component for EMAIL_OTP:
  - **Prerequisite**: T079x must confirm no suitable ai-elements component exists
  - [ ] [T079a] Verify Authenticator supports passwordless EMAIL_OTP flow configuration
  - [ ] [T079b] Document required Amplify configuration for USER_AUTH + EMAIL_OTP
  - [ ] [T079c] Identify any Amplify version constraints for EMAIL_OTP support
  - [ ] [T079d] Document how auth URL from agent tool should integrate with Amplify UI flow

### Frontend Setup

- [ ] [T080] [P3] Add `@aws-amplify/ui-react` and `@aws-amplify/auth` to `frontend/package.json`
- [ ] [T081] [P3] Create `frontend/src/components/AuthProvider.tsx`:
  - Wrap app with Amplify Authenticator configured for EMAIL_OTP
- [ ] [T082] [P3] Create `frontend/src/lib/auth.ts`:
  - Export auth context and hooks
- [ ] [T083] [P3] Update `frontend/src/app/layout.tsx`:
  - Wrap with AuthProvider

### Frontend Tests

- [ ] [T084] [P3] Create `frontend/tests/unit/auth.test.tsx`:
  - Test AuthProvider renders Authenticator
  - Test auth state updates on login/logout

---

## Phase 7: Polish & Cross-Cutting

**Goal**: Documentation, deployment verification, and edge case handling.

### Documentation

- [x] [T090] [P3] Update `backend/.env.example` with all required auth variables
- [ ] [T091] [P3] Update `CLAUDE.md` with auth tools and patterns
- [ ] [T092] [P3] Add auth flow troubleshooting to quickstart.md
- [ ] [T104] [P2] [FR-017] Document AgentCore Identity provider configuration (Cognito registration with terraform-aws-agentcore module outputs)

### Edge Case Handling

- [ ] [T093] [P2] Implement OTP resend functionality (rate limited)
- [ ] [T094] [P2] Handle Cognito email delivery failures gracefully (return `EMAIL_DELIVERY_FAILED` error code)
- [ ] [T095] [P2] Implement 10-minute session timeout with user notification
- [ ] [T099] [P2] Handle Cognito service unavailability with graceful degradation and retry guidance
- [ ] [T100] [P2] Handle concurrent login attempts from same email (session conflict resolution)

### Deployment Verification

- [x] [T096] [P1] Verify Cognito Essentials tier is active in deployed environment (User Pool: eu-west-1_VEgg3Z7oI)
- [x] [T097] [P1] Test full EMAIL_OTP flow in dev environment (tested 2025-12-29 with new user email)
- [x] [T098] [P1] Verify OAuth2 callback URL is correctly configured in Cognito client

### Success Criteria Verification

- [ ] [T101] [P1] [SC-004] Test concurrent auth flows to verify zero session confusion (integration test)
- [ ] [T102] [P1] [SC-005] Verify workload token auto-refresh has no user-facing latency impact (<100ms overhead)
- [ ] [T103] [P2] [SC-006] Add structured logging for OAuth2 flow completion tracking (success/failure/abandonment)

---

## Summary

| Phase | Tasks | Priority | User Stories |
|-------|-------|----------|--------------|
| Phase 1: Setup | 4 | P0 | — |
| Phase 2: Infrastructure | 16 | P0 | — |
| Phase 3: EMAIL_OTP Auth | 21 | P1 | US1, US2 |
| Phase 4: Workload Token | 5 | P1 | US3 |
| Phase 5: OAuth2 3LO | 15 | P2 | US4, US5 |
| Phase 6: Frontend | 9 | P3 | — |
| Phase 7: Polish | 15 | P1-P3 | — |
| **Total** | **85** | | |

**Note**: Phase 3 includes 4 additional bug fix tasks (T042a-d) added 2025-12-29 for Cognito `prevent_user_existence_errors` detection.

### MVP Scope

**Minimum Viable Product**: Phases 1-4 (46 tasks)
- Infrastructure deployed
- EMAIL_OTP sign-in and registration working (including `prevent_user_existence_errors` handling)
- Agent can authenticate guests via conversation
- Workload token for AgentCore API access

**Status (2025-12-29)**: Phases 1-3 complete and deployed. End-to-end EMAIL_OTP flow verified with new user registration.

### Parallel Opportunities

- **T009** (AgentCore module research) can start immediately as Phase 2 prerequisite
- **Phase 2A** (T010-T017): Cognito, DynamoDB, and gateway-v2 can run in parallel
- **T030-T031** (Models) can start while infrastructure deploys
- **T032-T033** (Tests) MUST complete before implementation per TDD gate (T032z)
- **T050-T054** (Phase 4) can start once Phase 3 models are complete
- **T061-T067** (Phase 5 Tests) MUST complete before implementation per TDD gate (T061z)
- **T079** (Amplify research) should complete before T080-T084 (Frontend setup)

### Dependencies

```
Phase 1 → Phase 2A → Phase 2B → Phase 2C → Phase 3 → Phase 4 → Phase 5 → Phase 7
          (parallel)                           ↘                 ↗
                                                 Phase 6 ────────┘
```

**Phase 2 Sub-Dependencies**:
- Phase 2A (Cognito + DynamoDB) - independent modules, can run in parallel
- Phase 2B (Gateway-v2) - depends on DynamoDB table name from Phase 2A
- Phase 2C (AgentCore) - depends on outputs from both 2A and 2B
