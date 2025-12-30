# Data Model: AgentCore Identity OAuth2 with Amplify EMAIL_OTP

**Feature Branch**: `005-agentcore-amplify-oauth2`
**Date**: 2025-12-30
**Source**: [spec.md](./spec.md), [research.md](./research.md)

## Overview

This document defines the data entities for the AgentCore Identity OAuth2 flow. Unlike spec 004 (agent-initiated auth), this feature uses **AgentCore-managed** entities for OAuth2 sessions and tokens.

### Key Difference from Spec 004

| Aspect | Spec 004 (Agent-Initiated) | Spec 005 (OAuth2) |
|--------|---------------------------|-------------------|
| Frontend Token Storage | Frontend localStorage | Amplify Auth session (browser) |
| Agent Token Access | JWT claims passed in payload | AgentCore TokenVault (guardrail) |
| Session State | DynamoDB (custom) | AgentCore-managed |
| Auth Trigger | Backend `AdminInitiateAuth` | `@requires_access_token` decorator |
| User Identity | JWT claims in payload | Agent extracts claims from TokenVault JWT |

### Critical Clarification: TokenVault Purpose

**TokenVault does NOT replace browser session storage**. They serve distinct purposes:

| Storage | Purpose | Owner |
|---------|---------|-------|
| **Amplify Session (Browser)** | User authentication state for frontend UI | Frontend |
| **AgentCore TokenVault** | Guardrail for agent - JWT tokens for DynamoDB query authorization | Agent Runtime |

The agent needs the JWT token to extract claims (`sub`, `email`) and scope DynamoDB queries to user-specific data. This prevents the agent from accessing other users' data.

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AgentCore Identity (Managed)                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────┐       ┌──────────────────────┐                │
│  │ OAuth2CredentialProv │       │   WorkloadIdentity   │                │
│  │──────────────────────│       │──────────────────────│                │
│  │ provider_id (PK)     │       │ identity_id (PK)     │                │
│  │ name                 │◄──────│ credential_providers │                │
│  │ vendor: "Cognito"    │       │ allowed_return_urls  │                │
│  │ client_id            │       │ runtime_arn          │                │
│  │ client_secret        │       └──────────────────────┘                │
│  │ discovery_url        │                │                               │
│  └──────────────────────┘                │                               │
│           │                              │                               │
│           ▼                              ▼                               │
│  ┌──────────────────────┐       ┌──────────────────────┐                │
│  │ AuthorizationSession │       │     TokenVault       │                │
│  │──────────────────────│       │──────────────────────│                │
│  │ session_uri (PK)     │──────►│ user_id              │                │
│  │ expires_at           │       │ provider_id          │                │
│  │ custom_state (CSRF)  │       │ access_token (enc)   │                │
│  │ status: pending/done │       │ refresh_token (enc)  │                │
│  └──────────────────────┘       │ expires_at           │                │
│                                 └──────────────────────┘                │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                        Cognito (Existing)                                │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────┐                                               │
│  │    CognitoUser       │                                               │
│  │──────────────────────│                                               │
│  │ sub (PK)             │──────────────────────┐                        │
│  │ email (unique)       │                      │                        │
│  │ name                 │                      │                        │
│  │ email_verified       │                      │                        │
│  └──────────────────────┘                      │                        │
└─────────────────────────────────────────────────│────────────────────────┘
                                                  │
┌─────────────────────────────────────────────────│────────────────────────┐
│                        DynamoDB (Existing)       │                        │
├─────────────────────────────────────────────────│────────────────────────┤
│  ┌──────────────────────┐                      │                        │
│  │       Guest          │◄─────────────────────┘                        │
│  │──────────────────────│                                               │
│  │ guest_id (PK)        │                                               │
│  │ cognito_sub (GSI)    │                                               │
│  │ email                │                                               │
│  │ name                 │                                               │
│  │ email_verified       │                                               │
│  │ created_at           │                                               │
│  │ updated_at           │                                               │
│  └──────────────────────┘                                               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## AgentCore-Managed Entities

These entities are created and managed by AgentCore Identity. We configure them via Terraform but don't directly manipulate them at runtime.

### OAuth2CredentialProvider

Stores Cognito client credentials for OAuth2 token exchange.

| Field | Type | Description |
|-------|------|-------------|
| `provider_id` | String | AgentCore-assigned unique identifier |
| `name` | String | Human-readable name (e.g., `booking-dev-cognito`) |
| `credential_provider_vendor` | Enum | Always `"Cognito"` for this feature |
| `client_id` | String | Cognito User Pool Client ID |
| `client_secret` | String | Cognito User Pool Client Secret (encrypted) |
| `discovery_url` | String | OIDC discovery URL for Cognito |

**Terraform Configuration**:
```hcl
resource "aws_bedrockagentcore_oauth2_credential_provider" "cognito" {
  name                        = "${module.label.id}-cognito"
  credential_provider_vendor  = "Cognito"

  oauth2_provider_config {
    custom_oauth2_provider_config {
      client_id     = aws_cognito_user_pool_client.agent.id
      client_secret = aws_cognito_user_pool_client.agent.client_secret
      oauth_discovery {
        discovery_url = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.main.id}/.well-known/openid-configuration"
      }
    }
  }
}
```

---

### WorkloadIdentity

Represents the agent application and its allowed OAuth2 callback URLs.

| Field | Type | Description |
|-------|------|-------------|
| `identity_id` | String | AgentCore-assigned unique identifier |
| `name` | String | Human-readable name (e.g., `booking-dev-agent`) |
| `allowed_resource_oauth2_return_urls` | List[String] | Allowed callback URLs for session binding |
| `credential_provider_arns` | List[String] | ARNs of linked OAuth2 credential providers |

**Terraform Configuration**:
```hcl
resource "aws_bedrockagentcore_workload_identity" "agent" {
  name = "${module.label.id}-agent"

  allowed_resource_oauth2_return_urls = [
    "https://${var.domain}/auth/callback"
  ]

  # Link to credential provider
  credential_provider_arns = [
    aws_bedrockagentcore_oauth2_credential_provider.cognito.arn
  ]
}
```

---

### AuthorizationSession

Temporary session created when agent requests OAuth2 token. Managed entirely by AgentCore.

| Field | Type | Description |
|-------|------|-------------|
| `session_uri` | String | Unique session identifier (passed in callback URL) |
| `expires_at` | DateTime | Session expiration (10 minutes from creation) |
| `custom_state` | String | CSRF protection token |
| `status` | Enum | `pending` (awaiting binding) or `completed` |
| `credential_provider_id` | String | Reference to OAuth2CredentialProvider |

**Lifecycle**:
1. Created by AgentCore when `@requires_access_token` tool is invoked without valid token
2. Passed to user via authorization URL (`session_id` query parameter)
3. Completed via `CompleteResourceTokenAuth` API call
4. Expires after 10 minutes if not completed

---

### TokenVault

Secure storage for OAuth2 tokens. Managed entirely by AgentCore. **Acts as a guardrail for the agent** - not a replacement for browser session storage.

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | String | User identifier (Cognito sub or custom) |
| `provider_id` | String | Reference to OAuth2CredentialProvider |
| `access_token` | String | Encrypted OAuth2 access token (JWT) |
| `refresh_token` | String | Encrypted OAuth2 refresh token |
| `expires_at` | DateTime | Token expiration time |

**Token Retrieval**:
- AgentCore automatically retrieves tokens for authenticated users
- Tokens are refreshed automatically when expired
- Agent tools receive tokens via `@requires_access_token` decorator

**Why Agent Needs JWT**:
- Agent extracts claims (`sub`, `email`) from the JWT
- Claims are used to scope DynamoDB queries to user-specific data
- Example: `reservations WHERE cognito_sub = {sub_from_jwt}`
- This prevents the agent from accessing other users' sensitive data

---

## Cognito Entities

### CognitoUser

Existing Cognito User Pool user entity. No schema changes required.

| Field | Type | Description |
|-------|------|-------------|
| `sub` | UUID | Cognito-assigned unique identifier |
| `email` | String | User's email address (username) |
| `name` | String | User's display name |
| `email_verified` | Boolean | Always `true` after EMAIL_OTP |

**Configuration Changes Required**:
```typescript
// Cognito User Pool must allow EMAIL_OTP
cfnUserPool.addPropertyOverride(
  'Policies.SignInPolicy.AllowedFirstAuthFactors',
  ['EMAIL_OTP']
);

// User Pool Client must allow USER_AUTH flow
cfnUserPoolClient.explicitAuthFlows = [
  'ALLOW_REFRESH_TOKEN_AUTH',
  'ALLOW_USER_AUTH'
];

// Add AgentCore callback to allowed callbacks
cfnUserPoolClient.callbackUrLs = [
  'https://${domain}/auth/callback'
];
```

---

## DynamoDB Entities

### Guest (Existing - No Changes)

The existing Guest entity from spec 004 remains unchanged. AgentCore session binding uses Cognito `sub` which maps to `cognito_sub` in the Guest table.

| Field | Type | Description |
|-------|------|-------------|
| `guest_id` | String (PK) | Application-assigned guest identifier |
| `cognito_sub` | String (GSI) | Cognito user identifier |
| `email` | String | User's email address |
| `name` | String | User's display name |
| `email_verified` | Boolean | Email verification status |
| `created_at` | DateTime | Record creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

**Usage in OAuth2 Flow**:
- After `CompleteResourceTokenAuth`, agent tools can query Guest by `cognito_sub`
- No direct token storage in DynamoDB (AgentCore TokenVault handles this)

---

## Frontend State (Browser)

### AmplifyAuthSession

Amplify Auth manages session state in browser storage. This is separate from AgentCore's token management.

| Field | Type | Storage | Description |
|-------|------|---------|-------------|
| `idToken` | JWT | Memory/Cookie | Cognito ID token |
| `accessToken` | JWT | Memory/Cookie | Cognito access token |
| `refreshToken` | String | Secure storage | Cognito refresh token |
| `clockDrift` | Number | localStorage | Clock sync offset |

**Note**: Amplify stores tokens using its own secure mechanism. The callback page extracts `accessToken` for `CompleteResourceTokenAuth` but doesn't manually manage storage.

---

## Data Flow

### OAuth2 Authentication Flow

```
1. User → Agent: "I want to book March 15-20"

2. Agent → Tool: make_reservation(dates, guest_info)
   └── @requires_access_token decorator triggers

3. AgentCore → Check TokenVault
   └── No valid token for this session

4. AgentCore → Create AuthorizationSession
   └── session_uri = "abc123", expires_at = now + 10min

5. AgentCore → Agent: on_auth_url callback
   └── auth_url = "https://example.com/login?session_id=abc123"

6. Agent → User: "Please sign in: [auth_url]"

7. User → Browser: Click auth_url

8. Browser → /login: Amplify Authenticator (EMAIL_OTP)
   └── User enters email → receives OTP → confirms

9. Amplify → Cognito: Exchange code for tokens
   └── Stores tokens in AmplifyAuthSession

10. Browser → /auth/callback?session_id=abc123

11. Callback → AgentCore: CompleteResourceTokenAuth(session_uri, accessToken)
    └── AgentCore stores token in TokenVault
    └── AuthorizationSession.status = "completed"

12. Browser → Redirect to chat

13. User → Agent: (continues conversation)

14. Agent → Tool: make_reservation(dates, guest_info)
    └── @requires_access_token now has valid token
    └── Tool executes with authenticated context
```

---

## Removed Entities (from Spec 004)

The following entities/patterns from spec 004 are **removed** in this implementation:

| Entity/Pattern | Spec 004 | Spec 005 |
|----------------|----------|----------|
| `auth_token` in request payload | Required | Not used |
| `TokenDeliveryEvent` in tool response | Required | Not used |
| Frontend localStorage JWT storage | Manual | Amplify-managed |
| Backend `AdminInitiateAuth` | Required | Removed |
| `OTPChallenge` state | DynamoDB | Not needed |
| `verify_cognito_otp` tool | Required | Removed |
| `initiate_cognito_login` tool | Required | Removed |

---

## Schema Validation

### Pydantic Models (Backend)

```python
# No new Pydantic models needed for OAuth2 flow
# AgentCore handles all session/token entities

# Existing Guest model remains unchanged
class Guest(BaseModel):
    guest_id: str
    cognito_sub: str | None = None
    email: str
    name: str
    email_verified: bool = False
    created_at: datetime
    updated_at: datetime
```

### TypeScript Types (Frontend)

```typescript
// Callback page types
interface CallbackPageProps {
  sessionId: string;  // From URL query param
}

interface CompleteAuthRequest {
  sessionUri: string;
  userIdentifier: {
    userToken: string;  // Cognito access token
  };
}

interface CompleteAuthResponse {
  success: boolean;
  redirectUrl?: string;
  error?: string;
}

// Amplify session (managed by Amplify Auth)
interface AmplifySession {
  tokens?: {
    accessToken?: { toString(): string };
    idToken?: { toString(): string };
  };
  userSub?: string;
}
```

---

## Migration Notes

### From Spec 004 to Spec 005

1. **No DynamoDB migration required** - Guest table unchanged
2. **Remove localStorage auth** - Amplify handles storage
3. **Remove `auth_token` from transport** - AgentCore handles auth context
4. **Update Cognito User Pool Client** - Add AgentCore callback URL
5. **Deploy AgentCore Identity resources** - New Terraform resources
