# Data Model: E2E Test Support for Cognito Email OTP

**Feature**: 019-e2e-email-otp | **Date**: 2026-01-06

## Overview

This feature adds OTP code interception for E2E testing. It reuses the existing `verification_codes` DynamoDB table with a minor extension to store the OTP code.

## Entity Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Cognito User Pool                        │
│                                                             │
│  EMAIL_OTP Authentication                                   │
│    ↓                                                        │
│  Custom Message Lambda Trigger ──────────────────────┐      │
│    ↓                                                 │      │
│  Email sent to user (unchanged)                      │      │
└─────────────────────────────────────────────────────────────┘
                                                       │
                                                       ↓
┌─────────────────────────────────────────────────────────────┐
│                   OTP Interceptor Lambda                    │
│                                                             │
│  Input: { triggerSource, request: { codeParameter, ... }}   │
│  Logic:                                                     │
│    1. Check if test environment                             │
│    2. Check if test email pattern                           │
│    3. Store code in DynamoDB                                │
│  Output: Pass-through (email still sent)                    │
└─────────────────────────────────────────────────────────────┘
                                                       │
                                                       ↓
┌─────────────────────────────────────────────────────────────┐
│                  verification_codes Table                   │
│                                                             │
│  PK: email (String)                                         │
│  Attributes:                                                │
│    - code (String) - NEW: The OTP code                      │
│    - created_at (String) - ISO timestamp                    │
│    - expires_at (Number) - TTL Unix timestamp               │
│    - trigger_source (String) - Cognito trigger type         │
└─────────────────────────────────────────────────────────────┘
                                                       │
                                                       ↓
┌─────────────────────────────────────────────────────────────┐
│                     E2E Test (Playwright)                   │
│                                                             │
│  1. Enter test email in auth flow                           │
│  2. Wait for OTP (poll DynamoDB via otp-helper)             │
│  3. Enter OTP code in UI                                    │
│  4. Verify authentication succeeds                          │
└─────────────────────────────────────────────────────────────┘
```

## Entities

### OTP Record (DynamoDB Item)

Stored in the existing `verification_codes` table.

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `email` | String (PK) | Email address (partition key) | `test+abc123@summerhouse.com` |
| `code` | String | 6-digit OTP code | `"123456"` |
| `trigger_source` | String | Cognito trigger type | `"CustomMessage_Authentication"` |
| `created_at` | String | ISO 8601 timestamp | `"2026-01-06T10:30:00Z"` |
| `expires_at` | Number | Unix timestamp for TTL | `1736162400` (5 minutes from creation) |

**TTL Policy**: Items auto-expire 5 minutes after creation via DynamoDB TTL on `expires_at`.

### Lambda Event (Input)

Received by the OTP Interceptor Lambda from Cognito.

```python
@dataclass
class CognitoCustomMessageEvent:
    version: str
    region: str
    userPoolId: str
    userName: str
    callerContext: dict
    triggerSource: str  # e.g., "CustomMessage_Authentication"
    request: CustomMessageRequest
    response: CustomMessageResponse

@dataclass
class CustomMessageRequest:
    userAttributes: dict[str, str]  # includes "email"
    codeParameter: str  # The actual OTP code
    usernameParameter: str | None  # For admin-created users

@dataclass
class CustomMessageResponse:
    smsMessage: str | None
    emailMessage: str | None
    emailSubject: str | None
```

### Test Email Pattern

E2E tests use unique email addresses to avoid collisions:

```
test+{uuid}@summerhouse.com
```

Examples:
- `test+e2e-abc123@summerhouse.com`
- `test+booking-flow-xyz789@summerhouse.com`

The Lambda only intercepts emails matching:
- Pattern: `+test` anywhere in local part, OR
- Domain: `@test.summerhouse.com`

## State Transitions

### OTP Lifecycle

```
┌──────────────┐     Lambda stores     ┌──────────────┐
│   Created    │ ───────────────────→  │   Active     │
│  (in Lambda) │                       │  (in DynamoDB)│
└──────────────┘                       └──────────────┘
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    │                         │                         │
                    ↓                         ↓                         ↓
           ┌──────────────┐          ┌──────────────┐          ┌──────────────┐
           │   Retrieved  │          │    Used      │          │   Expired    │
           │  (by test)   │          │ (by Cognito) │          │  (TTL=5min)  │
           └──────────────┘          └──────────────┘          └──────────────┘
```

## Schema Changes

### No DynamoDB Schema Changes Required

The existing `verification_codes` table already has:
- ✅ `email` as partition key
- ✅ `expires_at` TTL attribute enabled

New attributes (`code`, `trigger_source`, `created_at`) are added dynamically - DynamoDB is schema-less for non-key attributes.

### Terraform Changes

No changes to `infrastructure/modules/dynamodb/main.tf`. The table already exists with the correct configuration.

## Access Patterns

### Write (Lambda → DynamoDB)

```python
# OTP Interceptor Lambda
dynamodb.put_item(
    TableName=os.environ['VERIFICATION_CODES_TABLE'],
    Item={
        'email': {'S': email},
        'code': {'S': otp_code},
        'trigger_source': {'S': trigger_source},
        'created_at': {'S': datetime.utcnow().isoformat()},
        'expires_at': {'N': str(int(time.time()) + 300)}  # 5 min TTL
    }
)
```

### Read (E2E Test → DynamoDB)

```typescript
// Playwright test helper
const result = await dynamodb.send(new GetItemCommand({
  TableName: process.env.VERIFICATION_CODES_TABLE,
  Key: { email: { S: testEmail } }
}));
return result.Item?.code?.S;
```

## Security Considerations

1. **Test-only Activation**: Lambda checks `ENVIRONMENT=dev` before storing
2. **Email Pattern Filter**: Only intercepts test email patterns
3. **No Production Deployment**: Lambda module only instantiated in dev environment
4. **TTL Cleanup**: Codes auto-expire in 5 minutes
5. **IAM Scoped**: E2E tests only have `dynamodb:GetItem` on verification_codes table
