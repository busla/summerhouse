# Tool Response Contracts: JWT Session Authentication

**Feature**: 004-jwt-session-auth
**Date**: 2025-12-30
**Version**: 1.0.0

## Overview

This document defines the response schemas for authentication-related Strands tools. These contracts ensure consistent data exchange between the backend agent and frontend.

---

## initiate_cognito_login

Initiates EMAIL_OTP passwordless authentication flow.

### Request (Tool Arguments)

```json
{
  "email": "string (required) - User's email address"
}
```

### Success Response

```json
{
  "success": true,
  "session_token": "string - Cognito session token for verify_cognito_otp",
  "challenge": "EMAIL_OTP",
  "email": "string - The email address",
  "otp_sent_at": "string - ISO 8601 timestamp when OTP was sent"
}
```

**Example**:
```json
{
  "success": true,
  "session_token": "AYABeGx5c3Nz...truncated",
  "challenge": "EMAIL_OTP",
  "email": "guest@example.com",
  "otp_sent_at": "2025-12-30T10:15:30.000Z"
}
```

### Error Responses

**Invalid Email Format**:
```json
{
  "success": false,
  "error_code": "INVALID_EMAIL",
  "message": "Invalid email format"
}
```

**Email Delivery Failed**:
```json
{
  "success": false,
  "error_code": "ERR_EMAIL_DELIVERY_FAILED",
  "message": "Cognito error: LimitExceededException - Rate exceeded"
}
```

**Service Error**:
```json
{
  "success": false,
  "error_code": "AUTH_SERVICE_ERROR",
  "message": "Auth service error: NoCredentialsError: Unable to locate credentials"
}
```

---

## verify_cognito_otp

Verifies OTP code and returns authentication tokens.

### Request (Tool Arguments)

```json
{
  "email": "string (required) - User's email address",
  "otp_code": "string (required) - 6-digit OTP code",
  "session_token": "string (required) - Session token from initiate_cognito_login",
  "otp_sent_at": "string (required) - ISO timestamp when OTP was sent",
  "attempts": "integer (optional, default 0) - Number of previous failed attempts"
}
```

### Success Response (TokenDeliveryEvent)

**Schema**:
```json
{
  "event_type": "auth_tokens",
  "success": true,
  "id_token": "string - Cognito ID Token (JWT)",
  "access_token": "string - Cognito Access Token (JWT)",
  "refresh_token": "string - Cognito Refresh Token",
  "expires_in": "integer - Token validity in seconds",
  "guest_id": "string - Guest profile ID (GST-YYYY-XXXXXX)",
  "email": "string - User's email address",
  "cognito_sub": "string - Cognito user identifier (UUID)"
}
```

**Example**:
```json
{
  "event_type": "auth_tokens",
  "success": true,
  "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...truncated",
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...truncated",
  "refresh_token": "eyJjdHkiOiJKV1QiLCJlbmMiOiJBMjU2R0NNIiwiYWxnIjoiUlNBLU9BRVAifQ...truncated",
  "expires_in": 3600,
  "guest_id": "GST-2025-ABC123",
  "email": "guest@example.com",
  "cognito_sub": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### Error Responses

**Invalid OTP**:
```json
{
  "success": false,
  "error_code": "INVALID_OTP",
  "message": "The verification code is incorrect",
  "attempts": 1
}
```

**OTP Expired**:
```json
{
  "success": false,
  "error_code": "OTP_EXPIRED",
  "message": "The verification code has expired. Please request a new code."
}
```

**Max Attempts Exceeded**:
```json
{
  "success": false,
  "error_code": "MAX_ATTEMPTS_EXCEEDED",
  "message": "Maximum verification attempts exceeded. Please request a new code.",
  "attempts": 3
}
```

**Guest Creation Failed**:
```json
{
  "success": false,
  "error_code": "GUEST_CREATION_FAILED",
  "message": "Failed to create guest profile: ConditionalCheckFailedException"
}
```

---

## Token Claims

### ID Token Claims

The `id_token` is a JWT containing user identity claims:

```json
{
  "sub": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "email": "guest@example.com",
  "email_verified": true,
  "iss": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_XXXXXXX",
  "aud": "1234567890abcdefghijklmnop",
  "token_use": "id",
  "auth_time": 1735560930,
  "exp": 1735564530,
  "iat": 1735560930
}
```

### Access Token Claims

The `access_token` is a JWT for API authorization:

```json
{
  "sub": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "client_id": "1234567890abcdefghijklmnop",
  "scope": "openid email",
  "token_use": "access",
  "exp": 1735564530,
  "iat": 1735560930,
  "jti": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

---

## SSE Stream Format

Tool results are delivered via AgentCore SSE stream:

```
data: {"type":"tool-result","toolCallId":"call_abc123","result":{"event_type":"auth_tokens","success":true,"id_token":"eyJ...","access_token":"eyJ...","refresh_token":"eyJ...","expires_in":3600,"guest_id":"GST-2025-ABC123","email":"guest@example.com","cognito_sub":"a1b2c3d4-..."}}\n\n
```

### Parsing Example (TypeScript)

```typescript
function processSSEEvent(event: UIMessageChunk): void {
  if (event.type === 'tool-result') {
    const result = event.result
    if (isTokenDeliveryEvent(result)) {
      storeSession({
        isAuthenticated: true,
        guestId: result.guest_id,
        email: result.email,
        idToken: result.id_token,
        accessToken: result.access_token,
        refreshToken: result.refresh_token,
        expiresAt: Date.now() + result.expires_in * 1000,
        cognitoSub: result.cognito_sub,
      })
    }
  }
}
```

---

## Error Code Reference

| Code | HTTP Equiv | Description | Recovery |
|------|------------|-------------|----------|
| `INVALID_EMAIL` | 400 | Email format validation failed | Ask user to correct email |
| `INVALID_OTP` | 401 | OTP code doesn't match | Ask user to retry (up to 3 attempts) |
| `OTP_EXPIRED` | 401 | OTP code past 5-minute validity | Trigger new OTP request |
| `MAX_ATTEMPTS_EXCEEDED` | 429 | 3 failed OTP attempts | Trigger new OTP request |
| `ERR_EMAIL_DELIVERY_FAILED` | 503 | Cognito couldn't send email | Ask user to retry later |
| `AUTH_SERVICE_ERROR` | 500 | Backend auth service failure | Ask user to retry later |
| `GUEST_CREATION_FAILED` | 500 | DynamoDB write failed | Ask user to retry later |

---

## Versioning

This contract follows semantic versioning:

- **1.0.0** (2025-12-30): Initial contract with `TokenDeliveryEvent`

Future versions will maintain backward compatibility by:
1. Only adding new optional fields
2. Never removing existing fields
3. Never changing field types
4. Deprecating fields before removal (minimum 2 versions)
