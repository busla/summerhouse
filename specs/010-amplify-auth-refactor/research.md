# Research: Amplify Authentication Refactor

**Feature**: 010-amplify-auth-refactor | **Date**: 2026-01-02 | **Phase**: 0

## Research Questions & Findings

### RQ-1: Amplify v6 EMAIL_OTP API

**Question**: What is the exact API for `signUp`, `signIn`, `confirmSignIn` with EMAIL_OTP in Amplify v6?

**Answer**: Amplify v6 provides a clean API for passwordless EMAIL_OTP authentication using the `USER_AUTH` flow.

#### Sign In Flow (Existing Users)

```typescript
import { signIn, confirmSignIn } from 'aws-amplify/auth'

// Step 1: Initiate sign-in with EMAIL_OTP
const { nextStep } = await signIn({
  username: email,
  options: {
    authFlowType: 'USER_AUTH',
    preferredChallenge: 'EMAIL_OTP',
  },
})

// Response: nextStep.signInStep === 'CONFIRM_SIGN_IN_WITH_EMAIL_CODE'
// Cognito sends OTP to user's email automatically

// Step 2: Confirm with OTP code
const result = await confirmSignIn({
  challengeResponse: '123456', // User-entered code
})

// Success: result.isSignedIn === true
```

#### Sign Up Flow (New Users)

```typescript
import { signUp, confirmSignUp, autoSignIn } from 'aws-amplify/auth'

// Step 1: Register new user
const { nextStep } = await signUp({
  username: email,
  password: generateRandomPassword(), // Required but not used
  options: {
    userAttributes: { email, name },
    autoSignIn: { authFlowType: 'USER_AUTH' }, // Auto sign-in after confirm
  },
})

// Response: nextStep.signUpStep === 'CONFIRM_SIGN_UP'

// Step 2: Confirm registration
await confirmSignUp({
  username: email,
  confirmationCode: '123456',
})

// Step 3: Auto sign-in triggers automatically
// Listen for autoSignIn output or call signIn manually
```

**Key Findings**:
- `USER_AUTH` is the auth flow type for native EMAIL_OTP (requires Cognito ESSENTIALS tier)
- `preferredChallenge: 'EMAIL_OTP'` tells Cognito to use email-based OTP
- Password is technically required for sign-up but not used in EMAIL_OTP flow
- Auto sign-in can be configured to use USER_AUTH flow

**Source**: Context7 AWS Amplify documentation (`/aws-amplify/docs`)

---

### RQ-2: JWT Claims Access in FastAPI

**Question**: How does FastAPI extract JWT claims when API Gateway has already validated the token?

**Answer**: API Gateway REST API with Cognito User Pool authorizer passes claims in the request context.

#### API Gateway Behavior

For **REST API** with Cognito authorizer:
```python
# Lambda event structure
event = {
    "requestContext": {
        "authorizer": {
            "claims": {
                "sub": "12345678-1234-1234-1234-123456789012",
                "email": "user@example.com",
                "email_verified": "true",
                "cognito:username": "user@example.com",
                "iss": "https://cognito-idp.{region}.amazonaws.com/{userPoolId}",
                "aud": "{clientId}",
                ...
            }
        }
    }
}
```

#### Current Backend Implementation

The backend already extracts claims via the `x-user-sub` header (set by API Gateway integration):

```python
# backend/api/src/api/routes/guests.py
def _get_user_guest_id(request: Request) -> str | None:
    """Extract guest_id from request based on JWT sub claim."""
    user_sub = request.headers.get("x-user-sub")
    if not user_sub:
        return None
    db = get_dynamodb_service()
    guest = db.get_guest_by_cognito_sub(user_sub)
    return guest.get("guest_id") if guest else None
```

**Key Findings**:
- Backend trusts API Gateway - no need for PyJWT validation
- Claims passed via headers (configured in API Gateway integration)
- `sub` claim is the unique user identifier (UUID format)
- Existing `_get_user_guest_id()` function already queries by `cognito_sub`

**Source**: AWS Documentation (HTTP API JWT authorizer), existing codebase

---

### RQ-3: Cognito Sub Format

**Question**: What is the format of the `sub` claim from Cognito?

**Answer**: Standard UUID v4 format.

```
Format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Example: 12345678-1234-1234-1234-123456789012
```

**Key Findings**:
- 36 characters including hyphens
- Universally unique within the User Pool
- Immutable - never changes for a user
- Already used in `cognito_sub` field in Guest model

**Verification**: From `backend/shared/src/shared/models/guest.py`:
```python
cognito_sub: str | None = Field(
    default=None,
    description="Cognito User Pool subject identifier for OAuth2 binding",
)
```

---

### RQ-4: Session Refresh

**Question**: How does Amplify handle token refresh automatically?

**Answer**: Amplify handles token refresh transparently via `fetchAuthSession()`.

```typescript
import { fetchAuthSession } from 'aws-amplify/auth'

// Amplify automatically:
// 1. Checks if access token is expired or near expiration
// 2. Uses refresh token to get new tokens if needed
// 3. Returns fresh tokens

const session = await fetchAuthSession()
const idToken = session.tokens?.idToken?.toString()
```

**Key Findings**:
- `fetchAuthSession()` automatically refreshes tokens when needed
- Refresh token validity: 30 days (configured in Cognito)
- Access/ID token validity: 1 hour (configured in Cognito)
- Existing `ensureValidIdToken()` in `frontend/src/lib/auth.ts` already uses this

**Source**: Existing codebase (`frontend/src/lib/auth.ts`), Cognito configuration

---

### RQ-5: Error Handling

**Question**: What errors does Amplify throw for invalid OTP, expired OTP, rate limiting?

**Answer**: Amplify throws specific error types that can be caught and handled.

#### Error Types

| Error | Cause | Recovery |
|-------|-------|----------|
| `CodeMismatchException` | Invalid OTP entered | Retry with correct code |
| `ExpiredCodeException` | OTP expired (>5 min) | Request new code |
| `LimitExceededException` | Rate limit (3+ attempts) | Wait and retry |
| `UserNotFoundException` | Email not registered | Sign up instead |
| `NotAuthorizedException` | General auth failure | Varies |
| `UserNotConfirmedException` | Signup incomplete | Confirm signup first |

#### Error Handling Pattern

```typescript
import { signIn, confirmSignIn } from 'aws-amplify/auth'

try {
  await confirmSignIn({ challengeResponse: code })
} catch (error) {
  if (error instanceof Error) {
    switch (error.name) {
      case 'CodeMismatchException':
        // Show: "Invalid code. Please try again."
        break
      case 'ExpiredCodeException':
        // Show: "Code expired. Requesting new code..."
        // Call signIn again to get new OTP
        break
      case 'LimitExceededException':
        // Show: "Too many attempts. Please wait before trying again."
        break
      default:
        // Generic error handling
    }
  }
}
```

**Key Findings**:
- Error names match Cognito exception types
- Max 3 OTP attempts before requiring new code (Cognito default)
- OTP expires after 5 minutes (Cognito default)
- Rate limiting kicks in after excessive attempts

**Source**: Context7 AWS Amplify documentation, Cognito behavior

---

## Existing Code Analysis

### Frontend (`frontend/src/lib/auth.ts`)

✅ **Already Implemented**:
- `useAuth()` hook with `isAuthenticated`, `email`, `userId`
- `ensureValidIdToken()` for getting ID token
- `signOut` functionality
- Uses `fetchAuthSession()` and `getCurrentUser()`

❌ **Missing**:
- `signIn()` with EMAIL_OTP flow
- `signUp()` for new users
- `confirmSignIn()` for OTP verification
- Error handling for auth failures

### Backend (`backend/api/src/api/routes/guests.py`)

✅ **Already Implemented**:
- `_get_user_guest_id()` - extracts guest_id from cognito_sub
- `require_auth([AuthScope.OPENID])` decorator
- `/guests/verify` and `/guests/verify/confirm` endpoints
- Owner-only access patterns

✅ **DynamoDB Service** (`backend/shared/src/shared/services/dynamodb.py`):
- `get_guest_by_cognito_sub()` - queries GSI
- `update_guest_cognito_sub()` - binds sub to existing guest
- `cognito-sub-index` GSI already configured

### Infrastructure (`infrastructure/modules/cognito-passwordless/main.tf`)

✅ **Already Configured**:
- User Pool with ESSENTIALS tier (required for native EMAIL_OTP)
- `allowed_first_auth_factors = ["PASSWORD", "EMAIL_OTP"]`
- Public client with `ALLOW_USER_AUTH` flow (for Amplify)
- Identity Pool for IAM-based auth
- Token validity: 1 hour (access/ID), 30 days (refresh)

---

## Architecture Validation

### Simplified Auth Flow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Frontend    │    │   API Gateway   │    │     Backend     │
│    (Amplify)    │    │   (Cognito      │    │    (FastAPI)    │
│                 │    │    Authorizer)  │    │                 │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
    1. signIn(EMAIL_OTP)        │                      │
         │                      │                      │
    2. User receives OTP        │                      │
         │                      │                      │
    3. confirmSignIn(code)      │                      │
         │                      │                      │
    4. Session created          │                      │
         │                      │                      │
    5. API request with token ──┼──────────────────────┤
         │                      │                      │
         │              6. Validate JWT               │
         │                      │                      │
         │              7. Forward with claims ───────>│
         │                      │                      │
         │                      │          8. Query by sub
         │                      │                      │
         │<─────────────────────┼───────── 9. Response
```

### What's Being Removed

| Component | Previous State | New State |
|-----------|---------------|-----------|
| Agent auth | OAuth2 + token vault | Out of scope (agent unchanged) |
| JWT validation | PyJWT in backend | Trust API Gateway |
| Session storage | DynamoDB + localStorage + vault | Amplify-managed only |
| Token delivery | Tool response events | N/A (frontend initiates) |
| Auth implementations | 3 overlapping | 1 unified |

---

## Unknowns Resolved

All research questions answered. No blockers identified.

## Next Steps

1. **Phase 1**: Create `data-model.md` documenting Customer entity
2. **Phase 1**: Create `contracts/` for customer API endpoints
3. **Phase 1**: Create `quickstart.md` with implementation guide
4. **Phase 2**: Run `/speckit.tasks` to generate task breakdown
