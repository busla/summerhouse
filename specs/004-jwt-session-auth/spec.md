# Feature Specification: JWT Session Authentication Flow

**Feature Branch**: `004-jwt-session-auth`
**Created**: 2025-12-30
**Status**: Clarified
**Input**: User description: "Fix frontend/backend signup/signin flow: anonymous identity pool access for inquiries, agent-initiated EMAIL_OTP auth for reservations, JWT token delivery to frontend for session storage, authenticated AgentCore requests for memory retrieval and DynamoDB claims lookup"

## Problem Statement

The current authentication implementation has a fundamental architectural gap: the backend's `verify_cognito_otp` tool returns guest profile information but not Cognito JWT tokens, leaving the frontend unable to store tokens for authenticated requests.

**Current broken flow:**
1. User chats with agent (anonymous via Cognito Identity Pool) - works
2. User wants to make reservation - agent initiates EMAIL_OTP - works
3. User verifies OTP - backend gets JWT tokens - works
4. **GAP**: JWT tokens stay server-side; frontend never receives them
5. Subsequent requests remain anonymous; AgentCore Memory and user-specific DynamoDB queries fail

**Desired flow:**
1. User chats with agent (anonymous via Cognito Identity Pool) - works
2. User wants to make reservation - agent collects name/email - initiates `AdminInitiateAuth` with `EMAIL_OTP`
3. User verifies OTP - backend generates JWT tokens
4. **NEW**: Backend delivers JWT to frontend via tool response in AgentCore SSE stream
5. Frontend stores JWT in session (localStorage with `booking_session` key)
6. Subsequent AgentCore requests include JWT in request payload (`auth_token` field)
7. AgentCore Runtime uses JWT for Memory retrieval and DynamoDB queries

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Anonymous Inquiry Browsing (Priority: P1)

A customer visits the booking website and asks the agent about availability, pricing, and property details without creating an account or signing in. This is the default state for all new visitors.

**Why this priority**: This is the primary entry point for all users. 90%+ of initial interactions are anonymous inquiries. Must work flawlessly.

**Independent Test**: Can be fully tested by opening the website, starting a conversation with the agent, and asking "What dates are available in March?" without any authentication prompts. Agent responds with availability information.

**Acceptance Scenarios**:

1. **Given** a new visitor loads the booking website, **When** they send their first message to the agent, **Then** the message is sent to AgentCore Runtime using anonymous Cognito Identity Pool credentials
2. **Given** an anonymous user asks about availability, **When** the agent processes the query, **Then** the agent returns accurate availability data without requiring authentication
3. **Given** an anonymous user asks about pricing, **When** the agent processes the query, **Then** the agent returns pricing information without requiring authentication
4. **Given** an anonymous user asks about property features, **When** the agent processes the query, **Then** the agent returns property details without requiring authentication

---

### User Story 2 - Agent-Initiated Authentication for Reservations (Priority: P1)

When a customer expresses intent to make a reservation, the agent collects their name and email, then initiates the EMAIL_OTP authentication flow. The customer receives a verification code via email and enters it in the chat interface.

**Why this priority**: This is the critical conversion point where anonymous users become authenticated customers. Without this, no reservations can be made.

**Independent Test**: Can be fully tested by chatting with the agent, saying "I want to book March 15-20", providing name and email when asked, receiving an OTP via email, entering the code, and receiving confirmation of successful authentication.

**Acceptance Scenarios**:

1. **Given** an anonymous user tells the agent they want to make a reservation, **When** the agent processes this intent, **Then** the agent asks for the user's name and email address
2. **Given** the user provides name "John Doe" and email "john@example.com", **When** the agent receives this information, **Then** the agent calls `AdminInitiateAuth` with `AUTH_FLOW=USER_AUTH` and `AuthParameters` including `USERNAME` and `PREFERRED_CHALLENGE=EMAIL_OTP`
3. **Given** Cognito sends an OTP to the user's email, **When** the user receives the code within 60 seconds, **Then** the agent prompts the user to enter the 6-digit verification code
4. **Given** the user enters the correct OTP, **When** the agent verifies it via `AdminRespondToAuthChallenge`, **Then** Cognito returns `IdToken`, `AccessToken`, and `RefreshToken`

---

### User Story 3 - JWT Token Delivery to Frontend (Priority: P1)

After successful OTP verification, the backend must deliver the Cognito JWT tokens to the frontend browser so they can be stored in the session and used for subsequent authenticated requests.

**Why this priority**: This is the core gap in the current implementation. Without token delivery, users cannot maintain authenticated sessions.

**Independent Test**: Can be tested by completing the OTP verification flow and verifying that the browser's localStorage contains valid `IdToken` and `AccessToken` values with correct expiration times.

**Acceptance Scenarios**:

1. **Given** the backend successfully verifies the OTP and receives Cognito tokens, **When** preparing the response, **Then** the tokens are included in a structured response that the frontend can process
2. **Given** the AgentCore Runtime response contains authentication tokens, **When** the frontend receives this response, **Then** the frontend extracts the tokens and stores them using the auth module
3. **Given** tokens are stored in the browser, **When** the page is refreshed, **Then** the tokens persist and the user remains authenticated
4. **Given** tokens are approaching expiration (within 5 minutes), **When** the user makes a new request, **Then** the system uses the `RefreshToken` to obtain new access tokens automatically

---

### User Story 4 - Authenticated AgentCore Requests (Priority: P1)

Once the user has a valid JWT stored in their browser session, all subsequent requests to AgentCore Runtime include the JWT in a header, enabling the agent to access AgentCore Memory for that user and query DynamoDB using JWT claims.

**Why this priority**: This enables personalized experiences and secure data access. Without this, authenticated users get the same experience as anonymous users.

**Independent Test**: Can be tested by authenticating, then asking "What are my reservations?" and verifying the agent returns user-specific reservation data from DynamoDB (not generic data).

**Acceptance Scenarios**:

1. **Given** the frontend has a valid JWT stored, **When** sending a new message to AgentCore, **Then** the JWT is included in the request payload as `auth_token` field
2. **Given** AgentCore Runtime receives a request with a valid JWT, **When** processing a tool that requires authentication, **Then** the tool can decode the JWT to extract the `sub` claim for DynamoDB queries
3. **Given** an authenticated user asks "What are my reservations?", **When** the agent processes this, **Then** the agent queries DynamoDB using the Cognito `sub` from the JWT and returns only that user's reservations
4. **Given** AgentCore Runtime receives a request with a valid JWT, **When** accessing AgentCore Memory, **Then** the Memory service uses the JWT to scope memory to that specific user

---

### User Story 5 - New User Registration with Passwordless (Priority: P2)

When a first-time user provides an email that doesn't exist in Cognito, the system automatically creates a new user account as part of the EMAIL_OTP flow.

**Why this priority**: Reduces friction for new customers. They don't need to explicitly "sign up" - the booking intent triggers account creation seamlessly.

**Independent Test**: Can be tested by providing a completely new email address, completing OTP verification, and verifying a new Cognito user exists with that email marked as verified.

**Acceptance Scenarios**:

1. **Given** a user provides an email that doesn't exist in Cognito, **When** the agent initiates auth, **Then** Cognito creates a new user with email marked as verified upon OTP completion
2. **Given** a new user completes OTP verification, **When** the guest profile is created, **Then** a new record is created in the guests DynamoDB table with the Cognito `sub` linked
3. **Given** a new user has completed registration, **When** they return later with the same email, **Then** they can authenticate with EMAIL_OTP as a returning user

---

### Edge Cases

- What happens when the JWT expires during an active conversation? The frontend should detect 401 responses and trigger token refresh or re-authentication.
- How does the system handle network failures during OTP verification? The agent should allow retry and display a user-friendly error message.
- What happens if the user closes the browser before entering the OTP? The OTP remains valid for 5 minutes; the user can re-open and complete verification.
- How does the system handle concurrent authentication from multiple browser tabs? All tabs share the same localStorage; successful auth in one tab updates all tabs.
- What happens when Cognito rate limits are hit? The agent informs the user to wait and try again in a few minutes.
- How does the system handle malformed or tampered JWTs? The backend rejects invalid tokens and treats the request as unauthenticated.

## Requirements *(mandatory)*

### Functional Requirements

**Anonymous Access**:
- **FR-001**: System MUST allow unauthenticated users to chat with the booking agent using Cognito Identity Pool anonymous credentials
- **FR-002**: System MUST support availability, pricing, and property inquiry tools without requiring authentication
- **FR-003**: System MUST NOT prompt for authentication until the user expresses booking/reservation intent

**Agent-Initiated Authentication**:
- **FR-004**: Agent MUST collect user's name and email when booking intent is detected
- **FR-005**: Agent MUST initiate Cognito authentication via `AdminInitiateAuth` with `EMAIL_OTP` preferred challenge
- **FR-006**: Agent MUST prompt user to enter 6-digit OTP received via email
- **FR-007**: Agent MUST verify OTP via `AdminRespondToAuthChallenge` and receive Cognito tokens on success
- **FR-008**: System MUST create new Cognito user if email doesn't exist (seamless registration)

**Token Delivery**:
- **FR-009**: Backend MUST deliver `IdToken`, `AccessToken`, and `RefreshToken` to the frontend after successful OTP verification
- **FR-010**: Token delivery MUST use a structured format that the frontend can reliably parse from the AgentCore response stream
- **FR-011**: Frontend MUST extract and store tokens in browser session storage upon receiving them

**Session Management**:
- **FR-012**: Frontend MUST persist tokens across page refreshes (localStorage)
- **FR-013**: Frontend MUST include JWT in request payload (`auth_token` field) for all authenticated AgentCore requests
- **FR-014**: System MUST refresh tokens automatically when approaching expiration (within 5 minutes)
- **FR-015**: System MUST clear tokens and return to anonymous state on explicit sign-out

**Authenticated Operations**:
- **FR-016**: Backend tools MUST be able to extract user identity from JWT `sub` claim
- **FR-017**: Backend MUST query DynamoDB using Cognito `sub` to retrieve user-specific data
- **FR-018**: AgentCore Memory MUST scope to authenticated user's identity when JWT is present

**Security**:
- **FR-019**: OTP codes MUST expire after 5 minutes
- **FR-020**: OTP verification MUST be limited to 3 attempts per code
- **FR-021**: JWTs MUST be transmitted only over HTTPS
- **FR-022**: Backend MUST validate JWT signature before trusting claims for authenticated operations

### Key Entities

- **AuthSession**: Browser-side session state containing `idToken`, `accessToken`, `refreshToken`, `expiresAt`, and user metadata (`email`, `name`, `guestId`). Stored in localStorage.
- **OTPChallenge**: Server-side state during authentication flow. Contains `session` (Cognito session token), `email`, `expiresAt`, and `attempts` count.
- **Guest**: User profile in DynamoDB. Linked to Cognito via `cognito_sub`. Contains `guest_id`, `email`, `name`, `cognito_sub`, `email_verified`.
- **TokenDeliveryEvent**: Structured message from backend to frontend within the AgentCore response stream, containing tokens after successful authentication.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can browse availability, pricing, and property information without authentication (100% of inquiry flows work anonymously)
- **SC-002**: Users can complete the authentication flow (from "I want to book" to authenticated session) in under 90 seconds, excluding email delivery time
- **SC-003**: OTP codes are delivered to 95%+ of users within 60 seconds
- **SC-004**: Authenticated users can access their reservation history within 3 seconds of requesting it
- **SC-005**: Token refresh happens seamlessly with no user-visible interruption or re-authentication prompt
- **SC-006**: Users remain authenticated across page refreshes and browser tab switches (session persistence works 100%)
- **SC-007**: Zero data leakage between users (user A cannot see user B's reservations via JWT manipulation)

## Assumptions

1. **Cognito Essentials Tier**: The Cognito User Pool is configured for Essentials tier, which supports `EMAIL_OTP` as a first-factor authentication method.
2. **AdminInitiateAuth Permissions**: The AgentCore Runtime Lambda has IAM permissions to call `cognito-idp:AdminInitiateAuth` and `cognito-idp:AdminRespondToAuthChallenge`.
3. **Token Delivery Mechanism**: AgentCore tool responses flow through the SSE stream to the frontend. The `verify_cognito_otp` tool returns a `TokenDeliveryEvent` with `event_type: "auth_tokens"` that the frontend detects and processes.
4. **Direct localStorage Storage**: Tokens are stored directly in localStorage (not Amplify Auth). Amplify Auth v6 is designed for user-initiated flows; our agent-initiated flow uses direct storage.
5. **AgentCore Memory Scoping**: AgentCore Memory API can be scoped to a user identity based on the JWT passed in the request payload.

## Clarifications

*Added 2025-12-30 via `/speckit.clarify`:*

1. **No Amplify Auth**: This feature does NOT use Amplify Auth. Amplify Auth v6 is designed for user-initiated flows (frontend calls `signIn()`/`confirmSignIn()`). Our flow is agent-initiated (backend calls `AdminInitiateAuth`), so we use direct localStorage storage.

2. **Payload-based Auth (not header)**: JWT is passed in the request payload (`auth_token` field), not the `Authorization` header. While AgentCore Runtime supports custom headers via botocore event handlers, payload-based auth is simpler and sufficient for MVP.

3. **Remove `@requires_access_token`**: The existing `@requires_access_token` decorator in `backend/src/tools/auth.py` is for OAuth2 3LO (Three-Legged OAuth) with external providers like Google/GitHub. It is NOT appropriate for direct Cognito EMAIL_OTP authentication and should be removed.

4. **Token Refresh via Backend**: Token refresh uses a backend API endpoint calling `AdminInitiateAuth` with `REFRESH_TOKEN_AUTH` flow, not frontend Cognito SDK.

5. **Code Cleanup Required**: ALL unused/deprecated code related to incorrect auth patterns (like `@requires_access_token` for EMAIL_OTP) MUST be removed to prevent repo bloat.
