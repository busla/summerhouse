# API Contract: Customer Endpoints

**Feature**: 010-amplify-auth-refactor | **Date**: 2026-01-02 | **Phase**: 1

## Overview

These endpoints allow authenticated users to manage their customer profile. All endpoints require JWT authentication via API Gateway Cognito authorizer.

## Base URL

```
{API_BASE_URL}/api/customers
```

## Authentication

All endpoints require:
- `Authorization: Bearer {id_token}` header
- Token validated by API Gateway Cognito authorizer
- `sub` claim passed to backend via `x-user-sub` header

---

## GET /me

Get the current authenticated user's customer profile.

### Request

```http
GET /api/customers/me HTTP/1.1
Authorization: Bearer {id_token}
```

### Response (200 OK)

Customer found:

```json
{
  "guest_id": "GUEST-2025-ABC123",
  "email": "user@example.com",
  "name": "John Doe",
  "phone": "+34 612 345 678",
  "email_verified": true,
  "total_bookings": 3,
  "preferred_language": "en"
}
```

### Response (404 Not Found)

No customer record for authenticated user:

```json
{
  "error": "customer_not_found",
  "message": "No customer profile found for this account"
}
```

### Response (401 Unauthorized)

Missing or invalid token (handled by API Gateway):

```json
{
  "message": "Unauthorized"
}
```

---

## PUT /me

Update the current authenticated user's customer profile.

### Request

```http
PUT /api/customers/me HTTP/1.1
Authorization: Bearer {id_token}
Content-Type: application/json

{
  "name": "John Doe",
  "phone": "+34 612 345 678",
  "preferred_language": "es"
}
```

### Request Body Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | No | Full name (2-100 chars) |
| `phone` | string | No | Phone number (7-20 chars) |
| `preferred_language` | string | No | `"en"` or `"es"` |

All fields are optional - only provided fields are updated.

### Response (200 OK)

Profile updated:

```json
{
  "guest_id": "GUEST-2025-ABC123",
  "email": "user@example.com",
  "name": "John Doe",
  "phone": "+34 612 345 678",
  "email_verified": true,
  "total_bookings": 3,
  "preferred_language": "es"
}
```

### Response (404 Not Found)

No customer record to update:

```json
{
  "error": "customer_not_found",
  "message": "No customer profile found for this account"
}
```

### Response (422 Unprocessable Entity)

Validation error:

```json
{
  "detail": [
    {
      "loc": ["body", "name"],
      "msg": "String should have at least 2 characters",
      "type": "string_too_short"
    }
  ]
}
```

---

## POST /me

Create a customer profile for the authenticated user (if not exists).

### Request

```http
POST /api/customers/me HTTP/1.1
Authorization: Bearer {id_token}
Content-Type: application/json

{
  "name": "John Doe",
  "phone": "+34 612 345 678"
}
```

### Request Body Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | No | Full name (2-100 chars) |
| `phone` | string | No | Phone number (7-20 chars) |
| `preferred_language` | string | No | `"en"` or `"es"` (default: `"en"`) |

### Response (201 Created)

Profile created:

```json
{
  "guest_id": "GUEST-2025-ABC123",
  "email": "user@example.com",
  "name": "John Doe",
  "phone": "+34 612 345 678",
  "email_verified": true,
  "total_bookings": 0,
  "preferred_language": "en"
}
```

### Response (409 Conflict)

Profile already exists:

```json
{
  "error": "customer_exists",
  "message": "Customer profile already exists for this account"
}
```

---

## Implementation Notes

### Backend Claim Extraction

The backend extracts `cognito_sub` from the `x-user-sub` header (set by API Gateway integration):

```python
def get_current_customer(request: Request) -> Guest | None:
    sub = request.headers.get("x-user-sub")
    if not sub:
        raise HTTPException(401, "Missing user identity")
    return db.get_guest_by_cognito_sub(sub)
```

### Email Source

The email is extracted from JWT claims (set by Cognito during authentication). It cannot be changed via API - it's the source of truth from Cognito.

### Idempotent Profile Creation

`POST /me` is idempotent for the same `cognito_sub`. If a profile exists, return 409. The frontend should call `GET /me` first to check.

---

## OpenAPI Fragment

```yaml
paths:
  /api/customers/me:
    get:
      summary: Get current customer profile
      operationId: getCurrentCustomer
      tags: [Customers]
      security:
        - cognitoAuth: []
      responses:
        '200':
          description: Customer profile
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Customer'
        '404':
          description: Customer not found
        '401':
          description: Unauthorized

    put:
      summary: Update current customer profile
      operationId: updateCurrentCustomer
      tags: [Customers]
      security:
        - cognitoAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CustomerUpdate'
      responses:
        '200':
          description: Customer updated
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Customer'
        '404':
          description: Customer not found
        '422':
          description: Validation error

    post:
      summary: Create customer profile
      operationId: createCurrentCustomer
      tags: [Customers]
      security:
        - cognitoAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CustomerCreate'
      responses:
        '201':
          description: Customer created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Customer'
        '409':
          description: Customer already exists

components:
  schemas:
    Customer:
      type: object
      required: [guest_id, email, email_verified]
      properties:
        guest_id:
          type: string
          example: "GUEST-2025-ABC123"
        email:
          type: string
          format: email
        name:
          type: string
        phone:
          type: string
        email_verified:
          type: boolean
        total_bookings:
          type: integer
        preferred_language:
          type: string
          enum: [en, es]

    CustomerUpdate:
      type: object
      properties:
        name:
          type: string
          minLength: 2
          maxLength: 100
        phone:
          type: string
          minLength: 7
          maxLength: 20
        preferred_language:
          type: string
          enum: [en, es]

    CustomerCreate:
      type: object
      properties:
        name:
          type: string
          minLength: 2
          maxLength: 100
        phone:
          type: string
          minLength: 7
          maxLength: 20
        preferred_language:
          type: string
          enum: [en, es]
          default: en

  securitySchemes:
    cognitoAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
      description: Cognito User Pool ID token
```
