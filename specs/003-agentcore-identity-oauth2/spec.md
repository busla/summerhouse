# Feature Specification: AgentCore Identity OAuth2 Login

**Feature Branch**: `003-agentcore-identity-oauth2`
**Created**: 2025-12-29
**Status**: Draft
**Input**: User description: "Implement agentcore identity oauth2 login for customers that decide to make a reservation. The Strands agent shall provide them with an authorization url for 3LO login into cognito. boto3 get_workload_access_token_for_jwt, get_workload_access_token_for_user_id, get_workload_access_token, get_resource_oauth2_token, complete_resource_token_auth. cognito signup/signin should use otp/totp passwordless login that requires cognito essentials plan with advanced security features enabled."

## Clarifications

### Session 2025-12-29

- Q: Is TOTP MFA in scope for this feature? → A: No, TOTP is out of scope for this feature.
- Q: Should authorization URL lead to Cognito hosted UI or passwordless flow? → A: URL leads to passwordless flow initiation only (no Cognito hosted UI).
- Q: Should the frontend use AWS Amplify Auth UI components or custom React components for the OAuth2 flow UX? → A: Use `@aws-amplify/ui-react` Authenticator component for OTP flow UI (aligns with Constitution Principle VI: prefer official AWS SDKs over custom code).
- Q: How should the OAuth2 callback API be deployed? → A: New `infrastructure/modules/gateway-v2` Terraform module deploying FastAPI as Lambda function using `terraform-aws-modules/lambda/aws` (>=8.1.2) with `terraform_data` for bash commands.
- Q: How should the gateway-v2 Lambda be exposed? → A: API Gateway HTTP API with `$default` stage (no stage prefix in URL path).
- Q: How should CloudFront route to the API? → A: CloudFront adds API Gateway as origin with `/api` path prefix routing.
- Q: How should AgentCore Identity resources (workload tokens, memory, credential providers) be managed? → A: The `terraform-aws-agentcore` module handles all AgentCore identity/memory/workload-token management. Use module outputs for ARNs/names of resources.

### Session 2025-12-29 (Terraform Module Composition)

- Q: How should AgentCore module outputs (Cognito pool ID, credential provider ARNs, etc.) be propagated to other modules? → A: Terraform module outputs from `terraform-aws-agentcore` MUST be wired as inputs to dependent modules (cognito-passwordless, gateway-v2). NOT manually added to .env files or configuration files. This follows IaC best practices for module composition.
- Q: How should the `@requires_access_token` decorator's `callback_url` parameter receive the API Gateway URL? → A: Via environment variable (`OAUTH2_CALLBACK_URL`) set by Terraform module on Lambda, accessed via `os.getenv()`.
- Q: How should the frontend present the OAuth2 auth URL to the user? → A: Render as a clickable hyperlink within the chat message bubble.
- Q: Should gateway-v2 FastAPI Lambda include all auth endpoints or only OAuth2 callback? → A: Callback only. OTP initiate/verify tools run via AgentCore Runtime Strands agent.
- Q: How should oauth2-sessions DynamoDB table be managed? → A: As a standalone table in `infrastructure/main.tf`, separate from terraform-aws-agentcore module.

### Session 2025-12-29 (Python Version Constraint)

- Q: What Python version is required for the backend? → A: Python 3.13+ only. Python 3.12 is NOT allowed. This aligns with `pyproject.toml` constraint `requires-python = ">=3.13,<3.14"`.

### Session 2025-12-29 (OAuth2 Research Corrections)

- Q: Why implement three separate `get_workload_token_*` functions? → A: **CORRECTED**: `IdentityClient.get_workload_access_token()` is a SINGLE function with optional parameters (`user_token` or `user_id`). No separate implementations needed.
- Q: Why store PKCE code_verifier in DynamoDB? → A: **CORRECTED**: AgentCore handles PKCE internally. The application does NOT need to store code_verifier.
- Q: Why validate OAuth2 state parameter? → A: **CORRECTED**: AgentCore uses a two-stage callback flow:
  1. Cognito redirects to AgentCore's callback URL (handles code exchange)
  2. AgentCore redirects to YOUR app's callback with `session_id` parameter
  The app's callback must verify user identity and call `CompleteResourceTokenAuth(session_uri=session_id, user_identifier=...)`.
- Q: What is the purpose of the DynamoDB session table? → A: **CLARIFIED**: The `oauth2-sessions` table serves as a **conversation-to-callback bridge** for agent-initiated OAuth2 flows. Unlike browser-based apps (which use cookies to identify users), agent conversations have no browser session. When the agent initiates OAuth2, it stores `session_id → guest_email` in DynamoDB. When the HTTP callback receives `session_id`, it looks up the corresponding `guest_email` to call `CompleteResourceTokenAuth(session_uri, user_identifier)`. This ensures the correct user identity is verified even though the callback has no conversation context.
- Q: After `CompleteResourceTokenAuth` returns the user's JWT, how should the token be delivered to the agent for authenticated operations? → A: **CLARIFIED**: Use `@requires_access_token` decorator from AgentCore SDK. The decorator automatically handles token acquisition/refresh and injects the token via the `access_token` parameter. When authentication is needed, the decorator triggers the OAuth2 flow via `on_auth_url` callback, and once complete, the token is available for subsequent tool calls within the conversation context.
- Q: How should authenticated tools extract user identity from the injected JWT for DynamoDB queries? → A: **CLARIFIED**: Decode JWT in-tool using `pyjwt` to extract `sub` claim, then query DynamoDB `cognito-sub-index` GSI. Pattern: `claims = jwt.decode(access_token, options={"verify_signature": False})` to get claims, then `db.get_guest_by_cognito_sub(claims["sub"])`.
- Q: After OAuth2 flow completes, where should JWT tokens be stored client-side? → A: Use `@aws-amplify/auth` defaults (localStorage) - persists across browser sessions with automatic token refresh.

## Out of Scope

- **TOTP MFA**: Multi-factor authentication via time-based one-time passwords is explicitly out of scope for this feature. Authentication will rely solely on EMAIL_OTP passwordless flow.
- **Cognito Hosted UI**: Authorization URLs will initiate passwordless flow directly, not redirect to Cognito's managed hosted UI.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Guest Initiates Passwordless Authentication (Priority: P1)

A guest browsing the vacation rental agent decides to make a reservation. The agent prompts them to authenticate. The guest provides their email address, and the system sends them a one-time password (OTP) via email for passwordless sign-in.

**Why this priority**: Authentication is the foundation for secure reservations. Without this, guests cannot make verified bookings. This is the minimum viable authentication flow.

**Independent Test**: Can be fully tested by starting a conversation with the agent, requesting to book, providing an email, receiving an OTP code, and completing sign-in. Delivers authenticated guest identity.

**Acceptance Scenarios**:

1. **Given** a guest is in conversation with the booking agent and wants to make a reservation, **When** the guest provides their email address, **Then** the system initiates Cognito `USER_AUTH` flow with `EMAIL_OTP` as preferred challenge
2. **Given** the guest has entered their email, **When** Cognito sends the OTP code, **Then** the guest receives the code within 60 seconds and the code is valid for 5 minutes
3. **Given** the guest has received the OTP code, **When** they enter the correct code, **Then** the agent confirms successful authentication and proceeds with the booking flow
4. **Given** the guest enters an incorrect OTP code, **When** the maximum attempts (3) are exceeded, **Then** the system requires a new OTP to be sent

---

### User Story 2 - New Guest Registration with Passwordless (Priority: P1)

A new guest who has never used the system before wants to sign up and make their first reservation. The system creates their account using passwordless authentication (no password required).

**Why this priority**: New guest acquisition is critical for business growth. Passwordless reduces friction and eliminates password-related support issues.

**Independent Test**: Can be fully tested by providing a new email address, receiving verification OTP, confirming account, and having a Cognito user created with verified email status.

**Acceptance Scenarios**:

1. **Given** a guest provides an email that doesn't exist in Cognito, **When** they request to sign up, **Then** the system creates a new Cognito user with `USER_AUTH` flow configured for `EMAIL_OTP`
2. **Given** a new user receives their registration OTP, **When** they enter the correct code, **Then** their email is marked as verified and they receive authentication tokens
3. **Given** a user has completed passwordless registration, **When** they return to make another booking, **Then** they can sign in with the same passwordless EMAIL_OTP flow

---

### User Story 3 - Agent Obtains Workload Access Token (Priority: P1)

The Strands booking agent needs to authenticate itself to access AgentCore Identity services before it can facilitate user authentication flows.

**Why this priority**: The agent must have its own identity token to call AgentCore Identity APIs and manage OAuth2 flows for users. This is a prerequisite for all user authentication.

**Independent Test**: Can be tested by initializing the agent, calling `get_workload_access_token()`, and verifying a valid JWT token is returned.

**Acceptance Scenarios**:

1. **Given** the Strands agent is initialized, **When** it needs to facilitate authentication, **Then** it obtains a workload access token via `IdentityClient.get_workload_access_token()`
2. **Given** the agent has a workload token, **When** it needs to initiate user OAuth2 flow, **Then** it can call AgentCore Identity APIs with the workload token
3. **Given** the workload token approaches expiration, **When** a new API call is needed, **Then** the agent automatically refreshes its workload token

---

### User Story 4 - Three-Legged OAuth2 Flow for Cognito (Priority: P2)

When a guest needs to authenticate, the agent generates an authorization URL for Cognito OAuth2 login and guides the guest through the 3LO flow.

**Why this priority**: This implements the full OAuth2 flow with proper session binding, enabling secure token exchange. Builds on P1 authentication foundation.

**Independent Test**: Can be tested by requesting authentication, receiving an authorization URL, opening it, completing Cognito login, and having the callback complete the token exchange.

**Acceptance Scenarios**:

1. **Given** a guest requests to authenticate, **When** the agent processes the request, **Then** it calls `GetResourceOAuth2Token()` which returns an authorization URL (AgentCore handles PKCE/state internally)
2. **Given** the agent has generated an authorization URL, **When** presented to the guest, **Then** the URL is valid and leads to Cognito authentication
3. **Given** the guest completes Cognito authentication, **When** AgentCore's callback receives the code, **Then** AgentCore exchanges it for tokens and redirects to the app callback with `session_id`
4. **Given** the app callback receives `session_id`, **When** it calls `CompleteResourceTokenAuth(session_uri, user_identifier)`, **Then** the guest's identity is verified and tokens are returned

---

### User Story 5 - Session Binding for OAuth2 Callbacks (Priority: P2)

When multiple guests are authenticating simultaneously, the system must correctly bind OAuth2 callbacks to the correct conversation session and verify user identity.

**Why this priority**: Without user identity verification, a malicious actor could intercept a callback and complete someone else's authentication. Critical for production security.

**Independent Test**: Can be tested by initiating two concurrent authentication flows with different users, completing both, and verifying each user's tokens are correctly associated with their conversation.

**Acceptance Scenarios**:

1. **Given** the agent initiates an OAuth2 flow for a guest, **When** storing the session locally, **Then** the `session_id` (from AgentCore) is associated with `conversation_id` and `guest_email`
2. **Given** an OAuth2 callback is received with `session_id`, **When** calling `CompleteResourceTokenAuth`, **Then** the `user_identifier` parameter matches the guest who initiated the flow
3. **Given** a callback with mismatched `user_identifier`, **When** `CompleteResourceTokenAuth` is called, **Then** the request is rejected to prevent session hijacking

---

### Edge Cases

- What happens when a guest's email is blocked or bounces? The system must handle Cognito delivery failures gracefully and inform the guest.
- How does the system handle expired OTP codes? The agent prompts the guest to request a new code.
- What happens if OAuth2 callback never arrives? Sessions have a 10-minute timeout, after which the guest must restart authentication.
- How does the system handle concurrent login attempts from the same email? Cognito handles this; if a new auth flow starts within 30 seconds of an existing pending session for the same email, treat as conflict and return existing session. Otherwise, create new session (previous session expires via TTL).
- What happens when Cognito is unavailable? The agent should inform guests that authentication is temporarily unavailable and retry later.
- What happens when AgentCore callback service is unavailable? If `CompleteResourceTokenAuth` fails due to AgentCore service issues, mark the session as `failed`, log the error with correlation ID, and inform the guest to retry authentication. The frontend should display a user-friendly error and offer a "retry" action.

## Requirements *(mandatory)*

### Functional Requirements

**Authentication Flow**:
- **FR-001**: System MUST use Cognito `USER_AUTH` flow with `EMAIL_OTP` as the preferred challenge for passwordless authentication
- **FR-002**: System MUST support new user registration with automatic email verification via OTP
- **FR-003**: System MUST support returning user sign-in with EMAIL_OTP flow
- **FR-004**: System MUST implement 3-legged OAuth2 (3LO) flow with proper authorization URL generation

**AgentCore Identity Integration**:
- **FR-005**: Agent MUST obtain workload access tokens via `IdentityClient.get_workload_access_token()` for AgentCore API access. This single function accepts optional `user_token` or `user_id` parameters for user-delegated access.
- **FR-006**: Agent MUST use `GetResourceOAuth2Token()` to initiate OAuth2 flows with Cognito as the resource provider. This returns an authorization URL for the guest.
- **FR-007**: App callback MUST call `CompleteResourceTokenAuth(session_uri, user_identifier)` to complete OAuth2 flow. The `session_id` parameter is provided by AgentCore's redirect.
- ~~**FR-008**: System MUST support `get_workload_access_token_for_jwt()` for user-delegated access when user JWT is available~~ **REMOVED**: Covered by FR-005 (single function with parameters)
- ~~**FR-009**: System MUST support `get_workload_access_token_for_user_id()` for operations on behalf of known users~~ **REMOVED**: Covered by FR-005 (single function with parameters)

**Security Requirements**:
- **FR-010**: ~~System MUST use PKCE (code_challenge, code_verifier) for OAuth2 authorization code flow~~ **CORRECTED**: AgentCore handles PKCE internally. Application does NOT store code_verifier.
- **FR-011**: ~~System MUST validate OAuth2 state parameter to prevent CSRF attacks~~ **CORRECTED**: AgentCore manages state internally. App receives `session_id` (sessionUri) in callback redirect.
- **FR-012**: System MUST implement user identity verification: correlate the user who initiated the OAuth2 flow with the user completing it (via `user_identifier` in `CompleteResourceTokenAuth`)
- **FR-013**: OTP codes MUST expire after 5 minutes
- **FR-014**: OTP code entry MUST be limited to 3 attempts per code

**Infrastructure**:
- **FR-015**: Cognito User Pool MUST be configured for Essentials tier (required for EMAIL_OTP)
- **FR-016**: Cognito User Pool MUST have `AllowedFirstAuthFactors` configured to include `EMAIL_OTP`
- **FR-017**: AgentCore Identity credential provider configuration is managed by `terraform-aws-agentcore` module; implementation MUST consume module outputs for provider names/ARNs via Terraform input variables (NOT via .env files or manual configuration)
- **FR-018**: OAuth2 callback API MUST be deployed via `infrastructure/modules/gateway-v2` Terraform module
- **FR-019**: Gateway-v2 module MUST use `terraform-aws-modules/lambda/aws` (>=8.1.2) to deploy FastAPI as Lambda function
- **FR-020**: Gateway-v2 module MUST accept relative path to FastAPI app and use `terraform_data` for build commands
- **FR-021**: Gateway-v2 module MUST use API Gateway HTTP API with `$default` stage (clean URLs without stage prefix)
- **FR-022**: CloudFront distribution MUST add API Gateway as an origin with `/api` path prefix routing
- **FR-023**: OAuth2 sessions DynamoDB table MUST be created as standalone resource in `infrastructure/main.tf` (NOT part of terraform-aws-agentcore module)

### Key Entities

- **Guest**: User making a reservation. Identified by email address and `cognito_sub`.
- **WorkloadToken**: JWT token representing the agent's identity for AgentCore API calls. Managed by IdentityClient. Single token type with optional user delegation.
- **OAuth2Session**: Simplified session tracking for user identity correlation. Contains `session_id` (from AgentCore's `sessionUri`), `conversation_id`, `guest_email`, `status`, and `expires_at`. Does NOT store `state` or `code_verifier` (AgentCore handles these internally).
- **CredentialProvider**: AgentCore Identity configuration linking the agent to Cognito OAuth2 resource. Managed by `terraform-aws-agentcore` module.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Guests can complete passwordless EMAIL_OTP authentication in under 90 seconds. **Measurement**: Server-side timing from `initiate_cognito_login` tool invocation timestamp to `verify_cognito_otp` success response timestamp. Excludes network latency and user input time; measures only backend processing + Cognito API latency.
- **SC-002**: OTP codes are delivered to 95%+ of guests within 60 seconds. **Measurement**: Cognito delivery metrics (CloudWatch `EMAIL_OTP_DELIVERY_SUCCESS` within 60s of `initiate_cognito_login`).
- **SC-003**: OAuth2 callback processing completes in under 2 seconds
- **SC-004**: Zero authentication-related double-bookings or session confusion in concurrent scenarios
- **SC-005**: Agent workload token refresh happens seamlessly with no user-facing latency impact
- **SC-006**: 99.9% of OAuth2 flows complete successfully (excluding user abandonment)

## Technical Context

### AgentCore Identity APIs (boto3)

The implementation will use these bedrock-agentcore Identity APIs:

```python
from bedrock_agentcore.services.identity import IdentityClient

identity_client = IdentityClient()

# Agent workload identity - SINGLE function with optional parameters
workload_token = identity_client.get_workload_access_token()  # Anonymous agent token
workload_token = identity_client.get_workload_access_token(user_token=jwt)  # User-delegated via JWT
workload_token = identity_client.get_workload_access_token(user_id=id)  # User-delegated via user ID

# OAuth2 resource access - Two-stage callback flow
# Stage 1: Get authorization URL
oauth2_response = identity_client.get_resource_oauth2_token(
    provider_name="CognitoIdentityProvider",
    scopes=["openid", "email"],
    auth_flow="USER_FEDERATION",
    callback_url="https://your-app.com/api/auth/callback"
)
# oauth2_response contains authorization_url for guest to visit

# Stage 2: AgentCore redirects to YOUR callback with session_id
# YOUR callback receives: GET /api/auth/callback?session_id=<agentcore_session_uri>
# Then call CompleteResourceTokenAuth to verify user and get tokens:
tokens = identity_client.complete_resource_token_auth(
    session_uri=session_id,  # From AgentCore's redirect
    user_identifier=guest_email  # Verify it's the same user who initiated
)
```

**Key Flow Difference**: AgentCore handles the Cognito callback internally (code exchange, PKCE verification). Your app's callback only receives a `session_id` and must call `CompleteResourceTokenAuth` with user verification.

### Cognito Configuration Requirements

```json
{
  "UserPool": {
    "Tier": "ESSENTIALS",
    "SignInPolicy": {
      "AllowedFirstAuthFactors": ["EMAIL_OTP"]
    },
    "MfaConfiguration": "OFF"
  }
}
```

### Strands Agent Tool Pattern

```python
import jwt  # pyjwt
from strands import tool
from bedrock_agentcore.identity import requires_access_token

@tool
@requires_access_token(
    provider_name="CognitoIdentityProvider",
    scopes=["openid", "email"],
    auth_flow="USER_FEDERATION",
    on_auth_url=stream_auth_url_to_client,
    callback_url=oauth2_callback_endpoint
)
async def get_my_reservations(*, access_token: str):
    """Get reservations for the authenticated guest."""
    # Extract user identity from JWT claims (signature already verified by AgentCore)
    claims = jwt.decode(access_token, options={"verify_signature": False})
    cognito_sub = claims["sub"]

    # Look up guest by Cognito identity
    db = get_dynamodb_service()
    guest = db.get_guest_by_cognito_sub(cognito_sub)

    # Query reservations for this guest
    return db.get_reservations_by_guest(guest.guest_id)
```

### Frontend SDK Requirements

The frontend MUST use official AWS SDK components rather than custom implementations:

- **Authentication UI**: Use `@aws-amplify/ui-react` `Authenticator` component configured for passwordless EMAIL_OTP flow
- **AWS Client**: Use `@aws-sdk/client-bedrock-agentcore` with `fromCognitoIdentityPool` credentials (already established in Feature 001)
- **Cognito Integration**: Use `@aws-amplify/auth` for token management and session handling
- **Token Storage**: Use Amplify defaults (localStorage) - tokens persist across browser sessions with automatic refresh handling

This aligns with Constitution Principle VI: prefer official AWS SDKs and UI components over custom code.
