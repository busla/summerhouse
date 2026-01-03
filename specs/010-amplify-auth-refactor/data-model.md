# Data Model: Amplify Authentication Refactor

**Feature**: 010-amplify-auth-refactor | **Date**: 2026-01-02 | **Phase**: 1

## Overview

This feature consolidates authentication to use Amplify-managed sessions. The data model remains largely unchanged - the existing `Guest` entity already has `cognito_sub` support. This document clarifies how entities relate in the simplified auth architecture.

## Entities

### Guest (Customer)

The `Guest` entity represents a customer in the system. Key fields for authentication:

| Field | Type | Description |
|-------|------|-------------|
| `guest_id` | `string` (UUID) | Primary key |
| `email` | `string` (email) | Verified email address |
| `cognito_sub` | `string` (UUID) | **Links to Cognito User Pool** |
| `name` | `string?` | Full name |
| `phone` | `string?` | Phone number |
| `email_verified` | `boolean` | Email verification status |
| `first_verified_at` | `datetime?` | First verification timestamp |
| `total_bookings` | `integer` | Count of completed bookings |
| `created_at` | `datetime` | Creation timestamp |
| `updated_at` | `datetime` | Last update timestamp |

**Source**: `backend/shared/src/shared/models/guest.py`

### Session (Amplify-Managed)

Sessions are NOT stored in the application database. Amplify manages session state client-side:

| Token | Validity | Purpose |
|-------|----------|---------|
| ID Token | 1 hour | User identity claims (sub, email) |
| Access Token | 1 hour | API authorization |
| Refresh Token | 30 days | Obtaining new tokens |

**Key Point**: The backend never sees or stores session tokens. It only receives validated claims from API Gateway.

### OTP Code (Cognito-Managed)

OTP codes are managed entirely by Cognito:

| Property | Value |
|----------|-------|
| Length | 6-8 digits |
| Expiration | 5 minutes |
| Max Attempts | 3 per code |
| Delivery | Email (via SES or Cognito) |

**Key Point**: No application-level storage of OTP codes.

## Indexes

### DynamoDB GSIs

The `guests` table has these indexes for auth-related queries:

| Index Name | Partition Key | Use Case |
|------------|---------------|----------|
| `email-index` | `email` | Find guest by email (signup flow) |
| `cognito-sub-index` | `cognito_sub` | Find guest by JWT sub claim |

**Source**: `backend/shared/src/shared/services/dynamodb.py:318-324`

## Entity Relationships

```
┌─────────────────────────────────────────────────────────┐
│                    Cognito User Pool                     │
│  ┌─────────────────────────────────────────────────┐    │
│  │ User                                              │    │
│  │ - sub: "12345678-1234-1234-1234-123456789012"    │    │
│  │ - email: "guest@example.com"                     │    │
│  │ - email_verified: true                           │    │
│  └───────────────────────┬──────────────────────────┘    │
└──────────────────────────┼──────────────────────────────┘
                           │ cognito_sub (1:1)
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    DynamoDB guests                       │
│  ┌─────────────────────────────────────────────────┐    │
│  │ Guest                                             │    │
│  │ - guest_id: "GUEST-2025-ABC123"                  │    │
│  │ - cognito_sub: "12345678-1234-..."               │◄───┼── Linked via GSI
│  │ - email: "guest@example.com"                     │    │
│  │ - name: "John Doe"                               │    │
│  └───────────────────────┬──────────────────────────┘    │
└──────────────────────────┼──────────────────────────────┘
                           │ guest_id (1:N)
                           ▼
┌─────────────────────────────────────────────────────────┐
│                 DynamoDB reservations                    │
│  ┌─────────────────────────────────────────────────┐    │
│  │ Reservation                                       │    │
│  │ - reservation_id: "RES-2025-XYZ789"              │    │
│  │ - guest_id: "GUEST-2025-ABC123"                  │    │
│  └──────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## Data Flow

### New User Registration

```
1. User enters email in GuestDetailsForm
2. Frontend calls signUp() → Cognito creates user
3. User confirms OTP → Account verified
4. On first booking, backend creates Guest with cognito_sub
```

### Returning User Authentication

```
1. User enters email in GuestDetailsForm
2. Frontend calls signIn() → Cognito sends OTP
3. User confirms OTP → Session created
4. API requests include JWT → API Gateway validates
5. Backend queries Guest by cognito_sub from claims
```

### Guest Record Linking

Two scenarios for `cognito_sub` binding:

**A) New User (Signup → Booking)**:
- Guest record created with `cognito_sub` from JWT `sub` claim
- Single source of truth from registration

**B) Existing Guest (Pre-Auth Era)**:
- Guest exists with email but no `cognito_sub`
- On first authenticated request, bind `cognito_sub`
- Uses `update_guest_cognito_sub()` in DynamoDB service

```python
# backend/shared/src/shared/services/dynamodb.py:361-381
def update_guest_cognito_sub(self, guest_id: str, cognito_sub: str):
    """Bind a Cognito sub to an existing guest."""
    return self.update_item(
        table="guests",
        key={"guest_id": guest_id},
        update_expression="SET cognito_sub = :sub",
        expression_attribute_values={":sub": cognito_sub},
    )
```

## What's NOT Changing

| Component | Status | Notes |
|-----------|--------|-------|
| Guest model | ✅ Keep | Already has `cognito_sub` |
| Reservation model | ✅ Keep | Links to `guest_id`, not auth |
| DynamoDB indexes | ✅ Keep | `cognito-sub-index` exists |
| Guest service | ✅ Keep | `get_guest_by_cognito_sub()` exists |

## What's Being Simplified

| Component | Before | After |
|-----------|--------|-------|
| Session storage | DynamoDB + localStorage + AgentCore vault | Amplify only |
| Auth tokens | Multiple sources | Single Cognito source |
| User binding | Complex OAuth2 flows | Simple cognito_sub lookup |

## Validation Rules

### Guest Creation (with Auth)

```python
# When creating guest from authenticated request
guest = Guest(
    guest_id=generate_guest_id(),
    email=jwt_claims["email"],  # From ID token
    cognito_sub=jwt_claims["sub"],  # Always set for new users
    name=request.name,
    phone=request.phone,
    email_verified=True,  # Cognito verified
    first_verified_at=datetime.now(UTC),
    created_at=datetime.now(UTC),
    updated_at=datetime.now(UTC),
)
```

### Guest Lookup (API Request)

```python
# When handling authenticated request
def get_current_guest(request: Request) -> Guest | None:
    sub = request.headers.get("x-user-sub")  # From API Gateway
    if not sub:
        return None
    return db.get_guest_by_cognito_sub(sub)
```

## No Schema Changes Required

The existing Guest model in `backend/shared/src/shared/models/guest.py` already has all required fields. No migrations or schema updates needed.
