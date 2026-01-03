# Feature Specification: Amplify Authentication Refactor

**Feature Branch**: `010-amplify-auth-refactor`
**Created**: 2026-01-02
**Status**: Draft
**Input**: User description: "The authentication flow is extremely confusing and have several different implementations. This needs to be refactored and simplified. Requirements: Amplify shall handle complete signin/signup flow, ApiGateway shall handle authorizing protected endpoints, FastAPI backend shall trust JWT verified by API Gateway, FastAPI shall store/retrieve customer records using cognito sub claim."

## Problem Statement

The current codebase contains three overlapping authentication implementations from specs 003, 004, and 005:

1. **Spec 003 (AgentCore Identity OAuth2)**: Agent-initiated OAuth2 with `@requires_access_token` decorator, session binding via DynamoDB, and AgentCore token vault
2. **Spec 004 (JWT Session Auth)**: Agent-initiated EMAIL_OTP via `AdminInitiateAuth`, custom JWT delivery via tool responses, frontend localStorage storage
3. **Spec 005 (AgentCore Amplify OAuth2)**: Hybrid approach with authorization URLs and Amplify Authenticator pages

This creates confusion, maintenance burden, and inconsistent user experiences. The solution is to consolidate into a single, simple architecture:

- **Frontend (Amplify)**: Handles all authentication UI and token management
- **API Gateway**: Validates JWT tokens on protected endpoints (Cognito authorizer)
- **Backend (FastAPI)**: Trusts API Gateway validation, uses `sub` claim from JWT for customer identity

## Out of Scope

- **Agent-initiated authentication flows**: The agent will NOT initiate OAuth2 or EMAIL_OTP. Authentication is a frontend concern triggered by UI interactions.
- **AgentCore Identity token vault**: Not required when Amplify manages tokens client-side
- **OAuth2 session binding via DynamoDB**: Eliminated with direct Amplify authentication
- **Custom JWT delivery via tool responses**: Eliminated by moving auth to frontend
- **Password-based authentication**: EMAIL_OTP only (passwordless)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Date Selection and Continue to Guest Details (Priority: P1)

A customer browses the booking calendar, selects check-in and check-out dates, and clicks "Continue to guest details" to proceed with their booking.

**Why this priority**: This is the entry point to the booking flow. Every booking starts with date selection. This establishes the baseline user journey before authentication.

**Independent Test**: Can be fully tested by opening the booking page, selecting dates on the calendar, clicking "Continue to guest details", and verifying the guest details form appears.

**Acceptance Scenarios**:

1. **Given** a customer is on the booking page with a calendar widget, **When** they select check-in and check-out dates, **Then** the selected dates are highlighted and a summary shows the duration
2. **Given** valid dates are selected, **When** the customer clicks "Continue to guest details", **Then** the guest details form is displayed
3. **Given** invalid dates are selected (e.g., check-out before check-in), **When** the customer clicks "Continue to guest details", **Then** an error message is displayed and navigation is blocked

---

### User Story 2 - Returning User with Existing Session (Priority: P1)

A returning customer who has previously authenticated returns to the site with an existing Amplify session. The guest details form recognizes them and displays their stored name and email instead of empty input fields.

**Why this priority**: Returning users represent repeat business. Recognizing them and pre-filling their details reduces friction and improves conversion.

**Independent Test**: Can be tested by authenticating once, refreshing the page or returning later, navigating to guest details, and verifying name/email are displayed (not editable inputs).

**Acceptance Scenarios**:

1. **Given** a user has an active Amplify session with stored credentials, **When** they navigate to the guest details form, **Then** their full name and email are displayed as read-only text (not input fields)
2. **Given** a returning user sees their pre-filled details, **When** they want to use different details, **Then** they can sign out and re-authenticate with different credentials
3. **Given** a session exists but has expired, **When** the user navigates to guest details, **Then** the form shows empty input fields (no session state)

---

### User Story 3 - New User Email Verification (Priority: P1)

A new customer (no existing session) fills in their name and email, then clicks "Verify email" to receive an OTP code via email for account creation.

**Why this priority**: This is the critical conversion point for new customers. The EMAIL_OTP flow must be seamless to minimize abandonment.

**Independent Test**: Can be tested by navigating to guest details without a session, entering name and email, clicking "Verify email", receiving OTP via email within 60 seconds, and seeing the code input field appear.

**Acceptance Scenarios**:

1. **Given** a new user is on the guest details form without an existing session, **When** the form loads, **Then** editable input fields for "Full Name" and "Email Address" are displayed
2. **Given** the user enters a valid email address, **When** they click "Verify email", **Then** Amplify initiates Cognito EMAIL_OTP flow and sends a verification code
3. **Given** the OTP has been sent, **When** the user checks their email, **Then** the code arrives within 60 seconds and is valid for 5 minutes
4. **Given** the OTP was sent, **When** the UI updates, **Then** a "Code" input field and "Confirm" button appear below the email field
5. **Given** the email is invalid format, **When** the user clicks "Verify email", **Then** a validation error is shown and no OTP is sent

---

### User Story 4 - OTP Confirmation and Session Creation (Priority: P1)

After receiving the OTP, the customer enters the code and clicks "Confirm" to complete authentication. Amplify stores the session tokens.

**Why this priority**: This completes the authentication flow. Without successful OTP confirmation, the user cannot proceed with booking.

**Independent Test**: Can be tested by entering the correct OTP code, clicking "Confirm", and verifying the user becomes authenticated with a valid Amplify session.

**Acceptance Scenarios**:

1. **Given** the user has received an OTP code, **When** they enter the correct 6-8 digit code and click "Confirm", **Then** Amplify verifies the code with Cognito and creates a session
2. **Given** successful verification, **When** the session is created, **Then** the form transitions to show the user's name/email as read-only (authenticated state)
3. **Given** the user enters an incorrect code, **When** they click "Confirm", **Then** an error message is displayed and they can retry
4. **Given** the user exhausts retry attempts (3 attempts), **When** they try again, **Then** they must request a new OTP code
5. **Given** the OTP has expired (after 5 minutes), **When** the user tries to confirm, **Then** an error indicates expiration and they must request a new code

---

### User Story 5 - Protected API Endpoint Access (Priority: P2)

When an authenticated user submits a booking, the frontend sends the request to a protected API endpoint. The API Gateway validates the JWT before forwarding to the backend.

**Why this priority**: This validates the end-to-end authentication architecture but depends on the frontend authentication being complete.

**Independent Test**: Can be tested by authenticating, submitting a booking request, and verifying the request reaches the backend with the validated JWT claims.

**Acceptance Scenarios**:

1. **Given** an authenticated user submits a booking, **When** the frontend sends the request, **Then** the Amplify session token is included in the Authorization header
2. **Given** a valid JWT is included, **When** API Gateway receives the request, **Then** the Cognito authorizer validates the token before forwarding to the backend
3. **Given** the JWT is valid, **When** the backend receives the request, **Then** the `sub` claim from the JWT is available for identifying the customer
4. **Given** an invalid or expired JWT, **When** API Gateway receives the request, **Then** a 401 Unauthorized response is returned without reaching the backend

---

### User Story 6 - Customer Record Persistence (Priority: P2)

The backend stores and retrieves customer records in DynamoDB using the Cognito `sub` claim as the unique identifier, ensuring each authenticated user has a consistent customer profile.

**Why this priority**: Customer data persistence is essential for reservations but depends on the authentication flow being complete.

**Independent Test**: Can be tested by authenticating, creating a booking, and verifying the customer record is stored with the correct `sub` identifier in DynamoDB.

**Acceptance Scenarios**:

1. **Given** a new authenticated user completes their first booking, **When** the backend processes the request, **Then** a customer record is created in DynamoDB with `cognito_sub` as the identifier
2. **Given** a returning authenticated user makes another booking, **When** the backend processes the request, **Then** the existing customer record is retrieved using the `sub` claim
3. **Given** a customer record exists, **When** the backend queries by `cognito_sub`, **Then** the correct guest profile (name, email, booking history) is returned

---

### Edge Cases

- What happens when a user's session token expires mid-booking? The frontend should detect 401 responses and prompt re-authentication.
- What happens if the same email is used from multiple devices? Amplify session is device-specific; multiple sessions can coexist.
- What happens if Cognito EMAIL_OTP delivery fails? The user can request a new code after a brief delay (rate limiting applies).
- What happens if the user closes the browser before confirming OTP? The partial authentication state is lost; they must restart.
- What happens if backend receives a request without API Gateway validation? Direct backend access should be blocked by network configuration; backend trusts API Gateway.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST use AWS Amplify Auth library for all frontend authentication operations (sign-up, sign-in, OTP verification, session management)
- **FR-002**: System MUST configure Cognito User Pool with EMAIL_OTP as the only authentication method (no passwords)
- **FR-003**: System MUST display editable name and email input fields when no Amplify session exists
- **FR-004**: System MUST display read-only name and email values when an active Amplify session exists
- **FR-005**: System MUST provide a "Verify email" button that triggers Cognito EMAIL_OTP flow via Amplify
- **FR-006**: System MUST display a "Code" input field and "Confirm" button after OTP is sent
- **FR-007**: System MUST validate OTP codes via Amplify and create a session on success
- **FR-008**: System MUST configure API Gateway with Cognito User Pool authorizer for protected endpoints
- **FR-009**: Backend MUST NOT implement JWT validation logic (trusts API Gateway validation)
- **FR-010**: Backend MUST extract the `sub` claim from the JWT for customer identification
- **FR-011**: Backend MUST store customer records in DynamoDB using `cognito_sub` as the primary identifier
- **FR-012**: Backend MUST retrieve customer records by `cognito_sub` for authenticated operations
- **FR-013**: System MUST handle session expiration gracefully with clear re-authentication prompts
- **FR-014**: System MUST allow maximum 3 OTP attempts before requiring a new code request
- **FR-015**: System MUST enforce 5-minute OTP expiration

### Key Entities

- **Customer (Guest)**: Represents a user who makes bookings. Key attributes: `cognito_sub` (unique identifier from Cognito), `email`, `name`, `phone`, `booking_history`. The `cognito_sub` links the DynamoDB record to the Cognito user.
- **Session**: Managed entirely by Amplify Auth. Contains `IdToken`, `AccessToken`, `RefreshToken`. Not stored in application database.
- **OTP Code**: Temporary verification code sent via email. 6-8 digits, expires after 5 minutes, maximum 3 attempts. Managed by Cognito, not stored in application database.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can complete email verification (OTP sent and confirmed) in under 90 seconds
- **SC-002**: Returning users with existing sessions see pre-filled details within 500ms of form load
- **SC-003**: 95% of OTP codes are delivered within 30 seconds of request
- **SC-004**: Authentication-related support tickets reduce by 70% compared to previous implementation complexity
- **SC-005**: Protected endpoint requests with valid tokens succeed with under 100ms authorization overhead
- **SC-006**: Zero authentication-related code exists in the backend beyond `sub` claim extraction
- **SC-007**: Single authentication implementation replaces the three existing overlapping implementations (003, 004, 005)

## Assumptions

- Cognito User Pool is already provisioned with EMAIL_OTP support enabled (Cognito Essentials tier)
- API Gateway is configured with appropriate Cognito User Pool authorizer
- Amplify Auth library is compatible with the existing Next.js 14+ App Router architecture
- DynamoDB `guests` table already has a GSI on `cognito_sub` for efficient lookups
- The frontend booking flow (calendar widget, guest details form) already exists and requires modification, not creation from scratch
