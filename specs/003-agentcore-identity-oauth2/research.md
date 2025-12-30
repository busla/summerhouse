# Research: AgentCore Identity OAuth2 Login

**Branch**: `003-agentcore-identity-oauth2` | **Date**: 2025-12-29

## Decision Log

### 1. AgentCore Identity Client Integration

**Decision**: Use `IdentityClient` from `bedrock_agentcore.services.identity` with `@requires_access_token` decorator

**Rationale**:
- Official AgentCore SDK provides high-level abstractions for OAuth2 flows
- `@requires_access_token` decorator automatically handles token acquisition, refresh, and injection
- Built-in support for 3-legged OAuth via `USER_FEDERATION` auth_flow
- `on_auth_url` callback enables streaming authorization URLs directly to chat

**Alternatives Considered**:
- Raw boto3 calls to Cognito: More complex, requires manual token management
- Custom OAuth2 implementation: Reinvents existing SDK functionality

**Key API Methods**:
```python
from bedrock_agentcore.services.identity import IdentityClient

client = IdentityClient()

# Agent workload identity (anonymous)
token = await client.get_workload_access_token(workload_name="booking-agent")

# User-delegated access via JWT
token = await client.get_workload_access_token(user_token=cognito_jwt)

# User-delegated access via user ID
token = await client.get_workload_access_token(user_id="cognito-sub-uuid")

# Initiate 3LO flow - returns auth URL or tokens
result = await client.get_token(
    provider_name="CognitoIdentityProvider",
    scopes=["openid", "email"],
    auth_flow="USER_FEDERATION",
    on_auth_url=stream_url_to_client,
    callback_url="https://api.example.com/oauth2/callback",
    custom_state={"session_id": conversation_id}
)

# Complete OAuth2 after callback
tokens = await client.complete_resource_token_auth(
    session_uri=callback_session_uri,
    user_identifier=guest_email
)
```

---

### 2. Decorator Pattern for Protected Tools

**Decision**: Use `@requires_access_token` decorator on tools that require authentication

**Rationale**:
- Declarative approach: authentication requirements explicit in code
- Automatic token injection via `access_token` parameter
- Handles token refresh transparently
- `on_auth_url` callback integrates with Strands agent streaming

**Alternatives Considered**:
- Manual token acquisition in each tool: Repetitive, error-prone
- Middleware-based approach: Less explicit, harder to test

**Implementation Pattern**:
```python
from bedrock_agentcore.identity import requires_access_token
from strands import tool

def stream_auth_url_to_client(auth_url: str) -> None:
    """Callback to stream auth URL to guest via agent."""
    # Strands will handle streaming this to the chat
    pass

@tool
@requires_access_token(
    provider_name="CognitoIdentityProvider",
    scopes=["openid", "email"],
    auth_flow="USER_FEDERATION",
    on_auth_url=stream_auth_url_to_client,
    callback_url=os.getenv("OAUTH2_CALLBACK_URL")
)
async def create_reservation(*, access_token: str, dates: dict, guest_count: int):
    """Create a reservation (requires authentication)."""
    # access_token is automatically injected
    # Decode JWT to get guest identity
    pass
```

---

### 3. Cognito Passwordless Configuration

**Decision**: Use `USER_AUTH` flow with `EMAIL_OTP` as `PreferredChallenge`

**Rationale**:
- Cognito Essentials tier supports `EMAIL_OTP` as first-factor auth
- No passwords required - reduced friction for guests
- Cognito handles OTP generation, delivery, and validation
- 5-minute expiry and 3-attempt limit built into Cognito

**Alternatives Considered**:
- TOTP: Requires authenticator app setup (explicitly out of scope)
- SMS OTP: Additional cost, phone number requirement
- Cognito Hosted UI: Redirects away from agent experience

**Cognito Configuration**:
```json
{
  "UserPoolTier": "ESSENTIALS",
  "SignInPolicy": {
    "AllowedFirstAuthFactors": ["EMAIL_OTP"]
  },
  "AdvancedSecurityMode": "ENFORCED"
}
```

**Authentication Flow**:
```python
import boto3

cognito = boto3.client("cognito-idp")

# Step 1: Initiate auth
response = cognito.initiate_auth(
    AuthFlow="USER_AUTH",
    ClientId=client_id,
    AuthParameters={
        "USERNAME": guest_email,
        "PreferredChallenge": "EMAIL_OTP"
    }
)
# Returns: ChallengeName="EMAIL_OTP", Session=session_token

# Step 2: Guest enters OTP code
response = cognito.respond_to_auth_challenge(
    ClientId=client_id,
    ChallengeName="EMAIL_OTP",
    Session=session_token,
    ChallengeResponses={
        "USERNAME": guest_email,
        "EMAIL_OTP_CODE": otp_code
    }
)
# Returns: AuthenticationResult with tokens
```

---

### 4. Session Binding for OAuth2 Callbacks (CORRECTED)

**Decision**: Use DynamoDB table for user identity correlation only. AgentCore handles OAuth2 state and PKCE internally.

**Rationale**:
- AgentCore uses a **two-stage callback flow**:
  1. Cognito redirects to AgentCore's callback URL (AgentCore handles code exchange and PKCE verification)
  2. AgentCore redirects to YOUR app's callback with `session_id` (sessionUri) parameter
- **Why DynamoDB table is needed**: Unlike browser-based apps (which use cookies to identify users in callbacks), agent conversations have no browser session. The DynamoDB table serves as a **conversation-to-callback bridge**:
  - Agent initiates OAuth2 → stores `session_id → guest_email` mapping
  - HTTP callback receives `session_id` → looks up `guest_email` from table
  - Callback calls `CompleteResourceTokenAuth` with correct `user_identifier`
- AWS documentation shows browser pattern using `validate_session_cookies()` - we use DynamoDB instead
- `CompleteResourceTokenAuth(session_uri, user_identifier)` verifies user identity
- DynamoDB TTL cleans up abandoned sessions (10-minute expiry matches AgentCore session validity)

**Key Correction**: App does NOT store `state` or `code_verifier` - AgentCore manages these internally.

**Session Schema** (simplified):
```python
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

class OAuth2SessionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    EXPIRED = "expired"
    FAILED = "failed"

class OAuth2Session(BaseModel):
    """OAuth2 session for user identity correlation only."""
    model_config = ConfigDict(strict=True)

    session_id: str  # PK - From AgentCore's sessionUri in callback
    conversation_id: str  # Links to agent conversation
    guest_email: str  # User who initiated the flow
    status: OAuth2SessionStatus = OAuth2SessionStatus.PENDING
    created_at: datetime
    expires_at: int  # TTL epoch timestamp - 10 minutes from creation
```

**Flow** (corrected):
1. Agent calls tool requiring auth → `GetResourceOAuth2Token()` initiates OAuth2
2. AgentCore generates auth URL with PKCE/state (app doesn't see these)
3. Store `OAuth2Session(session_id, conversation_id, guest_email)` for later correlation
4. Stream auth URL to guest via `on_auth_url` callback
5. Guest completes Cognito login → Cognito redirects to AgentCore
6. AgentCore exchanges code for tokens → redirects to app callback with `session_id`
7. App callback receives `session_id`, looks up stored session to get `guest_email`
8. App calls `CompleteResourceTokenAuth(session_uri=session_id, user_identifier=guest_email)`
9. AgentCore verifies user, returns tokens to app

---

### 5. PKCE Implementation (CORRECTED)

**Decision**: ~~Application implements PKCE~~ → AgentCore handles PKCE internally. Application does NOT generate or store PKCE parameters.

**Rationale**:
- PKCE (S256 code challenge method) prevents authorization code interception attacks
- AgentCore's two-stage callback architecture means:
  - AgentCore generates `code_verifier` and `code_challenge` internally
  - AgentCore's callback URL receives the authorization code from Cognito
  - AgentCore performs the code exchange with PKCE verification
  - App callback only receives `session_id` (sessionUri), not raw authorization code
- Application security boundary is user identity verification, not PKCE

**Key Correction**: The original implementation section showing `generate_pkce_pair()` is NOT needed. AgentCore handles this entirely.

**What the App Actually Does**:
```python
# App does NOT do PKCE - instead it verifies user identity:
tokens = await client.complete_resource_token_auth(
    session_uri=callback_session_id,  # From AgentCore's redirect
    user_identifier=guest_email  # Verify same user who initiated flow
)
```

**Alternatives Considered**:
- ~~Custom PKCE implementation~~: Not needed - AgentCore handles it
- Client secret: Not applicable for this architecture (public client)

---

### 6. AgentCore Identity Provider Configuration

**Decision**: Configure Cognito as OAuth2 resource provider in AgentCore Identity

**Rationale**:
- AgentCore requires registered credential providers for OAuth2 flows
- Provider configuration links Cognito User Pool to AgentCore Identity
- Enables `get_token()` and `complete_resource_token_auth()` calls

**Provider Configuration** (via AgentCore Console or API):
```json
{
  "provider_name": "CognitoIdentityProvider",
  "provider_type": "OAUTH2",
  "oauth2_config": {
    "authorization_endpoint": "https://{domain}.auth.{region}.amazoncognito.com/oauth2/authorize",
    "token_endpoint": "https://{domain}.auth.{region}.amazoncognito.com/oauth2/token",
    "client_id": "{cognito_app_client_id}",
    "scopes": ["openid", "email", "profile"]
  }
}
```

---

### 7. JWT Claims Extraction for DynamoDB Lookups

**Decision**: Use `pyjwt` to decode JWT and extract `sub` claim for guest identity lookups

**Rationale**:
- JWT signature is already verified by AgentCore during OAuth2 flow
- Claims extraction is a cheap operation (~1ms), no network call
- `sub` claim is the stable Cognito user identifier (UUID format)
- Guest model already has `cognito_sub` field with `cognito-sub-index` GSI

**Alternatives Considered**:
- `python-jose`: More complex API, includes unnecessary JOSE features
- Create shared utility function: Adds indirection, harder to test tools in isolation
- Use `email` claim instead of `sub`: Email can change, `sub` is immutable

**Implementation Pattern**:
```python
import jwt  # pyjwt

@tool
@requires_access_token(...)
async def get_my_reservations(*, access_token: str):
    # Signature already verified by AgentCore - just extract claims
    claims = jwt.decode(access_token, options={"verify_signature": False})
    cognito_sub = claims["sub"]

    db = get_dynamodb_service()
    guest = db.get_guest_by_cognito_sub(cognito_sub)
    return db.get_reservations_by_guest(guest.guest_id)
```

---

## Open Questions (Resolved)

| Question | Resolution |
|----------|------------|
| Where does `@requires_access_token` come from? | `bedrock_agentcore.identity` module |
| How does `on_auth_url` integrate with Strands? | Callback function receives URL string, agent streams to client |
| What auth_flow for 3LO? | `USER_FEDERATION` for user-facing OAuth2 |
| How to bind callbacks to sessions? | **CORRECTED**: AgentCore provides `session_id` in callback redirect; app stores `session_id` ↔ `guest_email` mapping for `CompleteResourceTokenAuth` user verification |
| Why use DynamoDB instead of cookies? | **CLARIFIED**: Agent conversations have no browser session. DynamoDB serves as "conversation-to-callback bridge" - browser apps use cookies, agent apps use DynamoDB lookup |
| PKCE code verifier storage? | **CORRECTED**: App does NOT store code_verifier. AgentCore handles PKCE internally via two-stage callback. |
| Why separate workload token functions? | **CORRECTED**: `get_workload_access_token()` is ONE function with optional `user_token` or `user_id` parameters |
| What does app callback receive? | `session_id` (sessionUri) from AgentCore's redirect, NOT the raw authorization code |
| How does app complete OAuth2? | Call `CompleteResourceTokenAuth(session_uri, user_identifier)` to verify user and receive tokens |
| How is JWT delivered to agent tools? | `@requires_access_token` decorator automatically injects token via `access_token` parameter after OAuth2 flow completes |
| How do tools extract user identity from JWT? | Use `pyjwt` to decode token and extract `sub` claim, then query `cognito-sub-index` GSI |

---

## References

- [AgentCore Identity API Reference](https://awslabs.github.io/agents/bedrock-agentcore/api/bedrock_agentcore/services/identity/)
- [AgentCore Identity Quickstart](https://awslabs.github.io/agents/bedrock-agentcore/user-guide/identity/)
- [**AgentCore OAuth2 Session Binding**](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/oauth2-authorization-url-session-binding.html) - Critical reference for understanding session binding pattern
- [Cognito USER_AUTH Authentication Flow](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-authentication-flow-methods.html)
- [OAuth2 PKCE RFC 7636](https://datatracker.ietf.org/doc/html/rfc7636)
