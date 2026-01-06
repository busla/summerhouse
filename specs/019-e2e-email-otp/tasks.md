# Tasks: E2E Test Support for Cognito Email OTP

**Input**: Design documents from `/specs/019-e2e-email-otp/`
**Prerequisites**: plan.md, spec.md, data-model.md, quickstart.md, contracts/

**Tests**: Tests ARE included as this feature's core purpose is enabling E2E testing.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

---

## Status Summary

**Feature Status**: INCOMPLETE - Requires cleanup in new feature

### Completed
- Phase 1: Setup - All directories exist
- Phase 2: Lambda infrastructure deployed and working
- Phase 3 (US1): OTP helper implemented, retrieval works
- Phase 4 (US2): Partial - E2E tests created but have issues

### Issues Found (Need Cleanup in New Feature)
1. **OTP digit count mismatch**: Cognito EMAIL_OTP sends 6 digits, but UI was incorrectly changed to 8 slots
   - Fixed locally in `AuthStep.tsx` (6 slots) and `auth-step.schema.ts` (6 digits)
   - Fixed in tests: `booking-flow-with-otp.spec.ts` and `auth-step.spec.ts`
   - **NOT DEPLOYED** - Local changes need deployment to live site

2. **Frontend not auto-deploying**: `task tf:plan:dev` shows no changes because Terraform doesn't track `out/` content changes
   - Need manual S3 sync or Terraform apply with content hash triggers

3. **Test file `auth-step.spec.ts` had wrong expectations**: Expected 8 OTP slots, fixed to 6

---

## Phase 1: Setup (Project Structure)

**Purpose**: Create directory structure and project files

- [x] T001 [P] Create Lambda module directory `infrastructure/modules/otp-interceptor/`
- [x] T002 [P] Create Lambda source directory `backend/lambdas/otp-interceptor/`
- [x] T003 [P] Create E2E utils directory if not exists `frontend/tests/e2e/utils/`

---

## Phase 2: Foundational (Lambda Infrastructure)

**Purpose**: Deploy OTP Interceptor Lambda and wire Cognito trigger - MUST complete before any user story

### Lambda Source Code

- [x] T004 [P] Create Lambda handler `backend/lambdas/otp-interceptor/handler.py` per cognito-trigger-event.md contract
- [x] T005 [P] Create requirements.txt `backend/lambdas/otp-interceptor/requirements.txt` (boto3)
- [x] T006 [P] Create unit tests `backend/lambdas/otp-interceptor/tests/test_handler.py` with moto

### Terraform Module

- [x] T007 Create Lambda module `infrastructure/modules/otp-interceptor/main.tf` using terraform-aws-modules/lambda
- [x] T008 [P] Create module variables `infrastructure/modules/otp-interceptor/variables.tf`
- [x] T009 [P] Create module outputs `infrastructure/modules/otp-interceptor/outputs.tf`

### Environment Wiring

- [x] T010 Wire otp-interceptor module in `infrastructure/environments/dev/terragrunt.hcl`
- [x] T011 Add Custom Message trigger to Cognito in `infrastructure/modules/cognito-passwordless/main.tf`
- [x] T012 Deploy and verify Lambda trigger fires via CloudWatch logs (`task tf:apply:dev`)

**Checkpoint**: ✅ Lambda deployed, Cognito trigger configured, OTP codes appear in DynamoDB when test emails authenticate

---

## Phase 3: User Story 1 - E2E Test Retrieves OTP Code (Priority: P1) 🎯 MVP

**Goal**: E2E tests can retrieve OTP codes from DynamoDB and complete authentication without mocking

### Tests for User Story 1

- [x] T013 [US1] Create OTP retrieval integration test `frontend/tests/e2e/otp-retrieval.spec.ts`

### Implementation for User Story 1

- [x] T014 [US1] Implement otp-helper.ts `frontend/tests/e2e/utils/otp-helper.ts` per otp-helper-api.md contract
- [x] T015 [US1] Add OtpNotFoundError and OtpExpiredError error classes in otp-helper.ts
- [x] T016 [US1] Implement generateTestEmail() helper function in otp-helper.ts
- [x] T017 [US1] Implement clearOtpCode() cleanup function in otp-helper.ts
- [x] T018 [US1] Add AWS SDK DynamoDB client configuration with proper region handling

**Checkpoint**: ✅ OTP retrieval works - codes can be fetched from DynamoDB

---

## Phase 4: User Story 2 - Full Booking Flow with Real Auth (Priority: P2)

**Goal**: Complete 4-step booking flow (Date Selection → Auth/OTP → Guest Details → Payment) uses real OTP

### Tests for User Story 2

- [x] T019 [US2] Create full booking flow E2E test `frontend/tests/e2e/integration/booking-flow-with-otp.spec.ts`
  - **NOTE**: Test file created but fails due to deployment issue (live site has 8 OTP slots, not 6)

### Implementation for User Story 2

- [ ] T020 [US2] Update auth fixture `frontend/tests/e2e/fixtures/auth.fixture.ts` to use getOtpCode()
- [ ] T021 [US2] Remove `window.__MOCK_AUTH__` token injection from auth fixture
- [ ] T022 [US2] Update authenticateViaUI() to use otp-helper instead of manual entry
- [ ] T023 [US2] Add proper auth state persistence using real Cognito tokens
- [ ] T024 [US2] Verify Guest Details step is not skipped in updated flow

**Checkpoint**: ❌ BLOCKED - Frontend changes not deployed

---

## Phase 5: User Story 3 - OTP Code Resend Flow (Priority: P3)

**Goal**: E2E tests can verify the "Resend Code" functionality

### Tests for User Story 3

- [ ] T025 [US3] Create resend flow E2E test `frontend/tests/e2e/otp-resend.spec.ts`

### Implementation for User Story 3

- [ ] T026 [US3] Update Lambda handler to handle `CustomMessage_ResendCode` trigger source
- [ ] T027 [US3] Add createdAfter option usage in test to ignore stale codes
- [ ] T028 [US3] Verify OTP overwrite behavior (latest code wins per email)

**Checkpoint**: Not started

---

## Phase 6: Polish & Cleanup

**Purpose**: Remove legacy mock auth, documentation, final validation

- [ ] T029 [P] Remove `ALLOW_USER_PASSWORD_AUTH` from Cognito if no longer needed
- [ ] T030 [P] Delete any remaining `window.__MOCK_AUTH__` references
- [ ] T031 [P] Update E2E test documentation with new OTP flow
- [ ] T032 Add CI/CD environment variables `VERIFICATION_CODES_TABLE` and `AWS_REGION`
- [ ] T033 Run full E2E test suite to verify no regressions
- [ ] T034 Validate quickstart.md steps work end-to-end

---

## Cleanup Required (For New Feature)

### Priority 1: Deploy OTP digit fix
1. `AuthStep.tsx` - Changed to 6 OTP slots (local change, not deployed)
2. `auth-step.schema.ts` - OTP schema validates 6 digits (local change)
3. Deploy frontend to S3/CloudFront

### Priority 2: Fix test expectations
1. `auth-step.spec.ts` - Fixed to expect 6 OTP slots (local change)
2. `booking-flow-with-otp.spec.ts` - Fixed to expect 6 digits (local change)

### Priority 3: Verify end-to-end
1. Run `yarn test:e2e:live --grep "Booking Flow with OTP"` after deployment
2. Verify all 9 tests pass

---

## Key Findings

### Cognito EMAIL_OTP sends 6-digit codes (NOT 8)
- Confirmed by Lambda handler documentation: "Decrypted 6-digit OTP code"
- Confirmed by actual test run: received code "896531" (6 digits)
- UI was incorrectly showing 8 input slots

### Test name validation
- Test customer name cannot contain digits (regex: `/^[a-zA-ZÀ-ÿ\s'-]+$/`)
- Changed from "E2E Test User" to "Test User"

### InputOTP component behavior
- Clicking on OTP slot divs gets intercepted by hidden input element
- Need to click the input directly or use keyboard.type() after focusing

---

## Notes

- Lambda MUST check `ENVIRONMENT=dev` before storing OTP (security safeguard)
- Test emails MUST match pattern: `test+{anything}@summerhouse.com`
- OTP TTL: 5 minutes via DynamoDB TTL attribute
- All tasks depend on existing `verification_codes` DynamoDB table (no schema changes needed)
- E2E tests need AWS credentials with `dynamodb:GetItem` permission
