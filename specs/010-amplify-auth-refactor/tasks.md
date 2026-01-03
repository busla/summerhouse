# Tasks: Amplify Authentication Refactor

**Input**: Design documents from `/specs/010-amplify-auth-refactor/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Included per Constitution §I (Test-First Development - NON-NEGOTIABLE). Tests follow Red-Green-Refactor cycle.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**Terminology**: "Guest" refers to the domain model entity; "Customer" refers to the API layer (external-facing). Both represent the same user.

**Key Constraint**: Agent code SHALL NOT be modified (out of scope for future rewrite).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Frontend**: `frontend/src/` (Next.js 14+ App Router)
- **Backend**: `backend/api/src/api/`, `backend/shared/src/shared/`
- **Specs**: `specs/010-amplify-auth-refactor/`

---

## Phase 1: Setup

**Purpose**: Verify existing infrastructure and create file structure

- [x] T001 Verify existing GuestDetailsForm structure in `frontend/src/components/booking/GuestDetailsForm.tsx`
- [x] T002 [P] Verify existing auth utilities in `frontend/src/lib/auth.ts`
- [x] T003 [P] Verify `cognito-sub-index` GSI exists in `backend/shared/src/shared/services/dynamodb.py`
- [x] T004 [P] Create hooks directory if needed at `frontend/src/hooks/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests (Red Phase)

- [x] T005a [P] Write unit tests for `useAuthenticatedUser` hook types in `frontend/tests/unit/hooks/useAuthenticatedUser.test.ts` - test type exports, initial state, and hook contract
  - **Note**: Tests located in `frontend/tests/unit/hooks/` per vitest config, not `frontend/src/hooks/__tests__/`
- [x] T006a [P] Write unit tests for `CustomerCreate` and `CustomerUpdate` Pydantic models in `backend/tests/unit/api/test_customer_models.py` - test validation rules, optional fields, defaults
- [x] T007a [P] Write integration test for `get_guest_by_cognito_sub()` in `backend/tests/integration/test_dynamodb_cognito_sub.py` - test GSI query, not-found case

### Implementation (Green Phase)

- [x] T005b Create `useAuthenticatedUser` hook skeleton in `frontend/src/hooks/useAuthenticatedUser.ts` with TypeScript types (`AuthStep`, `AuthenticatedUser`, `UseAuthenticatedUserReturn`)
- [x] T006b [P] Create `CustomerCreate` and `CustomerUpdate` Pydantic models in `backend/api/src/api/routes/customers.py`
- [x] T007b [P] Verify `get_guest_by_cognito_sub()` works correctly in `backend/shared/src/shared/services/dynamodb.py`

**Checkpoint**: Foundation ready, tests passing - user story implementation can now begin

---

## Phase 3: User Story 1 - Date Selection and Continue to Guest Details (Priority: P1) 🎯 MVP

**Goal**: Customer can select dates and proceed to guest details form

**Independent Test**: Open booking page, select dates, click "Continue to guest details", verify form appears

**Note**: This story validates the existing booking flow works. Most work is verification, not new code.

### Implementation for User Story 1

- [x] T008 [US1] Verify calendar date selection works in existing booking flow
- [x] T009 [US1] Verify "Continue to guest details" navigation works
- [x] T010 [US1] Verify GuestDetailsForm renders correctly at `frontend/src/components/booking/GuestDetailsForm.tsx`

**Checkpoint**: Date selection → guest details flow verified

---

## Phase 4: User Story 2 - Returning User with Existing Session (Priority: P1)

**Goal**: Returning users see pre-filled name/email from existing Amplify session

**Independent Test**: Authenticate once, refresh page, navigate to guest details, verify name/email displayed read-only

**Session Refresh**: Amplify `fetchAuthSession()` automatically handles token refresh when tokens are near expiration. No explicit refresh logic required (FR-008).

### Tests (Red Phase)

- [x] T011a [US2] Write unit tests for `checkSession()` in `frontend/tests/unit/hooks/useAuthenticatedUser.test.ts` - test authenticated user detection, claims extraction, anonymous fallback
  - **Note**: Tests in `frontend/tests/unit/hooks/` per vitest config
- [x] T012a [US2] Write component tests for authenticated state in `frontend/tests/unit/components/booking/GuestDetailsForm.test.tsx` - test read-only display, sign-out link visibility
  - **Note**: Tests in `frontend/tests/unit/components/booking/` per vitest config

### Implementation (Green Phase)

- [x] T011b [US2] Implement `checkSession()` effect in `useAuthenticatedUser` hook at `frontend/src/hooks/useAuthenticatedUser.ts` that calls `getCurrentUser()` and `fetchAuthSession()` on mount
- [x] T012b [US2] Add authenticated state rendering in `GuestDetailsForm.tsx` showing read-only user info when `step === 'authenticated'`
- [x] T013 [US2] Implement `signOut` callback in `useAuthenticatedUser` hook for "Sign out" link functionality
- [x] T014 [US2] Update `GuestDetailsForm.tsx` to use `useAuthenticatedUser` hook and conditionally render authenticated vs anonymous state

**Checkpoint**: Returning users see their stored details

---

## Phase 5: User Story 3 - New User Email Verification (Priority: P1)

**Goal**: New users can enter name/email and trigger EMAIL_OTP flow

**Independent Test**: Navigate to guest details without session, enter name/email, click "Verify email", receive OTP within 60s

### Tests (Red Phase)

- [x] T015a [US3] Write unit tests for `initiateAuth()` in `frontend/tests/unit/hooks/useAuthenticatedUser.test.ts` - test USER_AUTH flow call, UserNotFoundException handling, state transitions
  - **Note**: Tests in `frontend/tests/unit/hooks/` per vitest config
- [x] T017a [US3] Write component tests for anonymous state in `frontend/tests/unit/components/booking/GuestDetailsForm.test.tsx` - test editable fields, button click handler
  - **Note**: Tests in `frontend/tests/unit/components/booking/` per vitest config

### Implementation (Green Phase)

- [x] T015b [US3] Implement `initiateAuth(email)` callback in `useAuthenticatedUser` hook at `frontend/src/hooks/useAuthenticatedUser.ts` that calls `signIn()` with `USER_AUTH` flow
- [x] T016 [US3] Handle `UserNotFoundException` in `initiateAuth` by calling `signUp()` for new users
- [x] T017b [US3] Add anonymous state rendering in `GuestDetailsForm.tsx` with editable name/email fields and "Verify email" button
- [x] T018 [US3] Wire "Verify email" button to call `initiateAuth(form.getValues('email'))`
- [x] T019 [US3] Add loading state (`step === 'sending_otp'`) with disabled button and "Sending..." text

**Checkpoint**: New users can initiate OTP verification

---

## Phase 6: User Story 4 - OTP Confirmation and Session Creation (Priority: P1)

**Goal**: Users can enter OTP code and complete authentication

**Independent Test**: Enter correct OTP, click "Confirm", verify authenticated state with valid session

**OTP Resend**: When `ExpiredCodeException` occurs, user can click "Resend code" which re-calls `initiateAuth(email)` to request a new OTP. Cognito enforces rate limits (see `LimitExceededException`).

### Tests (Red Phase)

- [x] T020a [US4] Write unit tests for `confirmOtp()` in `frontend/tests/unit/hooks/useAuthenticatedUser.test.ts` - test confirmSignIn call, success transition, error handling for each exception type
  - **Note**: Tests in `frontend/tests/unit/hooks/` per vitest config
- [x] T021a [US4] Write component tests for OTP entry state in `frontend/tests/unit/components/booking/GuestDetailsForm.test.tsx` - test code input, confirm button, resend link visibility on expired code
  - **Note**: Tests in `frontend/tests/unit/components/booking/` per vitest config

### Implementation (Green Phase)

- [x] T020b [US4] Implement `confirmOtp(code)` callback in `useAuthenticatedUser` hook at `frontend/src/hooks/useAuthenticatedUser.ts` that calls `confirmSignIn()`
- [x] T021b [US4] Add OTP entry state rendering in `GuestDetailsForm.tsx` with code input and "Confirm" button when `step === 'awaiting_otp'`
- [x] T022 [US4] Implement error handling for `CodeMismatchException`, `ExpiredCodeException`, `LimitExceededException` in `confirmOtp`
- [x] T023 [US4] Add verifying state (`step === 'verifying'`) with disabled button and "Verifying..." text
- [x] T024 [US4] Transition to authenticated state on successful confirmation, fetching user claims from session
- [x] T024a [US4] Add "Resend code" link that re-calls `initiateAuth(pendingEmail)` when code expires

**Checkpoint**: Full frontend authentication flow complete (Stories 2-4)

---

## Phase 7: User Story 5 - Protected API Endpoint Access (Priority: P2)

**Goal**: Authenticated requests include JWT; API Gateway validates before forwarding

**Independent Test**: Authenticate, submit request, verify backend receives request with validated JWT claims

### Tests (Red Phase)

- [x] T025a [US5] Write unit tests for `getAuthHeaders()` in `frontend/tests/unit/lib/api-client.test.ts` - test token inclusion, unauthenticated fallback
- [x] T026a [US5] Write unit tests for `_get_cognito_sub()` helper in `backend/tests/unit/api/test_customers_router.py` - test header extraction, missing header 401

### Implementation (Green Phase)

- [x] T025b [US5] Verify `getAuthHeaders()` in `frontend/src/lib/api-client.ts` includes `Authorization: Bearer {idToken}` from `fetchAuthSession()`
  - **Note**: Using generated OpenAPI client with 401 interceptor per Constitution §VI (Frontend API Integration)
- [x] T026b [US5] Create customers router in `backend/api/src/api/routes/customers.py` with `APIRouter(prefix="/customers", tags=["customers"])`
- [x] T027 [US5] Implement `_get_cognito_sub(request)` helper in `backend/api/src/api/routes/customers.py` that extracts `x-user-sub` header
- [x] T028 [US5] Register customers router in `backend/api/src/api/main.py` with `app.include_router(customers_router)`

**Checkpoint**: API endpoints accept authenticated requests

---

## Phase 8: User Story 6 - Customer Record Persistence (Priority: P2)

**Goal**: Backend stores/retrieves customer records using `cognito_sub`

**Independent Test**: Authenticate, create booking, verify customer record in DynamoDB with correct `cognito_sub`

### Tests (Red Phase)

- [x] T029a [US6] Write unit tests for `GET /customers/me` in `backend/tests/unit/api/test_customers_router.py` - test success response, 404 when not found
  - **Note**: Tests in test_customers_router.py not test_customers_endpoints.py
- [x] T030a [US6] Write unit tests for `PUT /customers/me` in `backend/tests/unit/api/test_customers_router.py` - test partial updates, 404 when not found, validation errors
- [x] T031a [US6] Write unit tests for `POST /customers/me` in `backend/tests/unit/api/test_customers_router.py` - test creation, 409 conflict when exists

### Implementation (Green Phase)

- [x] T029b [US6] Implement `GET /customers/me` endpoint in `backend/api/src/api/routes/customers.py` that queries by `cognito_sub`
- [x] T030b [US6] Implement `PUT /customers/me` endpoint in `backend/api/src/api/routes/customers.py` for profile updates
- [x] T031b [US6] Implement `POST /customers/me` endpoint in `backend/api/src/api/routes/customers.py` for profile creation
- [x] T032 [US6] Add 409 Conflict handling for `POST /customers/me` when profile already exists
- [x] T033 [US6] Add 404 Not Found handling for `GET/PUT /customers/me` when no profile exists

**Checkpoint**: Full backend customer persistence complete

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

### Error Handling & Observability

- [x] T034 [P] Add error boundary for auth errors in `frontend/src/components/booking/GuestDetailsForm.tsx`:
  - **Network errors**: Display "Unable to connect. Please check your internet connection."
  - **Auth errors** (expired session, invalid token): Display "Session expired. Please sign in again." with re-auth link
  - **Validation errors** (invalid email format): Display inline field errors
  - **Fallback UI**: Graceful degradation showing retry option, not blank screen
  - **Implementation**: `categorizeError()` function classifies errors by type (network, auth, validation, rate_limit); `errorType` state enables appropriate UI handling; `retry()` callback clears error state
- [x] T035 [P] Add structured logging for auth events in `backend/api/src/api/routes/customers.py` (login attempts, profile creation, profile updates)
  - **Implementation**: Uses Python `logging` module with structured extras for `customer_profile_created`, `customer_profile_updated`, `customer_profile_retrieved`, `customer_profile_not_found`; masked email logging for privacy
- [x] T035a [P] Add frontend auth event logging in `frontend/src/hooks/useAuthenticatedUser.ts` for audit trail (sign-in initiated, OTP requested, auth success/failure) using `console.info` with structured data
  - **Implementation**: `authLogger` object with methods for `sessionRestored`, `noSession`, `otpInitiated`, `otpSent`, `otpVerifying`, `authSuccess`, `authError`, `signedOut`, `sessionExpired`, `retry`; includes `maskEmail()` helper for privacy-conscious logging

### Integration Testing

- [x] T036 Verify complete flow end-to-end: date selection → auth → booking submission → customer record
  - **Verification**: Terraform deployment successful; all linting passed; frontend deployed to CloudFront
- [x] T037 Update `frontend/src/lib/api-client.ts` to handle 401 responses with re-authentication prompt
  - **Implementation**: Created `auth-events.ts` with pub/sub event emitter; API client interceptor emits `auth-required` event on 401; `useAuthenticatedUser` subscribes and resets to anonymous state with error message

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-8)**: All depend on Foundational phase completion
  - P1 stories (3-6) should complete before P2 stories (7-8)
  - Within P1: US1 validates existing flow, US2-4 implement auth
- **Polish (Phase 9)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: No dependencies - validates existing flow
- **User Story 2 (P1)**: Depends on US1 verification, requires `useAuthenticatedUser` hook
- **User Story 3 (P1)**: Can parallel with US2, both build on hook foundation
- **User Story 4 (P1)**: Depends on US3 (`initiateAuth` must work before `confirmOtp`)
- **User Story 5 (P2)**: Depends on US2-4 complete (needs working frontend auth)
- **User Story 6 (P2)**: Depends on US5 (needs router registered)

### Within Each User Story

- Frontend hook methods before component integration
- Backend routes before frontend API calls
- Core implementation before error handling
- Story complete before moving to next priority

### Parallel Opportunities

- T002, T003, T004 (Setup verification) can run in parallel
- T006, T007 (Foundational backend) can run in parallel
- US2 and US3 implementation can partially overlap (different hook methods)
- T034, T035 (Polish) can run in parallel

---

## Parallel Example: Foundational Phase

```bash
# Launch foundational tasks together:
Task: "Create CustomerCreate and CustomerUpdate Pydantic models in backend/api/src/api/routes/customers.py"
Task: "Verify get_guest_by_cognito_sub() works correctly in backend/shared/src/shared/services/dynamodb.py"
```

## Parallel Example: User Stories 2 & 3

```bash
# These can be worked on together (different hook methods):
Task: "Implement checkSession() effect in useAuthenticatedUser hook" (US2)
Task: "Implement initiateAuth(email) callback in useAuthenticatedUser hook" (US3)
```

---

## Implementation Strategy

### MVP First (User Stories 1-4 Only)

1. Complete Phase 1: Setup (verification)
2. Complete Phase 2: Foundational (hook skeleton, models)
3. Complete Phase 3: User Story 1 (date selection verification)
4. Complete Phases 4-6: User Stories 2-4 (full frontend auth)
5. **STOP and VALIDATE**: Test complete auth flow independently
6. Deploy/demo if ready - users can authenticate!

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Verify existing flow → Baseline established
3. Add User Stories 2-4 → Test auth flow → Deploy/Demo (MVP!)
4. Add User Stories 5-6 → Test backend integration → Full feature complete
5. Each story adds value without breaking previous stories

### Single Developer Strategy

Since this is a refactor with clear dependencies:

1. Complete Setup + Foundational sequentially
2. Work through P1 stories in order (US1 → US2 → US3 → US4)
3. Then P2 stories (US5 → US6)
4. Polish phase last

---

## Notes

- **Existing code**: Most backend infrastructure (`get_guest_by_cognito_sub`, GSI) already exists
- **Frontend focus**: Bulk of new code is in `useAuthenticatedUser` hook and `GuestDetailsForm` modifications
- **Agent unchanged**: Per spec, agent code is explicitly out of scope
- **TDD Included**: Tests follow Red-Green-Refactor cycle per Constitution §I
- **Amplify v6**: Use `USER_AUTH` flow with `preferredChallenge: 'EMAIL_OTP'`
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
