# Quickstart: AgentCore Identity OAuth2 with Amplify EMAIL_OTP

**Feature Branch**: `005-agentcore-amplify-oauth2`
**Date**: 2025-12-30

## Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform >= 1.5.0
- Node.js >= 20.x (for frontend)
- Python >= 3.13 (for backend)
- Yarn Berry (for frontend package management)
- uv (for Python dependency management)

## Local Development Setup

### 1. Clone and Checkout Feature Branch

```bash
cd ~/code/personal/summerhouse
git checkout -b 005-agentcore-amplify-oauth2
```

### 2. Install Dependencies

```bash
# Install all dependencies via Taskfile
task install

# Or individually:
task frontend:install
task backend:install
```

### 3. Deploy Infrastructure (Dev Environment)

The OAuth2 flow requires AgentCore Identity resources to be deployed:

```bash
# Initialize Terraform
task tf:init:dev

# Review changes (should show new AgentCore Identity resources)
task tf:plan:dev

# Apply infrastructure
task tf:apply:dev
```

**Expected new resources**:
- `aws_bedrockagentcore_oauth2_credential_provider.cognito`
- `aws_bedrockagentcore_workload_identity.agent`
- Updates to Cognito User Pool Client (callback URLs)

### 4. Get Environment Variables

After `task tf:apply:dev`, get the required environment variables:

```bash
task tf:output:dev
```

Update your environment files:

**Backend `.env`**:
```env
# Existing variables remain unchanged
AWS_REGION=eu-west-1
DYNAMODB_RESERVATIONS_TABLE=booking-dev-reservations
DYNAMODB_GUESTS_TABLE=booking-dev-guests
COGNITO_USER_POOL_ID=eu-west-1_xxxxx
COGNITO_CLIENT_ID=xxxxx
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514
LOG_LEVEL=INFO

# NEW: AgentCore Identity (for @requires_access_token)
AGENTCORE_WORKLOAD_IDENTITY_ARN=arn:aws:bedrock-agentcore:eu-west-1:123456789012:workload-identity/xxxxx
AGENTCORE_CREDENTIAL_PROVIDER_NAME=booking-dev-cognito
```

**Frontend `.env.local`**:
```env
# Existing variables
NEXT_PUBLIC_AWS_REGION=eu-west-1
NEXT_PUBLIC_COGNITO_IDENTITY_POOL_ID=eu-west-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
NEXT_PUBLIC_AGENTCORE_RUNTIME_ARN=arn:aws:bedrock-agentcore:eu-west-1:123456789012:runtime/xxxxx

# NEW: Amplify Auth configuration
NEXT_PUBLIC_COGNITO_USER_POOL_ID=eu-west-1_xxxxx
NEXT_PUBLIC_COGNITO_USER_POOL_CLIENT_ID=xxxxx
```

### 5. Run Development Servers

```bash
# Run both frontend and backend
task dev

# Or individually:
task frontend:dev  # http://localhost:3000
task backend:dev   # http://localhost:3001
```

---

## Testing the OAuth2 Flow

### Manual Test Sequence

1. **Open the chat interface**: http://localhost:3000

2. **Test anonymous inquiry** (should work without auth):
   ```
   You: "What dates are available in March?"
   Agent: [Lists availability without auth prompt]
   ```

3. **Trigger OAuth2 flow** (booking intent):
   ```
   You: "I want to book March 15-20"
   Agent: "To complete your booking, please sign in: [Click here to sign in]"
   ```

4. **Click the authorization URL** - should redirect to `/login`

5. **Complete EMAIL_OTP authentication**:
   - Enter email address
   - Receive OTP (check email)
   - Enter 8-digit code

6. **Observe callback redirect**:
   - Browser redirects to `/auth/callback?session_id=xxx`
   - `CompleteResourceTokenAuth` is called
   - Redirects back to chat

7. **Continue conversation** (now authenticated):
   ```
   You: [Continue booking conversation]
   Agent: [Proceeds with reservation using authenticated context]
   ```

### Debug Checklist

| Step | What to Check | Expected |
|------|---------------|----------|
| 1 | Network tab - AgentCore invoke | 200 OK, no auth errors |
| 2 | Console - anonymous inquiry | No auth URL returned |
| 3 | Console - booking intent | Auth URL in tool response |
| 4 | Login page loads | Amplify Authenticator visible |
| 5 | Email input only | No password field shown |
| 6 | OTP received | 8-digit code within 60s |
| 7 | Callback URL | `session_id` param present |
| 8 | CompleteResourceTokenAuth | Network call succeeds |
| 9 | Redirect to chat | Session preserved |
| 10 | Authenticated request | Tool executes without auth prompt |

---

## Code Locations

### Backend Changes

| File | Change |
|------|--------|
| `backend/src/tools/auth.py` | **DELETE** - Remove `initiate_cognito_login`, `verify_cognito_otp` |
| `backend/src/tools/reservation.py` | **MODIFY** - Add `@requires_access_token` decorator |
| `backend/src/services/auth_service.py` | **DELETE** - Remove `AdminInitiateAuth` code |
| `backend/src/agent/prompts/system.py` | **MODIFY** - Update for OAuth2 flow |

### Frontend Changes

| File | Change |
|------|--------|
| `frontend/src/app/login/page.tsx` | **CREATE** - Amplify EMAIL_OTP auth page |
| `frontend/src/app/auth/callback/page.tsx` | **CREATE** - OAuth2 callback handler |
| `frontend/src/lib/amplify-config.ts` | **CREATE** - Amplify Auth configuration |
| `frontend/src/lib/agentcore-auth.ts` | **CREATE** - CompleteResourceTokenAuth wrapper |
| `frontend/src/components/auth/AuthCallback.tsx` | **CREATE** - Callback client component |

### Infrastructure Changes

| File | Change |
|------|--------|
| `infrastructure/main.tf` | **MODIFY** - Add identity module call |
| `infrastructure/cognito.tf` | **MODIFY** - Update User Pool Client callbacks |

---

## Troubleshooting

### "Authorization URL expired"

**Symptom**: Clicking auth URL shows error page
**Cause**: More than 10 minutes elapsed since URL was generated
**Fix**: Return to chat, trigger booking intent again to get fresh URL

### "CompleteResourceTokenAuth failed"

**Symptom**: Callback page shows error
**Cause**: Session binding failed

**Debug steps**:
1. Check browser console for error details
2. Verify `session_id` param is present in URL
3. Verify Amplify session has valid `accessToken`
4. Check CloudWatch logs for AgentCore errors

### "No password field but I need to create account"

**Symptom**: New user can't sign up
**Cause**: EMAIL_OTP flow handles signup automatically
**Fix**: Enter email → receive OTP → account created on first verification

### "Agent still asking for auth after login"

**Symptom**: Auth flow completed but agent prompts again
**Cause**: Session binding didn't complete or token not in vault

**Debug steps**:
1. Check if `CompleteResourceTokenAuth` returned success
2. Verify redirect happened after callback
3. Check if same browser session (cookies)
4. Verify AgentCore Runtime can access TokenVault (IAM permissions)

---

## Running Tests

### Unit Tests

```bash
# Backend
task backend:test

# Frontend
task frontend:test
```

### Integration Tests

```bash
# Backend integration (requires AWS credentials)
cd backend && pytest tests/integration/ -v
```

### E2E Tests

```bash
# Requires dev environment deployed
cd frontend && yarn test:e2e

# Run specific OAuth2 flow test
cd frontend && yarn playwright test oauth-flow.spec.ts
```

---

## Environment-Specific Notes

### Local Development

- AgentCore Runtime must be deployed (can't run locally)
- OAuth2 flow requires real Cognito (can't mock)
- Use `task tf:apply:dev` to deploy minimal infrastructure

### Dev Environment

- Full infrastructure deployed
- OAuth2 callback URL: `https://dev.example.com/auth/callback`
- Cognito Hosted UI domain: `booking-dev.auth.eu-west-1.amazoncognito.com`

### Production

- Separate Terraform workspace
- OAuth2 callback URL: `https://www.example.com/auth/callback`
- Stricter IAM permissions
- CloudWatch alarms for auth failures

---

## Architecture Reference

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                           │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   /                    /login                 /auth/callback         │
│   ┌─────────┐         ┌─────────┐            ┌─────────┐            │
│   │  Chat   │         │ Amplify │            │ Session │            │
│   │Interface│──click──│  Auth   │──success──►│ Binding │            │
│   │         │◄────────│(EMAIL_  │            │ Handler │            │
│   │         │redirect │  OTP)   │            │         │            │
│   └────┬────┘         └─────────┘            └────┬────┘            │
│        │                                          │                  │
└────────│──────────────────────────────────────────│──────────────────┘
         │                                          │
         │ AgentCore                                │ CompleteResource
         │ InvokeAgent                              │ TokenAuth
         ▼                                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      AgentCore Runtime                                │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐           │
│   │   Agent     │     │  Identity   │     │   Token     │           │
│   │  (Strands)  │────►│  Service    │────►│   Vault     │           │
│   │             │     │             │     │             │           │
│   └─────────────┘     └─────────────┘     └─────────────┘           │
│         │                   │                                        │
│         │ @requires_        │ GetResourceOauth2Token                 │
│         │ access_token      │                                        │
│         ▼                   ▼                                        │
│   ┌─────────────┐     ┌─────────────┐                               │
│   │ Reservation │     │Authorization│                               │
│   │    Tool     │     │   Session   │                               │
│   │             │     │(10 min TTL) │                               │
│   └─────────────┘     └─────────────┘                               │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              │ OAuth2
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      Cognito User Pool                                │
├──────────────────────────────────────────────────────────────────────┤
│   EMAIL_OTP authentication │ Token exchange │ User attributes        │
└──────────────────────────────────────────────────────────────────────┘
```
