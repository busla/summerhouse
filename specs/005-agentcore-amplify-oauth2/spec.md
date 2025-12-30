# Feature Specification: AgentCore Identity OAuth2 with Amplify EMAIL_OTP

**Feature Branch**: `005-agentcore-amplify-oauth2`
**Created**: 2025-12-30
**Status**: Draft
**Input**: User description: "Standard AgentCore Identity OAuth2 signin/signup flow using Amplify EMAIL_OTP for reservations - agent returns authorization URL, user authenticates on Amplify-managed page, callback completes session binding"

## Problem Statement

The current authentication implementation (spec 004) uses **agent-initiated** EMAIL_OTP where the backend directly calls Cognito's `AdminInitiateAuth`. This approach:
1. Requires custom JWT token delivery via tool responses
2. Bypasses standard OAuth2 security patterns
3. Cannot leverage AgentCore Identity's token vault for secure credential management

The desired approach uses **user-initiated** authentication via the standard AgentCore Identity OAuth2 flow:
1. When user wants to make a reservation, agent tool decorated with `@requires_access_token` triggers
2. AgentCore returns an authorization URL (because no valid token exists)
3. User clicks URL, lands on custom Amplify Authenticator page configured for EMAIL_OTP only
4. User enters email, receives OTP, confirms
5. Amplify stores Cognito tokens, redirects to AgentCore Identity callback
6. Frontend callback page calls `CompleteResourceTokenAuth` with session binding
7. User is redirected back to chat; agent can now access protected resources

This aligns with OAuth2 security standards and leverages AgentCore's built-in identity management.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Anonymous Inquiry (No Auth Required) (Priority: P1)

A customer visits the booking website and asks the agent about availability, pricing, and property details. This flow remains unchanged and requires no authentication.

**Why this priority**: This is the primary entry point. Most visitors are just browsing, and they should not encounter any authentication friction.

**Independent Test**: Open the website, ask "What dates are available in March?" - agent responds with availability without any authentication prompts.

**Acceptance Scenarios**:

1. **Given** a new visitor loads the booking website, **When** they ask about availability, **Then** the agent responds with accurate data without authentication prompts
2. **Given** an anonymous user asks about pricing, **When** the agent processes the query, **Then** the agent returns pricing information immediately
3. **Given** an anonymous user asks about property features, **When** the agent processes the query, **Then** the agent returns property details without requiring login

---

### User Story 2 - Authorization URL Generation for Booking Intent (Priority: P1)

When a user expresses intent to make a reservation, the agent attempts to use a protected tool. Since no valid OAuth2 token exists, AgentCore returns an authorization URL that the agent presents to the user.

**Why this priority**: This is the critical handoff point from anonymous browsing to authenticated booking. The user experience here determines conversion rates.

**Independent Test**: Chat with agent, say "I want to book March 15-20". Agent responds with a clickable authorization URL and instruction to complete sign-in.

**Acceptance Scenarios**:

1. **Given** an anonymous user tells the agent "I want to make a reservation", **When** the agent invokes a tool decorated with `@requires_access_token`, **Then** AgentCore Identity returns an authorization URL
2. **Given** the agent receives an authorization URL, **When** formatting the response, **Then** the agent presents a clickable link with clear instruction: "Please click here to sign in and continue with your booking"
3. **Given** the authorization URL contains a session_id parameter, **When** the user clicks it, **Then** the browser navigates to the custom Amplify Authenticator page with EMAIL_OTP flow

---

### User Story 3 - Amplify EMAIL_OTP Authentication Page (Priority: P1)

The user lands on the Amplify-managed authentication page that uses Cognito EMAIL_OTP as the only sign-in method. No username/password form is displayed.

**Why this priority**: The authentication UX is critical for conversion. Passwordless EMAIL_OTP reduces friction and improves security.

**Independent Test**: Click the authorization URL, see a clean EMAIL_OTP form (email input only, no password field), enter email, receive OTP within 60 seconds.

**Acceptance Scenarios**:

1. **Given** the user clicks the authorization URL, **When** the Amplify auth page loads, **Then** only an email input field is displayed (no password field)
2. **Given** the user enters their email address, **When** they submit, **Then** Cognito sends an 8-digit OTP to their email within 60 seconds
3. **Given** the user has received the OTP, **When** the OTP input field appears, **Then** the user can enter the code
4. **Given** the user enters a valid OTP, **When** they submit, **Then** authentication succeeds and Amplify stores tokens
5. **Given** the user enters their name during first-time signup, **When** authentication completes, **Then** the name is stored in Cognito user attributes

---

### User Story 4 - Session Binding and Callback (Priority: P1)

After successful authentication, Amplify redirects to the AgentCore Identity callback URL. A callback handler page extracts the session_uri and completes the OAuth2 session binding by calling `CompleteResourceTokenAuth`.

**Why this priority**: Session binding is the security mechanism that ensures the user who initiated auth is the same user who completed it. Without this, the OAuth2 flow is incomplete.

**Independent Test**: Complete EMAIL_OTP verification, observe redirect to callback URL, verify `CompleteResourceTokenAuth` is called, then redirect back to chat interface.

**Acceptance Scenarios**:

1. **Given** authentication succeeds, **When** Amplify completes the flow, **Then** the browser redirects to the AgentCore Identity callback URL with session_id parameter
2. **Given** the callback page loads, **When** it parses the URL, **Then** it extracts the session_uri (session_id query parameter)
3. **Given** the callback page has the session_uri and user's Cognito token, **When** it calls `CompleteResourceTokenAuth`, **Then** AgentCore Identity binds the session to the user
4. **Given** `CompleteResourceTokenAuth` succeeds, **When** the callback logic completes, **Then** the user is redirected to the configured allowed redirect URL (the chat interface)
5. **Given** the user returns to the chat interface, **When** they send a new message, **Then** the agent can now access protected resources on their behalf

---

### User Story 5 - Returning User Authentication (Priority: P2)

A user who has previously authenticated returns and wants to make another reservation. If their token is still valid in AgentCore's token vault, no re-authentication is needed.

**Why this priority**: Good UX for returning users. Reduces friction for repeat bookings.

**Independent Test**: Complete a booking flow, wait 5 minutes, start a new booking request - agent should proceed without re-authentication.

**Acceptance Scenarios**:

1. **Given** a user has previously authenticated and their token is in AgentCore's token vault, **When** the agent invokes a protected tool, **Then** the tool proceeds without presenting an authorization URL
2. **Given** a user's token has expired, **When** the agent invokes a protected tool, **Then** AgentCore returns a new authorization URL for re-authentication

---

### Edge Cases

- What happens when the authorization URL expires (10-minute window)? The agent should detect the expired session and generate a new authorization URL.
- How does the system handle the user clicking the auth URL in a different browser? The callback must fail gracefully since session cookies won't match.
- What happens if the user closes the browser during OTP entry? They can re-click the authorization URL from the chat history (if still valid).
- How does the system handle network failure during `CompleteResourceTokenAuth`? Display an error message with retry option.
- What happens when Cognito rate limits are hit during OTP send? Display user-friendly message to wait and try again.

## Requirements *(mandatory)*

### Functional Requirements

**AgentCore Identity Integration**:
- **FR-001**: Protected booking tools MUST use the `@requires_access_token` decorator with Cognito as the credential provider
- **FR-002**: Agent MUST stream the authorization URL to the user via `on_auth_url` callback when authentication is required
- **FR-003**: The authorization URL MUST include a session_uri for session binding
- **FR-004**: Workload Identity MUST be configured with allowed OAuth2 return URLs including the callback page

**Amplify Authentication Page**:
- **FR-005**: Authentication page MUST use Amplify UI components for Cognito EMAIL_OTP flow
- **FR-006**: Authentication page MUST NOT display username/password fields - EMAIL_OTP only
- **FR-007**: Authentication page MUST collect user's name during first-time signup
- **FR-008**: Authentication page MUST redirect to AgentCore Identity callback URL on success

**Cognito Configuration**:
- **FR-009**: Cognito User Pool MUST be configured with EMAIL_OTP as the sign-in method
- **FR-010**: Cognito User Pool Client MUST have the AgentCore Identity callback URL as allowed callback
- **FR-011**: Authentication MUST use custom Amplify Authenticator page (Cognito Hosted UI cannot support EMAIL_OTP-only)

**Session Binding Callback**:
- **FR-012**: Callback page MUST extract session_uri from URL query parameters
- **FR-013**: Callback page MUST retrieve Cognito access_token from Amplify Auth session
- **FR-014**: Callback page MUST call `CompleteResourceTokenAuth` with session_uri and user token
- **FR-015**: Callback page MUST redirect to allowed return URL after successful binding
- **FR-016**: Callback page MUST display clear error message if session binding fails

**Terraform/Infrastructure**:
- **FR-017**: OAuth2 Credential Provider MUST be created with Cognito as the identity provider
- **FR-018**: Workload Identity MUST be updated with allowed return URLs via `terraform-aws-agentcore` module
- **FR-019**: Cognito User Pool Client MUST include AgentCore Identity's callback URL (available from `module.agentcore.identity.oauth2_provider_callback_urls["cognito"]` output)

**Security**:
- **FR-020**: Authorization URLs MUST expire within 10 minutes
- **FR-021**: Session binding MUST verify user identity before completing auth
- **FR-022**: All OAuth2 callbacks MUST use HTTPS
- **FR-023**: CSRF protection SHOULD use custom_state parameter for callback validation

### Key Entities

- **OAuth2CredentialProvider**: AgentCore Identity resource that holds Cognito client credentials and discovery URL. Created via Terraform.
- **WorkloadIdentity**: AgentCore Identity resource that represents the agent application. Contains allowed return URLs for session binding.
- **AuthorizationSession**: Temporary session (10-min TTL) created when agent requests token. Contains session_uri used for binding.
- **TokenVault**: AgentCore-managed secure storage for OAuth2 tokens. Acts as a **guardrail for the agent** - provides JWT tokens that the agent uses to extract claims (`sub`, `email`) for scoping DynamoDB queries to user-specific data. Does NOT replace frontend browser session storage. See [Clarifications](#clarifications) for details.
- **CognitoUser**: User record in Cognito User Pool with email (username) and name attributes. Created on first EMAIL_OTP verification.
- **AmplifySession**: Browser-side session managed by Amplify Auth. Stores Cognito tokens for client-side authentication state. Separate from TokenVault.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can browse availability, pricing, and property information without any authentication prompts (100% of inquiry flows work anonymously)
- **SC-002**: Users receive a clear, clickable authorization URL when attempting to book (link is rendered and clickable in chat interface)
- **SC-003**: Authentication page loads within 2 seconds and displays EMAIL_OTP form only (no password fields visible)
- **SC-004**: OTP codes are delivered to 95%+ of users within 60 seconds of request
- **SC-005**: Users complete the full authentication flow (click URL to enter email to enter OTP to return to chat) in under 2 minutes, excluding email delivery time
- **SC-006**: Session binding via `CompleteResourceTokenAuth` succeeds on first attempt for 99%+ of users
- **SC-007**: After successful authentication, protected agent tools execute without prompting for re-authentication
- **SC-008**: Zero security violations where one user can access another user's resources

## Assumptions

1. **terraform-aws-agentcore module**: The external `terraform-aws-agentcore` module handles creation of OAuth2 Credential Provider and Workload Identity with correct callback URLs.

2. **Amplify v6 compatibility**: Amplify Auth v6 with `aws-amplify` and `@aws-amplify/ui-react` supports custom authentication flows and can be configured for EMAIL_OTP only.

3. **Custom Amplify Authenticator**: Cognito Hosted UI cannot support EMAIL_OTP-only (requires password field). Instead, use custom Amplify Authenticator with `services` prop to configure `authFlowType: 'USER_AUTH'` and `preferredChallenge: 'EMAIL_OTP'`.

4. **AgentCore Runtime permissions**: The AgentCore Runtime execution role has IAM permissions for `bedrock-agentcore:GetResourceOauth2Token` and `bedrock-agentcore:CompleteResourceTokenAuth`.

5. **Static export compatibility**: The callback page can be part of the Next.js static export since it only needs client-side JavaScript to call `CompleteResourceTokenAuth` via AWS SDK.

## Clarifications

### TokenVault Purpose (CRITICAL)

**TokenVault does NOT replace browser session storage**. The two serve distinct purposes:

| Storage | Purpose | Owner |
|---------|---------|-------|
| **Amplify Session (Browser)** | User authentication state, UI state, Cognito tokens for client-side auth | Frontend |
| **AgentCore TokenVault** | Guardrail for agent - provides JWT tokens the agent needs to query DynamoDB with user-scoped permissions | Agent Runtime |

**Why the agent needs the JWT token:**
1. Protected tools use `@requires_access_token` decorator to receive Cognito JWT
2. Agent extracts token claims (`sub`, `email`) to identify the authenticated user
3. Agent uses these claims to scope DynamoDB queries to only fetch **that user's** sensitive data (reservations, guest profile)
4. Without a valid token in TokenVault, the agent cannot access user-specific data - this is the "guardrail"

**Data flow example:**
```
User: "Show me my reservations"
  → Agent tool invoked with @requires_access_token
  → AgentCore retrieves JWT from TokenVault
  → Agent extracts `sub` claim from JWT
  → Agent queries DynamoDB: reservations WHERE cognito_sub = {sub}
  → Only that user's reservations returned
```

This ensures the agent cannot accidentally (or maliciously via prompt injection) access another user's data - the JWT claims enforce authorization at the data layer.

### Session 2025-12-30

- Q: How does the authorization URL get generated and what parameters does it contain? → A: AgentCore Identity automatically generates the authorization URL when agent invokes `GetResourceOauth2Token` API. The URL contains `session_id` and `state` query parameters. No manual propagation needed.
- Q: Should spec use "Cognito Hosted UI" or "custom Amplify Authenticator"? → A: Custom Amplify Authenticator page. Cognito Hosted UI cannot support EMAIL_OTP-only (requires password field).
- Q: Where does the AgentCore Identity callback URL come from for Cognito configuration? → A: It's available as a Terraform module output: `module.agentcore.identity.oauth2_provider_callback_urls["cognito"]`. Must be added to Cognito User Pool Client allowed callback URLs.

### AgentCore OAuth2 Flow (CRITICAL)

**AgentCore Identity handles authorization URL generation automatically**. The flow works as follows:

1. **Invoke agent** – Agent code invokes `GetResourceOauth2Token` API when user needs to access a protected resource
2. **Generate authorization URL** – AgentCore Identity generates an authorization URL containing `session_id` and `state` parameters
3. **User authenticates** – User navigates to authorization URL and completes authentication (Amplify EMAIL_OTP page)
4. **Callback verification** – After auth, AgentCore redirects to the HTTPS callback endpoint with session info. The callback page verifies the originating agent user matches the currently logged-in user
5. **Complete session binding** – If users match, callback invokes `CompleteResourceTokenAuth` so AgentCore can fetch and store the access token
6. **Token available** – Agent can now retrieve OAuth2 access tokens for that user

**Security guarantee**: By requiring the callback endpoint to verify user identity, AgentCore ensures it's always the same user who initiated the auth request and who consented access.

---

## Out of Scope

- Refresh token handling (AgentCore Identity manages token lifecycle in its vault)
- Multiple OAuth2 providers (only Cognito is supported for MVP)
- MFA beyond EMAIL_OTP (no TOTP, no SMS OTP, no WebAuthn)
- Custom Cognito Lambda triggers (e.g., pre-signup validation)
