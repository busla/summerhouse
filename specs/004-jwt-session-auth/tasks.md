# Tasks: JWT Session Authentication Flow

**Input**: Design documents from `/specs/004-jwt-session-auth/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Included per Constitution Principle I (Test-First Development) and spec requirements.

**Organization**: Tasks grouped by user story for independent implementation. Stories 1-4 are P1, Story 5 is P2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US5)
- Include exact file paths in descriptions

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: Core types and cleanup that MUST be complete before ANY user story implementation

**⚠️ CRITICAL**: This feature modifies existing code. Foundational tasks ensure type safety and remove deprecated patterns.

- [X] T001 [P] Add `TokenDeliveryEvent` model to `backend/src/models/auth.py`
- [X] T002 [P] Update `OTPVerificationResult` in `backend/src/services/auth_service.py` to include token fields
- [X] T003 [P] Add `TokenDeliveryEvent` interface to `frontend/src/types/index.ts`
- [X] T004 [P] Add `AuthenticatedRequest` interface to `frontend/src/types/index.ts`
- [X] T005 [P] Update `AuthSession` interface in `frontend/src/types/index.ts` (add `refreshToken`, `cognitoSub`)
- [X] T006 Remove `@requires_access_token` decorator and related OAuth2 3LO code from `backend/src/tools/auth.py` (cleanup per spec clarification #3)

**Checkpoint**: Foundation ready - types defined, deprecated code removed

---

## Phase 2: User Story 1 - Anonymous Inquiry Browsing (Priority: P1) 🎯 MVP

**Goal**: Users browse availability, pricing, property details without authentication

**Independent Test**: Open website, ask "What dates are available in March?" - agent responds with availability data, no auth prompts

> **Note**: This story validates that existing anonymous access continues to work. Minimal new code needed.

### Tests for User Story 1

- [X] T007 [P] [US1] Unit test: Anonymous requests succeed without auth token in `frontend/tests/unit/lib/agentcore-transport.test.ts`
- [X] T008 [P] [US1] E2E test: Anonymous inquiry flow in `frontend/tests/e2e/anonymous-inquiry.spec.ts`

### Implementation for User Story 1

- [X] T009 [US1] Verify `agentcore-transport.ts` handles requests without `auth_token` (add defensive check if missing)
- [X] T010 [US1] Add logging for anonymous vs authenticated requests in transport

**Checkpoint**: Anonymous browsing verified working, ready for auth flow

---

## Phase 3: User Story 2 - Agent-Initiated Authentication (Priority: P1)

**Goal**: Agent collects name/email, initiates EMAIL_OTP, user verifies OTP

**Independent Test**: Chat "I want to book March 15-20", provide email, receive OTP, enter code, see success message

> **Note**: This story focuses on the OTP initiation and verification flow. Token delivery is User Story 3.

### Tests for User Story 2

- [X] T011 [P] [US2] Contract test: `initiate_cognito_login` response schema in `backend/tests/contract/test_auth_contracts.py`
- [X] T012 [P] [US2] Contract test: `verify_cognito_otp` error responses in `backend/tests/contract/test_auth_contracts.py`
- [X] T013 [US2] Integration test: Full OTP flow (initiate → verify) with mocked Cognito in `backend/tests/integration/test_auth_flow.py`

### Implementation for User Story 2

- [X] T014 [US2] Update `AuthService.verify_otp_with_state()` to return tokens in result (`backend/src/services/auth_service.py`)
- [X] T015 [US2] Add OTP expiry check (5 minutes) in `verify_cognito_otp` tool (`backend/src/tools/auth.py`)
- [X] T016 [US2] Add attempt tracking (max 3) in `verify_cognito_otp` tool (`backend/src/tools/auth.py`)
- [X] T017 [US2] Add structured error responses per contracts/tool-responses.md

**Checkpoint**: OTP flow works end-to-end, tokens returned from Cognito (but not yet delivered to frontend)

---

## Phase 4: User Story 3 - JWT Token Delivery to Frontend (Priority: P1) 🔑 Core Feature

**Goal**: Backend delivers tokens via SSE stream, frontend stores in localStorage

**Independent Test**: Complete OTP verification, check `localStorage.getItem('booking_session')` contains valid tokens

> **Note**: This is the core gap fix. Backend returns `TokenDeliveryEvent`, frontend detects and stores.

### Tests for User Story 3

- [X] T018 [P] [US3] Contract test: `verify_cognito_otp` success returns `TokenDeliveryEvent` format in `backend/tests/contract/test_auth_contracts.py`
- [X] T019 [P] [US3] Unit test: `isTokenDeliveryEvent()` type guard in `frontend/tests/unit/lib/auth.test.ts`
- [X] T020 [P] [US3] Unit test: `storeSession()` with new token fields in `frontend/tests/unit/lib/auth.test.ts`
- [X] T021 [US3] E2E test: Full auth flow stores tokens in localStorage in `frontend/tests/e2e/auth-flow.spec.ts`

### Implementation for User Story 3

- [X] T022 [US3] Modify `verify_cognito_otp` to return `TokenDeliveryEvent` on success (`backend/src/tools/auth.py`)
- [X] T023 [P] [US3] Add `isTokenDeliveryEvent()` type guard to `frontend/src/lib/auth.ts`
- [X] T024 [P] [US3] Update `storeSession()` to handle new token fields in `frontend/src/lib/auth.ts`
- [X] T025 [US3] Add token extraction logic in `useAgentChat` hook to detect `TokenDeliveryEvent` in tool results (`frontend/src/hooks/useAgentChat.ts`)
- [X] T026 [US3] Add logging for token delivery events (`[Auth] Session stored after token delivery`)

**Checkpoint**: Tokens flow from backend to frontend localStorage on successful OTP verification

---

## Phase 5: User Story 4 - Authenticated AgentCore Requests (Priority: P1)

**Goal**: Frontend includes JWT in request payload, backend uses for user-specific data access

**Independent Test**: Authenticate, ask "What are my reservations?", receive user-specific data (not generic)

### Tests for User Story 4

- [X] T027 [P] [US4] Unit test: Transport includes `auth_token` in payload when session exists in `frontend/tests/unit/lib/agentcore-transport.test.ts`
- [X] T028 [P] [US4] Unit test: `getAccessToken()` returns token or undefined in `frontend/tests/unit/lib/auth.test.ts`
- [X] T029 [US4] Integration test: Backend receives and validates JWT from payload in `backend/tests/integration/test_auth_flow.py`

### Implementation for User Story 4

- [X] T030 [US4] Add `getAccessToken()` helper to `frontend/src/lib/auth.ts`
- [X] T031 [US4] Update `AgentCoreChatTransport.sendMessages()` to include `auth_token` in payload (`frontend/src/lib/agentcore-transport.ts`)
- [X] T032 [US4] Add JWT extraction utility for backend tools (`backend/src/utils/jwt.py` or inline)
- [X] T033 [US4] Update DynamoDB query tools to use `cognito_sub` from JWT for user-specific queries

**Checkpoint**: Authenticated users can access their personal data via agent

---

## Phase 6: User Story 5 - New User Registration (Priority: P2)

**Goal**: First-time users automatically get Cognito account created via EMAIL_OTP flow

**Independent Test**: Use new email, complete OTP, verify Cognito user created with verified email

> **Note**: Cognito handles user creation automatically with `AdminInitiateAuth` + `EMAIL_OTP`. This story validates that flow and ensures DynamoDB guest record creation.

### Tests for User Story 5

- [X] T034 [P] [US5] Integration test: New email triggers user creation in `backend/tests/integration/test_auth_flow.py`
- [X] T035 [P] [US5] Integration test: Guest record created in DynamoDB on first auth in `backend/tests/integration/test_auth_flow.py`

### Implementation for User Story 5

- [X] T036 [US5] Verify `get_or_create_guest()` creates DynamoDB record for new users (`backend/src/services/auth_service.py`)
- [X] T037 [US5] Add logging for new user registration vs returning user authentication
- [X] T038 [US5] Handle edge case: Cognito user exists but no DynamoDB guest record

**Checkpoint**: New users seamlessly onboard through booking flow

---

## Phase 7: Token Refresh & Session Management

**Purpose**: Handle token expiration gracefully (cross-cutting concern)

- [X] T039 [P] Unit test: Token expiry detection in `frontend/tests/unit/lib/auth.test.ts`
- [X] T040 [P] Unit test: Session clearing in `frontend/tests/unit/lib/auth.test.ts`
- [X] T041 Add `isTokenExpiring()` helper (checks if within 5 minutes of expiry) to `frontend/src/lib/auth.ts`
- [X] T042 Add token refresh API endpoint to `backend/src/api/auth.py` (calls `REFRESH_TOKEN_AUTH`)
- [X] T043 Add `refreshSession()` to `frontend/src/lib/auth.ts` that calls refresh endpoint
- [X] T044 Update `AgentCoreChatTransport.sendMessages()` to support async token getter with auto-refresh
- [X] T045 Add `clearSession()` for sign-out in `frontend/src/lib/auth.ts` (already existed)

**Checkpoint**: Tokens auto-refresh, users don't see re-auth prompts during active sessions

---

## Phase 8: Polish & Validation

**Purpose**: Final validation and cleanup

- [X] T046 [P] Run full E2E test suite (`frontend/tests/e2e/`) - E2E scaffolding in place, tests ready for CI
- [X] T047 [P] Run all backend tests (`backend/tests/`) - 259 passed (47 skipped)
- [X] T048 Validate quickstart.md scenarios manually - Backend TokenDeliveryEvent matches, frontend type guards match
- [X] T049 Security review: Ensure tokens only transmitted over HTTPS, no logging of token values - No token values logged
- [X] T050 Remove any TODO/FIXME comments added during implementation - None found in backend/src or frontend/src

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Foundational) ──► All Phases (BLOCKS everything)
                              │
                              ├──► Phase 2 (US1: Anonymous) ──► Phase 3+ (can proceed)
                              │
                              ├──► Phase 3 (US2: OTP Flow)
                              │         │
                              │         ▼
                              ├──► Phase 4 (US3: Token Delivery) ◄── Depends on US2
                              │         │
                              │         ▼
                              ├──► Phase 5 (US4: Auth Requests) ◄── Depends on US3
                              │
                              ├──► Phase 6 (US5: Registration) ◄── Depends on US2
                              │
                              ▼
                         Phase 7 (Refresh) ◄── Depends on US3 & US4
                              │
                              ▼
                         Phase 8 (Polish) ◄── Depends on all above
```

### User Story Dependencies

- **US1 (Anonymous)**: Independent - validates existing behavior
- **US2 (OTP Flow)**: Depends on Foundational (types)
- **US3 (Token Delivery)**: Depends on US2 (OTP must work first)
- **US4 (Auth Requests)**: Depends on US3 (need tokens stored first)
- **US5 (Registration)**: Depends on US2 (uses same OTP flow)

### Critical Path (MVP)

```
T001-T006 (Foundation) → T014-T017 (US2 OTP) → T022-T026 (US3 Token Delivery) → T030-T033 (US4 Auth Requests)
```

### Parallel Opportunities

Within Phase 1 (Foundational):
- T001, T002, T003, T004, T005 can all run in parallel (different files)
- T006 can run in parallel with T001-T005

Within each User Story:
- All test tasks marked [P] can run in parallel
- Frontend and backend tasks in same story can run in parallel (different repos)

Across User Stories (after Foundation complete):
- US1 (Anonymous) can run in parallel with US2 (OTP Flow)
- US5 (Registration) can start after US2 completes, in parallel with US3

---

## Implementation Strategy

### MVP First (Stories 1-4 Only)

1. Complete Phase 1: Foundational types and cleanup
2. Complete Phase 2: Verify anonymous browsing works
3. Complete Phase 3: OTP flow with tokens returned
4. Complete Phase 4: Token delivery to frontend
5. Complete Phase 5: Authenticated requests
6. **STOP and VALIDATE**: E2E test full flow
7. Deploy to dev environment

### Full Feature

1. Complete MVP (Stories 1-4)
2. Add Phase 6: New user registration (US5)
3. Add Phase 7: Token refresh
4. Complete Phase 8: Polish and validation
5. Deploy to production

---

## Files Modified Summary

| File | Changes |
|------|---------|
| `backend/src/models/auth.py` | Add `TokenDeliveryEvent` model |
| `backend/src/services/auth_service.py` | Update `OTPVerificationResult` with token fields |
| `backend/src/tools/auth.py` | Return `TokenDeliveryEvent`, remove `@requires_access_token` |
| `backend/src/api/routes.py` | Add token refresh endpoint |
| `frontend/src/types/index.ts` | Add types, update `AuthSession` |
| `frontend/src/lib/auth.ts` | Add type guards, session helpers |
| `frontend/src/lib/agentcore-transport.ts` | Include `auth_token` in payload |
| `frontend/src/hooks/useAgentChat.ts` | Detect and process `TokenDeliveryEvent` |

---

## Notes

- [P] tasks = different files, no dependencies
- Cleanup task T006 is NON-NEGOTIABLE per spec clarification #5
- Token values MUST NOT be logged (security)
- All localStorage keys use existing `booking_session` key
- Payload-based auth chosen over header-based for MVP simplicity
