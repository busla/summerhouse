# Research: JWT Session Authentication Flow

**Feature**: 004-jwt-session-auth
**Date**: 2025-12-30
**Status**: Complete

## Problem Statement

The current authentication implementation has an architectural gap where Cognito JWT tokens stay server-side after OTP verification. The frontend never receives them, making it impossible to:
1. Store authenticated session in browser localStorage
2. Include JWT in subsequent AgentCore requests
3. Access AgentCore Memory scoped to user identity
4. Query DynamoDB using JWT claims

## Research Questions

### RQ1: How do Strands tool return values reach the frontend?

**Finding**: Tool return values are serialized as JSON and streamed via AgentCore SSE events.

The SSE format is:
```
data: {"type": "tool-result", "toolCallId": "...", "result": {...}}\n\n
```

The frontend `agentcore-transport.ts:172-233` already parses these SSE events and extracts JSON payloads. Tool results flow directly through this channel.

**Implication**: Adding tokens to `verify_cognito_otp`'s return dict will automatically deliver them to the frontend via the existing SSE stream.

### RQ2: How does AgentCore Runtime support authenticated requests?

**Finding**: AgentCore Runtime supports OAuth via `Authorization: Bearer {jwt}` header.

From AgentCore Runtime API documentation:
- `generate_ws_connection_oauth` method accepts bearer tokens
- The SDK client can be configured with custom headers
- Anonymous Cognito Identity Pool credentials are separate from user identity tokens

**Implication**: The frontend can include the user's JWT in requests while still using Cognito Identity Pool for SigV4 signing.

### RQ3: What is the current implementation gap?

**Finding**: Two specific gaps identified:

1. **Backend gap** (`backend/src/tools/auth.py:129-203`):
   ```python
   @tool
   def verify_cognito_otp(...) -> dict[str, Any]:
       # ... OTP verification returns tokens from Cognito ...
       result, updated_state = auth_service.verify_otp_with_state(auth_state, otp_code)
       # ... but only returns guest info, NOT tokens ...
       return {
           "success": True,
           "guest_id": guest.guest_id,      # ✓ Returned
           "cognito_sub": guest.cognito_sub, # ✓ Returned
           "email": email,                   # ✓ Returned
           # MISSING: id_token, access_token, refresh_token, expires_in
       }
   ```

2. **Frontend gap** (`frontend/src/lib/agentcore-transport.ts:77-159`):
   ```typescript
   class AgentCoreChatTransport {
     async sendMessages(...) {
       // Uses anonymous Cognito Identity Pool credentials
       const credentials = await getAWSCredentials()
       // No mechanism to include user JWT in Authorization header
     }
   }
   ```

### RQ4: Is `@requires_access_token` the right pattern?

**Finding**: NO. `@requires_access_token` is designed for OAuth2 3LO (Three-Legged OAuth) with external resource providers.

The decorator:
- Triggers OAuth2 authorization flow with external providers
- Stores tokens in AgentCore Token Vault
- Is for accessing external resources (like Google Drive, GitHub)
- NOT for user authentication tokens staying client-side

Our use case is direct Cognito EMAIL_OTP authentication where:
- User authenticates directly with our Cognito User Pool
- Tokens should be stored in browser, not server
- Frontend needs tokens for subsequent authenticated requests

**Implication**: Remove `@requires_access_token` dependency from this flow. Use direct token return from `verify_cognito_otp`.

### RQ5: How should tokens be extracted from the SSE stream?

**Finding**: The frontend already processes tool results in the SSE stream. Need to detect auth-related tool results.

Proposed approach:
1. `verify_cognito_otp` returns a `TokenDeliveryEvent` object type-discriminated with `"event_type": "auth_tokens"`
2. Frontend hook watches for tool results with this event type
3. On detection, extracts tokens and stores in localStorage
4. Updates transport to include token in subsequent requests

Pattern:
```typescript
// In useAgentChat or similar hook
function processToolResult(result: unknown) {
  if (isTokenDeliveryEvent(result)) {
    storeSession({
      isAuthenticated: true,
      accessToken: result.access_token,
      idToken: result.id_token,
      refreshToken: result.refresh_token,
      expiresAt: Date.now() + result.expires_in * 1000,
      ...
    })
  }
}
```

### RQ6: How should the transport include the JWT?

**Finding**: Two options for including JWT in authenticated requests:

**Option A: Custom header in SDK client** (Preferred)
```typescript
const client = new BedrockAgentCoreClient({
  region: config.region,
  credentials,  // SigV4 signing still uses Cognito Identity Pool
  customUserAgent: undefined,
})

// Add JWT as custom header in request
const input: InvokeAgentRuntimeCommandInput = {
  agentRuntimeArn: config.runtimeArn,
  payload: payloadBytes,
  // Note: SDK may not support custom headers directly
}
```

**Option B: Include token in payload** (Fallback)
```typescript
const payload = JSON.stringify({
  prompt: userText,
  session_id: this.sessionId,
  auth_token: getAccessToken(),  // Backend extracts from payload
})
```

**Decision**: Start with Option B (token in payload) as it's guaranteed to work with the current SDK. The backend can extract the token and validate it for authenticated operations.

### RQ7: How should token refresh work?

**Finding**: Cognito tokens have the following lifetimes:
- Access Token: 5 minutes to 1 day (configurable, default 60 minutes)
- ID Token: 5 minutes to 1 day (configurable, default 60 minutes)
- Refresh Token: 1 hour to 10 years (configurable)

Refresh flow:
1. Frontend checks `expiresAt` before each request
2. If within 5 minutes of expiry, call `InitiateAuth` with `REFRESH_TOKEN_AUTH` flow
3. Update stored session with new tokens
4. Continue with request

**Note**: For MVP, we can use `AdminInitiateAuth` with `REFRESH_TOKEN_AUTH` via a backend API endpoint, avoiding Cognito SDK in frontend.

## Architecture Decision

### Token Delivery Mechanism

**Decision**: Return tokens directly in `verify_cognito_otp` tool response.

**Rationale**:
1. **Simplicity**: Leverages existing SSE stream - no new transport mechanism
2. **Security**: Tokens delivered once over HTTPS, stored client-side
3. **Compatibility**: Works with existing frontend session storage code
4. **Minimal Changes**: Only modifies tool response, not architecture

### Request Authentication

**Decision**: Include JWT in request payload (not header) for MVP.

**Rationale**:
1. **SDK Limitation**: BedrockAgentCoreClient may not support custom headers
2. **Backend Control**: Backend can validate and use token as needed
3. **Migration Path**: Can move to header-based auth later if SDK supports it

### Token Storage

**Decision**: Use localStorage with `booking_session` key (existing pattern).

**Rationale**:
1. **Existing Code**: `frontend/src/lib/auth.ts` already implements this
2. **Persistence**: Survives page refresh
3. **Tab Sharing**: Accessible from all tabs (handles edge case in spec)

## Resolved Unknowns

| Unknown | Resolution |
|---------|------------|
| Token delivery mechanism | Return in tool response, flows via SSE stream |
| AgentCore auth support | Supports OAuth but we'll use payload-based for MVP |
| @requires_access_token usage | NOT appropriate - that's for OAuth2 3LO with external providers |
| Token refresh strategy | Backend API endpoint with REFRESH_TOKEN_AUTH flow |
| Session storage location | localStorage with existing `booking_session` key |

## Implementation Sequence

1. **Backend: Modify verify_cognito_otp** - Return tokens in response dict
2. **Frontend: Token extraction** - Detect TokenDeliveryEvent in tool results
3. **Frontend: Transport update** - Include token in request payload
4. **Backend: Token validation** - Validate JWT on authenticated operations
5. **Full stack: Token refresh** - API endpoint + frontend refresh logic
6. **E2E tests** - Complete flow from OTP to authenticated request

## References

- AgentCore Runtime API: https://docs.aws.amazon.com/bedrock-agentcore/latest/runtime-api/
- AgentCore Identity API: https://docs.aws.amazon.com/bedrock-agentcore/latest/identity-api/
- Strands Tool Documentation: https://strandsagents.com/latest/user-guide/concepts/tools/
- Cognito AdminRespondToAuthChallenge: https://docs.aws.amazon.com/cognito-user-identity-pools/latest/APIReference/API_AdminRespondToAuthChallenge.html
