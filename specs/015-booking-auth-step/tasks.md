# Tasks: Booking Authentication Step

**Input**: Design documents from `/specs/015-booking-auth-step/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/README.md, quickstart.md

**Tests**: E2E tests are REQUIRED per FR-019. Unit tests included for critical components.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

---

## ⚠️ KNOWN ISSUE: OTP Authentication Broken

**Status**: OTP flow is not working due to Cognito USER_AUTH configuration issues.

**Error**: "The selected challenge is not available" when attempting EMAIL_OTP authentication.

**Root Cause**: Cognito User Pool USER_AUTH flow with EMAIL_OTP is not properly configured or enabled.

**Resolution**: Will be fixed in a **new feature** (016-fix-cognito-otp or similar). The UI components and flow logic implemented here are correct - only the Cognito backend configuration needs adjustment.

**Workaround for E2E tests**: Password-based authentication works correctly. E2E tests use `auth.fixture.ts` with password auth.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Frontend**: `frontend/src/`, `frontend/tests/`
- **Backend**: No backend changes required (existing API sufficient)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install dependencies and create project structure

- [x] T001 Install shadcn/ui `input-otp` component via `npx shadcn@latest add input-otp` in `frontend/`
- [x] T002 [P] Verify input-otp installation by checking `frontend/src/components/ui/input-otp.tsx` exists
- [x] T003 [P] Verify `input-otp` dependency added to `frontend/package.json`

**Checkpoint**: shadcn/ui input-otp component available for use

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core schemas and state that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Create Zod validation schema file `frontend/src/lib/schemas/auth-step.schema.ts` with `authStepSchema` (name, email, phone) and `otpSchema` (6-digit code)
- [x] T005 [P] Add `AuthStepFormData` and `OtpFormData` type exports to `frontend/src/lib/schemas/auth-step.schema.ts`
- [x] T006 Extend `BookingStep` type in `frontend/src/app/book/page.tsx` to include `'auth'` step: `'dates' | 'auth' | 'guest' | 'payment' | 'confirmation'`
- [x] T007 Extend `BookingFormState` interface in `frontend/src/app/book/page.tsx` with auth fields: `customerName`, `customerEmail`, `customerPhone`, `authStep`, `customerId`
- [x] T008 [P] Create `SimplifiedGuestDetails` type in `frontend/src/lib/schemas/booking-form.schema.ts` (guestCount, specialRequests only)
- [x] T009 Update `useFormPersistence` hook usage in BookPage to handle new auth fields serialization

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - New Customer Email Verification (Priority: P1) MVP

**Goal**: New customers can verify their email via OTP and create a customer profile

**Independent Test**: Navigate to `/book`, select dates, enter user details, verify OTP UI appears, confirm creates customer

### Tests for User Story 1 (REQUIRED per FR-019)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T010 [P] [US1] Create unit test file `frontend/tests/unit/components/booking/AuthStep.test.tsx` with test cases for: form validation, auth state transitions, OTP input behavior, error handling
- [x] T011 [P] [US1] Create E2E test file `frontend/tests/e2e/auth-step.spec.ts` with unauthenticated flow test: form → fill fields → click "Verify Email" → OTP UI appears

### Implementation for User Story 1

- [x] T012 [US1] Create `AuthStep` component in `frontend/src/components/booking/AuthStep.tsx` with props: `defaultValues`, `onAuthenticated`, `onBack`, `onChange`
- [x] T013 [US1] Implement name/email/phone form in AuthStep using react-hook-form + zodResolver with `authStepSchema`
- [x] T014 [US1] Implement "Verify Email" button that calls `useAuthenticatedUser.initiateAuth(email)` ⚠️ OTP broken - see known issue
- [x] T015 [US1] Implement OTP input section using `InputOTP`, `InputOTPGroup`, `InputOTPSlot` from shadcn/ui (6 boxes with auto-advance)
- [x] T016 [US1] Display email address OTP was sent to per FR-009
- [x] T017 [US1] Implement "Confirm" button that calls `useAuthenticatedUser.confirmOtp(code)` ⚠️ OTP broken - see known issue
- [x] T018 [US1] Implement customer profile creation via `customersPostCustomersMe` from generated API client after successful OTP verification (JWT token automatically included by client per FR-012)
- [x] T019 [US1] Handle 409 Conflict response gracefully per FR-020 (proceed without error if customer exists)
- [x] T020 [US1] Implement error display with categorization (network, auth, validation, rate_limit) per FR-016
- [x] T021 [US1] Implement "Retry" action for network errors and "Resend code" for expired codes per FR-017
- [x] T022 [US1] Integrate AuthStep into BookPage: render between DatePicker and GuestDetailsForm when `currentStep === 'auth'`
- [x] T023 [US1] Update step indicator in BookPage to show 4 steps: Dates > Verify Identity > Guest Details > Payment per FR-002
- [x] T024 [US1] Wire up AuthStep `onAuthenticated` callback to set `customerId` and advance to guest step
- [x] T025 [US1] Wire up AuthStep `onChange` callback to persist form values to BookingFormState

**Checkpoint**: New customers can complete full authentication flow and proceed to guest details ⚠️ OTP broken - UI complete but Cognito EMAIL_OTP not working

---

## Phase 4: User Story 2 - Returning Customer Recognition (Priority: P2)

**Goal**: Returning customers can re-authenticate via OTP without re-entering details; name is pre-filled

**Independent Test**: Complete booking, start new booking with same email, verify returning flow and pre-fill

### Tests for User Story 2

- [ ] T026 [P] [US2] Add E2E test case to `frontend/tests/e2e/auth-step.spec.ts`: returning customer flow - email triggers OTP without signup, name pre-filled on guest step

### Implementation for User Story 2

- [ ] T027 [US2] Ensure `useAuthenticatedUser.initiateAuth` handles existing Cognito users (signIn flow instead of signUp)
- [ ] T028 [US2] After successful auth, fetch existing customer profile if 409 response, extract name for pre-fill
- [ ] T029 [US2] Pass customer name from auth step to guest details for pre-fill display

**Checkpoint**: Returning customers experience streamlined re-authentication

---

## Phase 5: User Story 3 - Already Authenticated Customer Bypass (Priority: P3)

**Goal**: Authenticated users skip the auth step entirely and see pre-filled details

**Independent Test**: Pre-set auth session, navigate to `/book`, select dates, verify auth step is skipped

### Tests for User Story 3 (REQUIRED per FR-019)

- [ ] T030 [P] [US3] Add E2E test case to `frontend/tests/e2e/auth-step.spec.ts` using `auth.fixture.ts`: authenticated user skips auth step after date selection
- [ ] T031 [P] [US3] Add E2E test case: authenticated user sees email/name pre-filled and read-only on guest details

### Implementation for User Story 3

- [ ] T032 [US3] In BookPage, check authentication state on mount via `useAuthenticatedUser`
- [ ] T033 [US3] If user is authenticated when navigating from dates step, skip directly to guest step per FR-014
- [ ] T034 [US3] Pre-fill email and name from authenticated user session on guest details form
- [ ] T035 [US3] Make email and name fields read-only for authenticated users per User Story 3, Scenario 2

**Checkpoint**: Authenticated users bypass authentication step entirely

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Cleanup legacy code, fix bugs, update existing tests

### Bug Fixes (from research.md)

- [ ] T036 [P] Fix Bug 1: Clear OTP code between attempts in AuthStep (not reusing old GuestDetailsForm code)
- [ ] T037 [P] Fix Bug 2: Update `useAuthenticatedUser.retry` to not reset to anonymous during OTP verification in `frontend/src/hooks/useAuthenticatedUser.ts`
- [ ] T038 [P] Fix Bug 4: Ensure pendingEmail is always current when resending OTP (handled by AuthStep owning email field)

### GuestDetailsForm Simplification (FR-018)

- [ ] T039 Simplify `frontend/src/components/booking/GuestDetailsForm.tsx`: remove name, email, phone fields
- [ ] T040 Remove OTP UI and state from GuestDetailsForm
- [ ] T041 Remove `useAuthenticatedUser` integration from GuestDetailsForm (now handled by AuthStep)
- [ ] T042 Keep only guestCount selector (1-4) and specialRequests textarea in GuestDetailsForm
- [ ] T043 Update GuestDetailsForm props to receive customer info from parent (read-only display)

### Existing E2E Test Updates

- [ ] T044 Update `frontend/tests/e2e/direct-booking.spec.ts` to account for new auth step in booking flow
- [ ] T045 Ensure all existing booking flow tests pass with new 4-step flow

### Final Validation

- [ ] T046 Run full E2E test suite: `cd frontend && yarn test:e2e`
- [ ] T047 Run unit tests: `cd frontend && yarn test --run`
- [ ] T048 Manual verification: complete full booking flow as new customer
- [ ] T049 Manual verification: complete booking as authenticated user (skip auth step)
- [ ] T050 Verify form state persists across browser refresh at each step

**Checkpoint**: Feature complete, all tests passing, no regressions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3, 4, 5)**: All depend on Foundational phase completion
  - US1 (Phase 3) should complete first as MVP
  - US2 (Phase 4) can start after US1 (may reuse components)
  - US3 (Phase 5) can start after US1 (depends on auth step existing)
- **Polish (Phase 6)**: Can start after US1 complete; some tasks can run in parallel with US2/US3

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Depends on US1 completion (reuses AuthStep component)
- **User Story 3 (P3)**: Depends on US1 completion (auth step must exist to be skipped)

### Within Each User Story

- Tests (T010, T011, T026, T030, T031) MUST be written and FAIL before implementation
- Schema/types before components
- Core component before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks can complete quickly (just CLI commands)
- Foundational schema tasks (T004, T005, T008) can run in parallel
- Tests for each story can be written in parallel
- Phase 6 bug fixes (T036, T037, T038) can run in parallel
- Phase 6 GuestDetailsForm tasks (T039-T043) should be sequential

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (install input-otp)
2. Complete Phase 2: Foundational (schemas, types, state)
3. Complete Phase 3: User Story 1 (AuthStep component + BookPage integration)
4. **STOP and VALIDATE**: Test complete auth flow manually + E2E
5. Deploy/demo if ready - new customers can book!

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. User Story 1 → Test independently → Deploy (MVP!)
3. User Story 2 → Test independently → Deploy (better returning customer UX)
4. User Story 3 → Test independently → Deploy (authenticated user optimization)
5. Polish → Cleanup legacy code, ensure no regressions

### Test Commands

```bash
# Unit tests
cd frontend && yarn test --run

# E2E tests (local)
cd frontend && yarn test:e2e

# E2E tests (live site)
cd frontend && yarn test:e2e --project=live
```

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- E2E testing uses two-pronged approach per spec clarifications:
  - Unauthenticated: Test UI up to OTP submission only
  - Authenticated: Use `auth.fixture.ts` with password auth for bypass testing
- Bug 3 (Missing AuthErrorBoundary) skipped per research.md - AuthStep handles its own errors
- No backend changes required - existing `POST /customers/me` endpoint is sufficient
