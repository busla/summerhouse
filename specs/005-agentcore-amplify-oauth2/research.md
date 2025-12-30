# Phase 0 Research: AgentCore Identity OAuth2 with Amplify EMAIL_OTP

**Feature Branch**: `005-agentcore-amplify-oauth2`
**Date**: 2025-12-30
**Status**: Complete

## Executive Summary

This research validates the technical approach for implementing standard AgentCore Identity OAuth2 flow with Amplify EMAIL_OTP authentication. The key finding is that **this is a well-supported pattern** with official SDK support on both frontend and backend.

### Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Auth Page Approach | Custom Amplify UI (NOT Cognito Hosted UI) | Hosted UI cannot be configured for EMAIL_OTP-only; Amplify Authenticator with custom `services` and `formFields` provides full control |
| Session Binding | `CompleteResourceTokenAuth` with `userToken` | SDK provides `CompleteResourceTokenAuthCommand` in `@aws-sdk/client-bedrock-agentcore` |
| Infrastructure | `terraform-aws-agentcore` identity module | Already supports OAuth2 credential providers and workload identity |
| Token Flow | Amplify stores Cognito tokens, callback extracts for AgentCore | Standard OAuth2 pattern with Amplify handling token lifecycle |
| TokenVault Purpose | **Agent guardrail, NOT browser storage replacement** | Agent uses JWT claims (`sub`, `email`) to scope DynamoDB queries to user-specific data |

### Critical Clarification: TokenVault vs Browser Session

**TokenVault does NOT replace Amplify's browser session storage**. They serve distinct purposes:

| Storage | Purpose | Owner |
|---------|---------|-------|
| **Amplify Session** | User authentication state for frontend UI | Browser/Frontend |
| **AgentCore TokenVault** | Guardrail - JWT tokens for agent DynamoDB query authorization | Agent Runtime |

The agent extracts JWT claims (`sub`, `email`) to scope queries:
```
reservations WHERE cognito_sub = {sub_from_jwt}
```
This prevents the agent from accessing other users' sensitive data.

---

## Research Question 1: Amplify EMAIL_OTP Configuration

**Question**: How to configure Amplify UI to show ONLY email input + OTP (no username/password)?

### Finding: Use Custom Auth Flow with Amplify Authenticator

The Amplify Authenticator component supports custom authentication flows via the `services` prop. For EMAIL_OTP-only:

```typescript
// amplify-config.ts - Configure Amplify Auth
import { Amplify } from 'aws-amplify';

Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: 'YOUR_USER_POOL_ID',
      userPoolClientId: 'YOUR_CLIENT_ID',
      signUpVerificationMethod: 'code',
    }
  }
});

// Custom signIn service for EMAIL_OTP
const services = {
  async handleSignIn({ username }: { username: string }) {
    const { signIn } = await import('aws-amplify/auth');
    return signIn({
      username,
      options: {
        authFlowType: 'USER_AUTH',
        preferredChallenge: 'EMAIL_OTP',
      },
    });
  },
};
```

### Authenticator Component Configuration

```tsx
import { Authenticator } from '@aws-amplify/ui-react';

// Hide password field via formFields customization
const formFields = {
  signIn: {
    username: {
      placeholder: 'Enter your email',
      label: 'Email',
      isRequired: true,
    },
    // NO password field defined = not shown
  },
};

// Custom component to hide unnecessary UI elements
const components = {
  SignIn: {
    Footer() {
      // Hide "Forgot Password" link (not applicable for passwordless)
      return null;
    },
  },
};

export function AuthPage() {
  return (
    <Authenticator
      formFields={formFields}
      services={services}
      components={components}
      loginMechanisms={['email']}
      hideSignUp={false} // Allow signup with same EMAIL_OTP flow
    >
      {({ user }) => <AuthenticatedContent user={user} />}
    </Authenticator>
  );
}
```

### Cognito User Pool Requirements

The User Pool must be configured for passwordless auth:

```typescript
// CDK/Amplify backend override
cfnUserPool.addPropertyOverride(
  'Policies.SignInPolicy.AllowedFirstAuthFactors',
  ['EMAIL_OTP']  // EMAIL_OTP only - no PASSWORD
);

cfnUserPoolClient.explicitAuthFlows = [
  'ALLOW_REFRESH_TOKEN_AUTH',
  'ALLOW_USER_AUTH'  // Required for USER_AUTH flow
];
```

**Source**: [Amplify Docs - Switching Authentication Flows](https://docs.amplify.aws/react/build-a-backend/auth/connect-your-frontend/switching-authentication-flows/)

---

## Research Question 2: Cognito Hosted UI vs Custom Amplify UI

**Question**: Can Hosted UI be configured for EMAIL_OTP-only, or do we need custom Amplify UI?

### Finding: Cognito Hosted UI Does NOT Support EMAIL_OTP-Only

Cognito Hosted UI is designed for traditional OAuth2 flows with username/password. It **cannot** be configured to:
- Hide the password field
- Use EMAIL_OTP as the primary/only authentication method
- Customize the auth flow to USER_AUTH

### Recommendation: Use Custom Amplify UI

Build a custom `/login` page using Amplify UI components:

| Feature | Hosted UI | Custom Amplify UI |
|---------|-----------|-------------------|
| EMAIL_OTP only | Not supported | Supported via `services` prop |
| Hide password field | Not supported | Supported via `formFields` prop |
| Custom branding | Limited CSS | Full React component control |
| OAuth2 redirect | Built-in | Manual redirect after auth |
| AgentCore callback | Requires custom page anyway | Integrated in same app |

The callback page (`/auth/callback`) must be custom regardless, so building the login page custom provides consistency.

---

## Research Question 3: CompleteResourceTokenAuth SDK

**Question**: Exact parameters and error handling for `@aws-sdk/client-bedrock-agentcore`

### Finding: SDK Provides Complete Support

The `@aws-sdk/client-bedrock-agentcore` package includes `CompleteResourceTokenAuthCommand`:

```typescript
import {
  BedrockAgentCoreClient,
  CompleteResourceTokenAuthCommand,
} from '@aws-sdk/client-bedrock-agentcore';

// Create client with Cognito Identity credentials
const client = new BedrockAgentCoreClient({
  region: 'us-east-1',
  credentials: fromCognitoIdentityPool({
    clientConfig: { region: 'us-east-1' },
    identityPoolId: 'us-east-1:xxxxx',
  }),
});

// Complete session binding
const command = new CompleteResourceTokenAuthCommand({
  sessionUri: 'session_id_from_callback_url',  // Required
  userIdentifier: {
    // Union type - use ONE of:
    userToken: 'cognito_access_token',  // Preferred: pass Cognito token
    // OR
    // userId: 'cognito_sub',           // Alternative: pass user ID
  },
});

try {
  const response = await client.send(command);
  // Success - session is bound, redirect to chat
} catch (error) {
  if (error.name === 'ValidationException') {
    // Invalid session_uri or expired
  } else if (error.name === 'AccessDeniedException') {
    // Credential provider mismatch or invalid token
  }
}
```

### Error Handling

| Error | Cause | Recovery |
|-------|-------|----------|
| `ValidationException` | Session expired (>10 min) or invalid session_uri | Redirect back to chat, agent will generate new auth URL |
| `AccessDeniedException` | Token doesn't match credential provider | Verify Cognito client ID matches OAuth2 credential provider |
| `ResourceNotFoundException` | Session already completed or doesn't exist | Redirect to chat (may already be authenticated) |
| `ThrottlingException` | Rate limit exceeded | Retry with exponential backoff |

**Source**: [AWS SDK v3 - BedrockAgentCoreClient](https://docs.aws.amazon.com/AWSJavaScriptSDK/v3/latest/client/bedrock-agentcore/)

---

## Research Question 4: Session URI Format

**Question**: How is `session_uri` passed in the authorization URL?

### Finding: Query Parameter `session_id`

The authorization URL includes the session identifier as a query parameter:

```
https://your-domain.com/auth/callback?session_id=<session_uri>&custom_state=<csrf_token>
```

### OAuth2 Authorization URL Flow

1. **Agent tool triggers auth** (`@requires_access_token` decorator)
2. **AgentCore generates auth URL** via `GetResourceOauth2Token`
3. **Auth URL structure**:
   ```
   https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/oauth2/authorize?
     client_id={client_id}&
     response_type=code&
     redirect_uri={callback_url}&
     state={session_id}|{custom_state}&
     scope=openid+email+profile
   ```
4. **After Cognito auth**, redirect to callback with `session_id` extracted from state

### Callback Page Flow

```typescript
// /auth/callback/page.tsx
export default function CallbackPage() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get('session_id');

  useEffect(() => {
    async function completeAuth() {
      // 1. Get Cognito token from Amplify
      const session = await fetchAuthSession();
      const accessToken = session.tokens?.accessToken?.toString();

      // 2. Call CompleteResourceTokenAuth
      await completeSessionBinding(sessionId, accessToken);

      // 3. Redirect to chat
      window.location.href = '/';
    }
    completeAuth();
  }, [sessionId]);
}
```

**Source**: [AWS Docs - OAuth2 Session Binding](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/oauth2-authorization-url-session-binding.html)

---

## Research Question 5: ai-elements Catalogue

**Question**: Does ai-elements have authentication/OTP components we should use?

### Finding: Not Applicable for This Feature

The ai-elements catalogue (if it exists in this project) is for AI chat UI components, not authentication. For authentication:

- **Use Amplify UI React** (`@aws-amplify/ui-react`) for the Authenticator component
- **Use Vercel AI SDK** (`ai`, `@ai-sdk/react`) for the chat interface (existing)

The authentication page is a standalone route that doesn't need AI-specific components.

---

## terraform-aws-agentcore Module Analysis

### Identity Module Structure

Located at `terraform-aws-agentcore/modules/identity/`:

```hcl
# OAuth2 Credential Provider
resource "aws_bedrockagentcore_oauth2_credential_provider" "this" {
  for_each = var.oauth2_providers

  name = "${module.this.id}-${each.key}"
  credential_provider_vendor = each.value.vendor  # "Cognito"

  oauth2_provider_config {
    custom_oauth2_provider_config {
      client_id     = each.value.client_id
      client_secret = each.value.client_secret
      oauth_discovery {
        discovery_url = each.value.discovery_url
        # Format: https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration
      }
    }
  }
}

# Workload Identity (for callback URLs)
resource "aws_bedrockagentcore_workload_identity" "this" {
  count = var.workload_identity_enabled ? 1 : 0

  name = module.this.id
  allowed_resource_oauth2_return_urls = var.allowed_resource_oauth2_return_urls
  # Must include: https://{domain}/auth/callback
}
```

### OAuth Callback Module

Located at `terraform-aws-agentcore/modules/oauth-callback/`:

Outputs `callback_url` that must be:
1. Added to Cognito User Pool Client allowed callback URLs
2. Added to Workload Identity `allowed_resource_oauth2_return_urls`

---

## Implementation Approach

### Phase 1: Infrastructure (Terraform)

1. **Update identity module call** with Cognito OAuth2 provider:
   ```hcl
   oauth2_providers = {
     cognito = {
       vendor        = "Cognito"
       client_id     = module.cognito.client_id
       client_secret = module.cognito.client_secret
       discovery_url = "https://cognito-idp.${var.region}.amazonaws.com/${module.cognito.user_pool_id}/.well-known/openid-configuration"
     }
   }
   ```

2. **Configure workload identity** with callback URLs:
   ```hcl
   allowed_resource_oauth2_return_urls = [
     "https://${var.domain}/auth/callback"
   ]
   ```

### Phase 2: Backend (Python)

1. **Remove agent-initiated auth tools** (`initiate_cognito_login`, `verify_cognito_otp`)
2. **Add `@requires_access_token` decorator** to reservation tools
3. **Implement `on_auth_url` callback** to stream authorization URL to user
4. **Use JWT claims as guardrail** - extract `sub`, `email` from token to scope DynamoDB queries to user-specific data

### Phase 3: Frontend (TypeScript)

1. **Create `/login` page** with Amplify Authenticator (EMAIL_OTP only)
2. **Create `/auth/callback` page** with `CompleteResourceTokenAuth` call
3. **Configure Amplify** for USER_AUTH flow

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Cognito Hosted UI doesn't support EMAIL_OTP | High | Use custom Amplify UI (validated approach) |
| Session binding fails silently | Medium | Implement comprehensive error handling with user feedback |
| Authorization URL expires before user completes auth | Low | 10-minute window is sufficient; agent can regenerate |
| Token refresh during callback | Low | Amplify handles refresh automatically |

---

## Dependencies Confirmed

### Frontend
- `@aws-amplify/ui-react` ^6.x - Authenticator component
- `@aws-amplify/auth` ^6.x - Auth APIs (signIn, confirmSignIn)
- `@aws-sdk/client-bedrock-agentcore` - CompleteResourceTokenAuth
- `@aws-sdk/credential-providers` - fromCognitoIdentityPool

### Backend
- `strands-agents` - Agent framework
- `bedrock-agentcore` - `@requires_access_token` decorator
- `boto3` - AWS SDK (if needed for backend operations)

### Infrastructure
- `terraform-aws-agentcore` - Identity module
- Existing Cognito User Pool (from spec 004)

---

## Next Steps

1. **Phase 1: Design** - Create data-model.md with OAuth2 entities
2. **Phase 1: Contracts** - Define tool response formats and callback API
3. **Phase 1: Quickstart** - Local development setup guide
4. **Phase 2: Tasks** - Generate implementation tasks via `/speckit.tasks`
