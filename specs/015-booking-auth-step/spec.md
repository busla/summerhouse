# Feature Specification: Booking Authentication Step

**Feature Branch**: `015-booking-auth-step`
**Created**: 2025-01-05
**Status**: Draft
**Input**: User description: "Improve the booking flow for unauthenticated customers by adding a dedicated authentication step after date selection. The step collects name, email, and phone number, then verifies email via Cognito OTP. Upon successful verification, a customer profile is created via the FastAPI API. The flow must use Amplify for auth and update Playwright tests."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - New Customer Email Verification (Priority: P1)

A new customer who has selected their booking dates needs to verify their identity before proceeding to guest details. They enter their name, email, and phone number, then verify their email via a one-time passcode sent to their inbox.

**Why this priority**: This is the core flow - authentication is required before booking can proceed. Without this, the entire feature fails.

**Independent Test**: Can be fully tested by navigating to `/book`, selecting dates, entering user details, submitting, and verifying OTP entry UI appears. Delivers verified customer identity.

**Acceptance Scenarios**:

1. **Given** a customer on the date selection step with valid dates selected, **When** they click "Continue", **Then** they are taken to the authentication step with name, email, and phone fields.

2. **Given** a customer on the authentication step with all fields filled, **When** they click "Verify Email", **Then** a verification code is sent to their email and a code input field appears.

3. **Given** a customer has received a verification code, **When** they enter the correct 6-digit code and click "Confirm", **Then** they are authenticated, a customer profile is created via API, and they proceed to the guest details step.

4. **Given** a customer enters an invalid verification code, **When** they click "Confirm", **Then** an error message is displayed and they can retry entering the code.

---

### User Story 2 - Returning Customer Recognition (Priority: P2)

A customer who has previously verified their email returns to make another booking. The system recognizes their email and allows them to re-authenticate via OTP without re-entering other details.

**Why this priority**: Enhances user experience for repeat customers but is not critical for first-time booking flow.

**Independent Test**: Can be tested by first completing a booking with email verification, then starting a new booking with the same email to verify the returning flow.

**Acceptance Scenarios**:

1. **Given** a customer enters an email that has been previously verified (existing Cognito user), **When** they click "Verify Email", **Then** a verification code is sent (no new signup required) and their existing customer profile is used.

2. **Given** a returning customer completes email verification, **When** they proceed to guest details, **Then** their name from the previous profile is pre-filled.

---

### User Story 3 - Already Authenticated Customer Bypass (Priority: P3)

A customer who is already authenticated (has valid session) should skip the authentication step entirely.

**Why this priority**: Edge case optimization - most booking flows start unauthenticated, but this prevents friction for logged-in users.

**Independent Test**: Can be tested by pre-setting auth session, navigating to `/book`, and verifying the authentication step is skipped.

**Acceptance Scenarios**:

1. **Given** a customer has an active authenticated session, **When** they select dates and click "Continue", **Then** they skip the authentication step and go directly to guest details.

2. **Given** an authenticated customer on the guest details step, **When** they view the form, **Then** their email and name are pre-filled and read-only.

---

### Edge Cases

- What happens when the verification code expires? System shows "Code expired" error with a "Resend code" button.
- What happens when the customer enters wrong code 3+ times? System shows rate limit error and asks to wait before retrying (rate limit timing managed by Cognito).
- What happens if the API call to create customer profile fails after successful Cognito auth? System shows error, allows retry without re-verifying email (session is valid).
- What happens if the customer navigates back from guest details to authentication step? Their previously entered data should be preserved.
- What happens if network connection is lost during verification? System shows network error with retry option.
- What happens if the customer closes the browser during OTP entry and returns? Form state should be persisted, but they may need to request a new code.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display a new "Verify Identity" step in the booking flow between date selection and guest details.
- **FR-002**: System MUST update the step indicator to show 4 steps: Dates > Verify Identity > Guest Details > Payment.
- **FR-003**: The authentication step MUST collect three fields: Full Name, Email Address, and Phone Number.
- **FR-004**: The Name field MUST be required with 2-100 character validation.
- **FR-005**: The Email field MUST be required with valid email format validation.
- **FR-006**: The Phone field MUST be required with 7-20 character validation, supporting international formats.
- **FR-007**: System MUST display a "Verify Email" button that initiates Amplify EMAIL_OTP authentication flow.
- **FR-008**: After clicking "Verify Email", system MUST show a 6-digit OTP input using shadcn/ui `input-otp` component (6 separate boxes with auto-advance) and a "Confirm" button.
- **FR-009**: System MUST display the email address the code was sent to in the OTP entry section.
- **FR-010**: System MUST validate the 6-digit verification code via Amplify `confirmSignIn`.
- **FR-011**: Upon successful verification, system MUST create a customer profile via `POST /customers/me` API endpoint.
- **FR-012**: The API call MUST include the authenticated user's JWT token for authorization.
- **FR-013**: The API call MUST include name and phone from the form; email comes from JWT claims.
- **FR-014**: System MUST allow authenticated users to skip the authentication step entirely.
- **FR-015**: System MUST persist form state across browser refresh using existing `useFormPersistence` hook pattern.
- **FR-016**: System MUST display appropriate error messages categorized by type: network, auth, validation, rate_limit. Specific message text defined at implementation time based on error context.
- **FR-017**: System MUST provide "Retry" action for network errors and "Resend code" for expired codes.
- **FR-018**: Guest details step MUST be simplified to remove the embedded authentication UI, keeping only guest count and special requests.
- **FR-019**: Playwright E2E tests MUST be updated to test the new authentication step flow.
- **FR-020**: System MUST handle the case where customer profile already exists (409 Conflict) gracefully by proceeding without error.
- **FR-021**: System MUST fix any existing bugs in the `useAuthenticatedUser` hook and OTP flow as part of extracting to the dedicated auth step.

### Key Entities

- **Customer**: Represents a verified user with `customer_id`, `email`, `cognito_sub`, `name`, `phone`, `preferred_language`, `email_verified`, `created_at`, `updated_at`.
- **BookingFormState**: Extended to include `currentStep` with new `'auth'` value and auth-related fields like `customerName`, `customerEmail`, `customerPhone`.
- **AuthStep**: State machine values: `'anonymous'`, `'sending_otp'`, `'awaiting_otp'`, `'verifying'`, `'authenticated'`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can complete the entire booking flow (dates > auth > guest details > payment) in under 5 minutes for new customers.
- **SC-002**: Returning customers who re-authenticate via OTP can reach guest details in under 2 minutes.
- **SC-003**: 95% of users who enter a valid verification code are successfully authenticated on first attempt.
- **SC-004**: Form data persists across page refresh with 100% data retention.
- **SC-005**: All error scenarios display user-friendly messages within 2 seconds of the error occurring.
- **SC-006**: Playwright test suite includes at least 5 new test cases covering the authentication step flow.
- **SC-007**: No regression in existing booking flow tests - all current tests continue to pass.
- **SC-008**: Customer profile is successfully created in the backend for 100% of newly verified users.

## Assumptions

- Cognito User Pool is already configured with EMAIL_OTP authentication flow (confirmed by existing implementation).
- The `POST /customers/me` API endpoint exists and accepts `name`, `phone`, and `preferred_language` fields (confirmed in codebase).
- Amplify is already configured in the frontend application (confirmed by existing `useAuthenticatedUser` hook).
- The existing `useFormPersistence` hook supports extending form state with new fields.
- Phone number validation accepts international formats starting with `+`.

## Dependencies

- AWS Cognito User Pool with EMAIL_OTP enabled (existing)
- Amplify Auth library (`aws-amplify/auth`) (existing)
- FastAPI backend with `/customers/me` endpoint (existing)
- shadcn/ui components for form fields (existing), including `input-otp` component (may need to be added via `npx shadcn@latest add input-otp`)
- Playwright test infrastructure (existing)

## Clarifications

### Session 2025-01-05

- Q: OTP input UX pattern (single field vs 6 boxes)? → A: Six separate single-digit input boxes using shadcn/ui `input-otp` component.
- Q: Existing OTP implementation is broken - scope of fix? → A: Fix the broken OTP flow as part of this feature (extract + fix).
- Q: When to diagnose OTP bugs? → A: Defer to planning phase - add "investigate OTP bugs" as first implementation task.
- Q: E2E testing strategy for EMAIL_OTP flows? → A: Two-pronged approach: (1) Unauthenticated flow - test UI up to OTP submission only (form validation, "Verify Email" triggers OTP UI), cannot verify real OTP on live site; (2) Authenticated bypass - use existing `auth.fixture.ts` with password-based test user (SSM-stored credentials, `USER_PASSWORD_AUTH` flow) to test User Story 3 where authenticated users skip the auth step entirely.

## Out of Scope

- Social login (Google, Facebook) - not part of this feature
- SMS OTP verification - email only
- Profile editing after creation - separate feature
- Multi-factor authentication beyond email OTP
- Password-based authentication
