# Contract: OTP Record (DynamoDB Item)

**Feature**: 019-e2e-email-otp | **Version**: 1.0.0

## Overview

This contract defines the DynamoDB item structure for intercepted OTP codes stored in the `verification_codes` table.

## Table Configuration

| Property | Value |
|----------|-------|
| Table Name | `booking-{env}-verification-codes` |
| Partition Key | `email` (String) |
| Sort Key | None |
| Billing Mode | PAY_PER_REQUEST |
| TTL Attribute | `expires_at` |
| TTL Duration | 5 minutes |

## Item Schema

```typescript
interface OtpRecord {
  // Primary Key
  email: string;          // Partition key - email address

  // OTP Data
  code: string;           // 6-digit OTP code
  trigger_source: string; // Cognito trigger type

  // Timestamps
  created_at: string;     // ISO 8601 timestamp
  expires_at: number;     // Unix timestamp (TTL)
}
```

## Field Specifications

### email (String, PK)

- **Format**: Valid email address
- **Pattern for tests**: `test+{uuid}@summerhouse.com` or `*@test.summerhouse.com`
- **Example**: `test+e2e-550e8400@summerhouse.com`
- **Constraints**: Max 256 characters

### code (String)

- **Format**: 6-digit numeric string
- **Example**: `"123456"`
- **Constraints**: Exactly 6 digits, stored as string to preserve leading zeros

### trigger_source (String)

- **Values**: One of:
  - `CustomMessage_SignUp`
  - `CustomMessage_Authentication`
  - `CustomMessage_ResendCode`
- **Example**: `"CustomMessage_Authentication"`

### created_at (String)

- **Format**: ISO 8601 UTC timestamp
- **Example**: `"2026-01-06T10:30:00.000Z"`
- **Precision**: Milliseconds

### expires_at (Number)

- **Format**: Unix timestamp in seconds
- **Calculation**: `created_at + 300` (5 minutes)
- **Example**: `1736162400`
- **Purpose**: DynamoDB TTL auto-deletion

## Example Item

```json
{
  "email": {
    "S": "test+e2e-abc123@summerhouse.com"
  },
  "code": {
    "S": "123456"
  },
  "trigger_source": {
    "S": "CustomMessage_Authentication"
  },
  "created_at": {
    "S": "2026-01-06T10:30:00.000Z"
  },
  "expires_at": {
    "N": "1736162400"
  }
}
```

## Access Patterns

### Write (Lambda → DynamoDB)

```python
# OTP Interceptor Lambda writes new OTP record
import time
from datetime import datetime, timezone

dynamodb.put_item(
    TableName=os.environ['VERIFICATION_CODES_TABLE'],
    Item={
        'email': {'S': email},
        'code': {'S': otp_code},
        'trigger_source': {'S': trigger_source},
        'created_at': {'S': datetime.now(timezone.utc).isoformat()},
        'expires_at': {'N': str(int(time.time()) + 300)}
    }
)
```

### Read (E2E Test → DynamoDB)

```typescript
// Playwright test retrieves OTP code
const result = await dynamodb.send(new GetItemCommand({
  TableName: process.env.VERIFICATION_CODES_TABLE,
  Key: {
    email: { S: testEmail }
  }
}));

const otpCode = result.Item?.code?.S;
const createdAt = result.Item?.created_at?.S;
```

## Overwrite Behavior

When a new OTP is generated for the same email (e.g., resend):
- The `put_item` operation overwrites the existing item
- Only the latest OTP code is stored
- Previous codes are implicitly invalidated

## IAM Permissions Required

### Lambda (Write)
```json
{
  "Effect": "Allow",
  "Action": ["dynamodb:PutItem"],
  "Resource": "arn:aws:dynamodb:*:*:table/booking-dev-verification-codes"
}
```

### E2E Tests (Read)
```json
{
  "Effect": "Allow",
  "Action": ["dynamodb:GetItem"],
  "Resource": "arn:aws:dynamodb:*:*:table/booking-dev-verification-codes"
}
```
