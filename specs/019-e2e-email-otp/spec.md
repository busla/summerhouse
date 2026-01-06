# Feature Specification: E2E Test Support for Cognito Email OTP

**Feature Branch**: `019-e2e-email-otp`
**Created**: 2026-01-06
**Status**: Draft
**Input**: User description: "The email OTP signup/signin is currently broken because I haven't figured out a way for the e2e tests to use email sent confirmation code to test the actual user flow. It's currently hacked together by using the cognito password auth to get a user session and then skip the Guest detail view. Your task is to find a way for the e2e tests to receive the sent code and use it in the tests so that the tests use the same pattern as a regular user."

## Problem Statement

The current E2E testing approach bypasses the production authentication flow by:
1. Using Cognito's `ALLOW_USER_PASSWORD_AUTH` flow instead of the production `EMAIL_OTP` flow
2. Injecting mock tokens via `window.__MOCK_AUTH__` to skip actual OTP verification
3. Skipping the Guest Details step in the booking flow

This creates a gap between what tests verify and what users actually experience. The tests don't exercise:
- The OTP email sending mechanism
- The OTP entry UI and validation
- The complete 4-step booking flow as users experience it

## User Scenarios & Testing *(mandatory)*

### User Story 1 - E2E Test Retrieves OTP Code (Priority: P1)

An E2E test initiates the authentication flow by entering a customer's email, then retrieves the OTP code that Cognito would have sent, and uses it to complete verification—mirroring the exact flow a real user would follow.

**Why this priority**: This is the core capability that enables authentic E2E testing. Without it, no other improvements to test fidelity are possible.

**Independent Test**: Can be fully tested by running a single Playwright test that completes the full auth step without mocking, verifying that the user reaches the Guest Details step with a valid session.

**Acceptance Scenarios**:

1. **Given** an E2E test environment with OTP interception enabled, **When** the test triggers OTP verification for a test email address, **Then** the test can retrieve the generated OTP code within 5 seconds without checking email.

2. **Given** an OTP code has been generated for a test email, **When** the test enters the OTP code in the verification UI, **Then** the user is authenticated and redirected to the next step.

3. **Given** the test completes OTP verification, **When** checking the session state, **Then** valid Cognito tokens are present (not mocked tokens).

---

### User Story 2 - Full Booking Flow with Real Auth (Priority: P2)

An E2E test completes the entire 4-step booking flow (Date Selection → Auth/OTP → Guest Details → Payment) using the same authentication mechanism as production users.

**Why this priority**: Once OTP retrieval works, the full flow should be verified to ensure no regressions in the complete user journey.

**Independent Test**: Can be tested by running a complete booking E2E test from date selection through to Stripe checkout initiation.

**Acceptance Scenarios**:

1. **Given** a test user selecting dates, **When** they proceed through all 4 steps using real OTP verification, **Then** each step completes successfully without mocked authentication.

2. **Given** a user completes OTP verification, **When** they view the Guest Details form, **Then** their email is pre-populated from the auth step.

3. **Given** a user completes all steps, **When** they reach payment, **Then** the reservation is created with proper customer association.

---

### User Story 3 - OTP Code Resend Flow (Priority: P3)

An E2E test verifies the "Resend Code" functionality by requesting a new OTP and using the updated code.

**Why this priority**: Resend is a secondary flow that users encounter when the first OTP expires or isn't received.

**Independent Test**: Can be tested by initiating OTP, waiting, clicking resend, and using the new code.

**Acceptance Scenarios**:

1. **Given** an OTP has been sent and the user clicks "Resend Code", **When** a new OTP is generated, **Then** the test can retrieve the new code and the previous code is invalidated.

2. **Given** multiple resend attempts, **When** checking rate limits, **Then** the system enforces appropriate throttling.

---

### Edge Cases

- What happens when a test retrieves an OTP that has expired? The test should fail with a clear error indicating the code expired.
- How does the system handle concurrent tests for the same email address? Each test should use unique email addresses or the latest OTP should be returned.
- What happens if OTP interception is accidentally enabled in production? The mechanism must only function in designated test environments.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST intercept OTP codes before they are emailed during Cognito authentication flows in test environments
- **FR-002**: System MUST store intercepted OTP codes in a retrievable location accessible to E2E tests
- **FR-003**: E2E tests MUST be able to retrieve the OTP code for a specific email address within 5 seconds of generation
- **FR-004**: System MUST only enable OTP interception in designated test environments (never in production)
- **FR-005**: OTP codes MUST be stored with their associated email address and timestamp for proper retrieval
- **FR-006**: System MUST support the complete 4-step booking flow without any mocked authentication
- **FR-007**: Stored OTP codes MUST have a time-to-live (TTL) to prevent accumulation of test data
- **FR-008**: System MUST handle the "Change Email" flow where a user restarts authentication with a different email
- **FR-009**: E2E test fixture MUST provide a helper function to retrieve the latest OTP for a given email

### Non-Functional Requirements

- **NFR-001**: OTP retrieval latency MUST be under 500ms for test efficiency
- **NFR-002**: OTP storage MUST be isolated per test environment to prevent cross-contamination
- **NFR-003**: The solution MUST NOT modify the production Cognito authentication flow
- **NFR-004**: Infrastructure changes MUST be deployable via Terraform following existing patterns

### Key Entities

- **OTP Record**: Represents an intercepted verification code
  - Email address (the recipient)
  - OTP code (6-digit string)
  - Timestamp (when generated)
  - TTL (auto-expiration)
  - Environment identifier

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: E2E tests complete the full 4-step booking flow using real OTP verification with 95% reliability
- **SC-002**: OTP code retrieval completes in under 500ms for 99% of requests
- **SC-003**: Zero OTP interception functionality is accessible in production environments
- **SC-004**: E2E test suite execution time increases by no more than 30 seconds compared to the mocked approach
- **SC-005**: The `window.__MOCK_AUTH__` workaround can be removed from the test suite after this feature ships

## Technical Approach Options

### Option A: Custom Message Lambda Trigger (Recommended)

A Lambda function attached to Cognito's "Custom Message" trigger intercepts OTP codes before email dispatch. The Lambda:
1. Checks if the environment is designated for testing
2. Stores the OTP code in DynamoDB with the email as the key
3. Returns the message to Cognito for normal email delivery (or suppresses it in test)

**Pros**: No external dependencies, instant retrieval, native AWS integration
**Cons**: Requires Lambda infrastructure, careful environment isolation

### Option B: SES Email Receiving

Configure SES to receive emails for test addresses, store them in S3, and parse the OTP from email content.

**Pros**: Tests actual email delivery end-to-end
**Cons**: Requires domain configuration for receiving, slower, more complex

### Option C: Third-Party Test Email Service (e.g., Mailosaur)

Use a dedicated test email service that provides API access to received emails.

**Pros**: Battle-tested, professional support, tests real email
**Cons**: External dependency, recurring cost, API rate limits

## Assumptions

- The test environment is identifiable (e.g., via environment variable, stage name, or domain)
- DynamoDB is an acceptable storage mechanism for test OTP codes (already used by the project)
- E2E tests run in CI/CD environments with AWS credentials that can access the OTP storage
- The Cognito User Pool supports Custom Message Lambda triggers (requires ESSENTIALS tier or higher)
- Test email addresses follow a pattern that can be identified (e.g., `*+test@domain.com` or specific test domain)

## Out of Scope

- Modifications to the production authentication flow
- SMS OTP support (project uses email only)
- Load testing of the OTP mechanism
- Multi-region OTP storage
