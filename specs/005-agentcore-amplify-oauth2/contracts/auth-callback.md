# Contract: OAuth2 Authentication Callback

**Feature Branch**: `005-agentcore-amplify-oauth2`
**Date**: 2025-12-30
**Endpoint**: `/auth/callback`

## Overview

The callback page handles session binding after successful Cognito EMAIL_OTP authentication. It extracts the session identifier from the URL and calls AgentCore's `CompleteResourceTokenAuth` API to bind the user's identity to the agent session.

---

## Callback URL Format

```
GET /auth/callback?session_id={session_uri}&custom_state={csrf_token}
```

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | String | Yes | AgentCore authorization session identifier |
| `custom_state` | String | No | CSRF token for additional validation |

### Example URL

```
https://booking.example.com/auth/callback?session_id=abc123-def456-ghi789&custom_state=csrf_token_value
```

---

## Callback Page Flow

```typescript
// /auth/callback/page.tsx

'use client';

import { useSearchParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { fetchAuthSession } from 'aws-amplify/auth';
import { completeSessionBinding } from '@/lib/agentcore-auth';

export default function CallbackPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [error, setError] = useState<string | null>(null);

  const sessionId = searchParams.get('session_id');

  useEffect(() => {
    async function handleCallback() {
      if (!sessionId) {
        setError('Missing session_id parameter');
        setStatus('error');
        return;
      }

      try {
        // 1. Get Cognito token from Amplify session
        const session = await fetchAuthSession();
        const accessToken = session.tokens?.accessToken?.toString();

        if (!accessToken) {
          throw new Error('No access token available');
        }

        // 2. Complete session binding
        await completeSessionBinding(sessionId, accessToken);

        // 3. Redirect to chat
        setStatus('success');
        router.push('/');
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        setStatus('error');
      }
    }

    handleCallback();
  }, [sessionId, router]);

  // Render loading/success/error states
}
```

---

## CompleteResourceTokenAuth API

### Request

```typescript
// @aws-sdk/client-bedrock-agentcore
import {
  BedrockAgentCoreClient,
  CompleteResourceTokenAuthCommand,
} from '@aws-sdk/client-bedrock-agentcore';

const command = new CompleteResourceTokenAuthCommand({
  sessionUri: sessionId,      // Required: from callback URL
  userIdentifier: {
    userToken: accessToken,   // Cognito access token
  },
});

const response = await client.send(command);
```

### Request Schema

```typescript
interface CompleteResourceTokenAuthRequest {
  sessionUri: string;         // Required
  userIdentifier: UserIdentifier;
}

// Union type - exactly ONE field must be present
type UserIdentifier =
  | { userToken: string }     // OAuth2 access token
  | { userId: string };       // User identifier string
```

### Response

```typescript
interface CompleteResourceTokenAuthResponse {
  // Empty response on success (HTTP 200)
}
```

### Error Responses

| HTTP Status | Error Code | Description | Recovery |
|-------------|------------|-------------|----------|
| 400 | `ValidationException` | Invalid session_uri format | Check URL parameter |
| 403 | `AccessDeniedException` | Token doesn't match credential provider | Verify Cognito configuration |
| 404 | `ResourceNotFoundException` | Session not found or expired | Return to chat for new auth URL |
| 409 | `ConflictException` | Session already completed | May already be authenticated |
| 429 | `ThrottlingException` | Rate limit exceeded | Retry with backoff |

---

## AgentCore Auth Library

### Implementation

```typescript
// /lib/agentcore-auth.ts

import {
  BedrockAgentCoreClient,
  CompleteResourceTokenAuthCommand,
} from '@aws-sdk/client-bedrock-agentcore';
import { fromCognitoIdentityPool } from '@aws-sdk/credential-providers';

const client = new BedrockAgentCoreClient({
  region: process.env.NEXT_PUBLIC_AWS_REGION!,
  credentials: fromCognitoIdentityPool({
    clientConfig: { region: process.env.NEXT_PUBLIC_AWS_REGION! },
    identityPoolId: process.env.NEXT_PUBLIC_COGNITO_IDENTITY_POOL_ID!,
  }),
});

export interface CompleteSessionBindingResult {
  success: boolean;
  error?: string;
}

export async function completeSessionBinding(
  sessionUri: string,
  userToken: string
): Promise<CompleteSessionBindingResult> {
  try {
    await client.send(
      new CompleteResourceTokenAuthCommand({
        sessionUri,
        userIdentifier: { userToken },
      })
    );
    return { success: true };
  } catch (error) {
    if (error instanceof Error) {
      // Map specific errors to user-friendly messages
      if (error.name === 'ResourceNotFoundException') {
        return {
          success: false,
          error: 'Authorization session expired. Please return to chat and try again.',
        };
      }
      if (error.name === 'ConflictException') {
        // Session already completed - treat as success
        return { success: true };
      }
      return { success: false, error: error.message };
    }
    return { success: false, error: 'Unknown error occurred' };
  }
}
```

---

## UI States

### Loading State

```tsx
<div className="flex flex-col items-center justify-center min-h-screen">
  <Spinner size="lg" />
  <p className="mt-4 text-gray-600">Completing authentication...</p>
</div>
```

### Success State

```tsx
<div className="flex flex-col items-center justify-center min-h-screen">
  <CheckCircle className="w-16 h-16 text-green-500" />
  <h1 className="mt-4 text-2xl font-semibold">Authentication Successful</h1>
  <p className="mt-2 text-gray-600">Redirecting you back to the chat...</p>
</div>
```

### Error State

```tsx
<div className="flex flex-col items-center justify-center min-h-screen">
  <XCircle className="w-16 h-16 text-red-500" />
  <h1 className="mt-4 text-2xl font-semibold">Authentication Failed</h1>
  <p className="mt-2 text-gray-600">{error}</p>
  <Button onClick={() => router.push('/')} className="mt-4">
    Return to Chat
  </Button>
</div>
```

---

## Security Considerations

### CSRF Protection

The `custom_state` parameter can be used for CSRF validation:

```typescript
// Before completing auth, validate custom_state
const storedState = sessionStorage.getItem('oauth_state');
const urlState = searchParams.get('custom_state');

if (storedState && urlState && storedState !== urlState) {
  throw new Error('Invalid state parameter - possible CSRF attack');
}
```

### Session Expiration

Authorization sessions expire after 10 minutes. The callback page should handle this gracefully:

```typescript
if (error.name === 'ResourceNotFoundException') {
  // Show user-friendly message about session expiration
  setError('Your authentication session has expired. Please return to the chat and request a new sign-in link.');
}
```

### Token Handling

- Access tokens are obtained from Amplify's secure session storage
- Tokens are passed directly to AgentCore, never stored by our code
- AgentCore's Token Vault handles long-term token storage

---

## Testing

### Unit Test Cases

| Test Case | Input | Expected Output |
|-----------|-------|-----------------|
| Valid session binding | Valid sessionId, valid token | Success, redirect to `/` |
| Missing session_id | No query param | Error: "Missing session_id parameter" |
| Expired session | Valid sessionId, expired | Error: "session expired" message |
| Invalid token | Valid sessionId, invalid token | Error: AccessDeniedException |
| Already completed | Previously completed sessionId | Success (idempotent) |

### E2E Test Flow

```typescript
// e2e/oauth-flow.spec.ts
test('complete OAuth2 callback flow', async ({ page }) => {
  // Setup: Get a valid session_id from test agent
  const sessionId = await getTestSessionId();

  // Navigate to callback with session_id
  await page.goto(`/auth/callback?session_id=${sessionId}`);

  // Verify loading state
  await expect(page.getByText('Completing authentication')).toBeVisible();

  // Wait for redirect (success case requires valid Cognito session)
  await page.waitForURL('/');
});
```

---

## Monitoring

### CloudWatch Metrics

| Metric | Description | Alarm Threshold |
|--------|-------------|-----------------|
| `CallbackAttempts` | Total callback page loads | N/A (informational) |
| `CallbackSuccess` | Successful session bindings | < 95% = warning |
| `CallbackErrors` | Failed session bindings | > 5% = warning |
| `SessionExpired` | Expired session errors | > 10% = investigate |

### Structured Logging

```typescript
// Log format for callback events
const logEvent = {
  event: 'oauth_callback',
  sessionId: sessionId?.substring(0, 8) + '...', // Truncate for privacy
  status: 'success' | 'error',
  error?: errorCode,
  duration: endTime - startTime,
  timestamp: new Date().toISOString(),
};
```
