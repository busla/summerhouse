# API Contracts: Booking Authentication Step

**Feature Branch**: `015-booking-auth-step`
**Date**: 2025-01-05

## Overview

This feature uses **existing backend API contracts** - no new endpoints required.

## Endpoints Used

### POST /customers/me

**Purpose:** Create customer profile after successful OTP verification

**Location:** `backend/api/src/api/routes/customers.py`

**Request:**
```http
POST /api/customers/me
Authorization: Bearer <id_token>
Content-Type: application/json

{
  "name": "María García",      // 2-100 chars, optional
  "phone": "+34 612 345 678",  // 7-20 chars, optional
  "preferred_language": "en"   // "en" or "es", default "en"
}
```

**Success Response (201 Created):**
```json
{
  "customer_id": "uuid",
  "email": "maria@example.com",
  "cognito_sub": "cognito-sub-id",
  "name": "María García",
  "phone": "+34 612 345 678",
  "preferred_language": "en",
  "email_verified": true,
  "created_at": "2025-01-05T10:00:00Z",
  "updated_at": "2025-01-05T10:00:00Z"
}
```

**Error Responses:**

| Status | Scenario | Body |
|--------|----------|------|
| 401 | Missing/invalid JWT | `{"detail": "Authentication required: cognito_sub not found"}` |
| 400 | Missing email claim | `{"detail": "Missing email: could not extract from request"}` |
| 409 | Customer already exists | `{"detail": "Customer profile already exists"}` |

**Handling 409 (FR-020):**
The AuthStep component treats 409 as success - the customer profile already exists, so we proceed without error.

## Authentication Flow (Cognito)

No backend changes - uses existing Cognito EMAIL_OTP flow via Amplify:

1. `signIn({ username: email })` - Initiates OTP (existing user)
2. `signUp({ username: email, ... })` - Creates Cognito user if new
3. `confirmSignIn({ challengeResponse: code })` - Verifies OTP

## Generated Client Usage

Frontend uses the hey-api generated client:

```typescript
import { customersPostCustomersMe } from '@/lib/api/sdk.gen'

const result = await customersPostCustomersMe({
  body: {
    name: formData.name,
    phone: formData.phone,
    preferred_language: 'en',
  },
})
```

## No New Contracts Needed

- ✅ `POST /customers/me` - Exists, fully supports auth step requirements
- ✅ Cognito EMAIL_OTP - Configured in existing User Pool
- ✅ Generated API client - Already includes customer endpoints
