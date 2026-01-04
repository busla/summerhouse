# Data Model: Stripe Payment Integration

**Phase**: 1 | **Date**: 2026-01-03 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

## Overview

This document defines data models for the Stripe Payment Integration feature. Models follow these conventions:

- **Extend existing models** from `shared/models/` where appropriate
- **Create Stripe-specific models** for webhook events and checkout sessions
- **Use Pydantic v2 strict mode** for all models
- **Include examples** for OpenAPI documentation quality
- **Amounts in EUR cents** (not euros) to avoid floating-point issues

> **Note on PaymentSession**: The `PaymentSession` entity mentioned in spec.md is a **transient, Stripe-managed object**.
> It is NOT persisted in our DynamoDB tables. Stripe Checkout sessions are created via API, returned as a `checkout_url`,
> and tracked only by their `session_id` stored in the `Payment.stripe_checkout_session_id` field.
> The `CheckoutSessionRequest`/`CheckoutSessionResponse` models below handle the API contract.

---

## Enumerations (Existing)

All existing enums in `shared/models/enums.py` remain unchanged:

| Enum | Values | Notes |
|------|--------|-------|
| `PaymentProvider` | `stripe`, `mock` | **STRIPE already exists** - no changes needed |
| `TransactionStatus` | `pending`, `completed`, `failed`, `refunded` | Used for payment status |
| `PaymentMethod` | `card`, `paypal`, `bank_transfer` | Card used for Stripe |

---

## Model Changes Summary

| Model | File | Action | Changes |
|-------|------|--------|---------|
| `Payment` | `shared/models/payment.py` | **MODIFY** | Add Stripe-specific optional fields |
| `PaymentResult` | `shared/models/payment.py` | **MODIFY** | Add `checkout_url` for Stripe redirect |
| `StripeWebhookEvent` | `shared/models/stripe_webhook.py` | **NEW** | Webhook event logging |
| `CheckoutSessionRequest` | `api/models/payments.py` | **NEW** | Create session request |
| `CheckoutSessionResponse` | `api/models/payments.py` | **NEW** | Session URL response |
| `RefundRequest` | `api/models/payments.py` | **NEW** | Refund initiation request |
| `RefundResponse` | `api/models/payments.py` | **NEW** | Refund result response |

---

## Core Models

### Payment (Extended)

**File**: `shared/models/payment.py`
**Action**: MODIFY - Add optional Stripe fields

```python
class Payment(BaseModel):
    """A payment transaction for a reservation.

    Amounts are stored in EUR cents.
    Supports both mock provider (testing) and Stripe (production).
    """

    model_config = ConfigDict(strict=True)

    # Existing fields (unchanged)
    payment_id: str = Field(..., description="Unique payment ID")
    reservation_id: str = Field(..., description="Reference to Reservation")
    amount: int = Field(..., ge=0, description="Amount in EUR cents")
    currency: str = Field(default="EUR", description="Currency code")
    status: TransactionStatus = Field(..., description="Transaction status")
    payment_method: PaymentMethod = Field(..., description="Payment method used")
    provider: PaymentProvider = Field(..., description="Payment provider")
    provider_transaction_id: str | None = Field(
        default=None, description="External transaction reference (PaymentIntent ID for Stripe)"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    completed_at: datetime | None = Field(
        default=None, description="Completion timestamp"
    )
    error_message: str | None = Field(
        default=None, description="Error details if failed"
    )

    # NEW: Stripe-specific fields (optional for backward compatibility)
    stripe_checkout_session_id: str | None = Field(
        default=None,
        description="Stripe Checkout Session ID (cs_xxx)",
        examples=["cs_test_abc123def456"],
    )
    stripe_payment_intent_id: str | None = Field(
        default=None,
        description="Stripe PaymentIntent ID (pi_xxx) - also stored in provider_transaction_id",
        examples=["pi_3ABC123DEF456"],
    )
    stripe_refund_id: str | None = Field(
        default=None,
        description="Stripe Refund ID (re_xxx) if refunded",
        examples=["re_3ABC123DEF456"],
    )
    refund_amount: int | None = Field(
        default=None,
        ge=0,
        description="Refund amount in EUR cents (if partial or full refund)",
    )
    refunded_at: datetime | None = Field(
        default=None,
        description="Timestamp when refund was processed",
    )
```

**Example (Stripe payment)**:
```json
{
  "payment_id": "PAY-2026-ABC123",
  "reservation_id": "RES-2026-XYZ789",
  "amount": 112500,
  "currency": "EUR",
  "status": "completed",
  "payment_method": "card",
  "provider": "stripe",
  "provider_transaction_id": "pi_3ABC123DEF456",
  "created_at": "2026-01-03T10:00:00Z",
  "completed_at": "2026-01-03T10:02:15Z",
  "error_message": null,
  "stripe_checkout_session_id": "cs_test_abc123def456",
  "stripe_payment_intent_id": "pi_3ABC123DEF456",
  "stripe_refund_id": null,
  "refund_amount": null,
  "refunded_at": null
}
```

---

### PaymentResult (Extended)

**File**: `shared/models/payment.py`
**Action**: MODIFY - Add checkout_url for Stripe redirect

```python
class PaymentResult(BaseModel):
    """Result of a payment operation.

    For Stripe Checkout, includes the redirect URL.
    For mock provider, includes transaction status only.
    """

    model_config = ConfigDict(strict=True)

    payment_id: str
    status: TransactionStatus
    provider_transaction_id: str | None = None
    error_message: str | None = None

    # NEW: Stripe Checkout redirect URL
    checkout_url: str | None = Field(
        default=None,
        description="Stripe Checkout URL for payment redirect",
        examples=["https://checkout.stripe.com/c/pay/cs_test_abc123"],
    )
    expires_at: datetime | None = Field(
        default=None,
        description="When the checkout session expires (30 minutes)",
    )
```

**Example (Stripe checkout session created)**:
```json
{
  "payment_id": "PAY-2026-ABC123",
  "status": "pending",
  "provider_transaction_id": null,
  "error_message": null,
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_abc123def456",
  "expires_at": "2026-01-03T10:30:00Z"
}
```

---

## New Models

### StripeWebhookEvent

**File**: `shared/models/stripe_webhook.py` (NEW)
**Purpose**: Log received webhook events for idempotency and auditing

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class StripeWebhookEvent(BaseModel):
    """Log of a received Stripe webhook event.

    Used for:
    - Idempotency: prevent processing same event twice
    - Auditing: track all webhook deliveries
    - Debugging: investigate payment issues
    """

    model_config = ConfigDict(strict=True)

    event_id: str = Field(
        ...,
        description="Stripe event ID (evt_xxx)",
        examples=["evt_1ABC123DEF456"],
    )
    event_type: str = Field(
        ...,
        description="Stripe event type",
        examples=["checkout.session.completed", "charge.refunded"],
    )
    processed_at: datetime = Field(
        ...,
        description="When the event was processed",
    )
    payload_hash: str = Field(
        ...,
        description="SHA-256 hash of payload for deduplication",
        examples=["a1b2c3d4e5f6..."],
    )
    reservation_id: str | None = Field(
        default=None,
        description="Associated reservation ID from metadata",
    )
    payment_id: str | None = Field(
        default=None,
        description="Associated payment ID if created/updated",
    )
    processing_result: str = Field(
        default="success",
        description="Result of processing: success, duplicate, error",
    )
    error_message: str | None = Field(
        default=None,
        description="Error details if processing failed",
    )
```

**DynamoDB Table**: `booking-{env}-stripe-webhook-events`

| Attribute | Type | Description |
|-----------|------|-------------|
| `event_id` | String (PK) | Stripe event ID |
| `event_type` | String | Event type for filtering |
| `processed_at` | String (ISO) | Processing timestamp |
| `payload_hash` | String | For deduplication |
| `reservation_id` | String | From checkout session metadata |
| `payment_id` | String | Created/updated payment |
| `processing_result` | String | success/duplicate/error |
| `error_message` | String | Error details |
| `ttl` | Number | Auto-delete after 90 days |

**GSI**: `event_type-index` on `event_type` for querying by event type.

---

### CheckoutSessionRequest

**File**: `api/models/payments.py` (NEW)
**Purpose**: Request to create a Stripe Checkout session

```python
class CheckoutSessionRequest(BaseModel):
    """Request to create a Stripe Checkout session.

    Amount is determined by the reservation total - not user-provided.
    Success/cancel URLs are optional for API flexibility.
    """

    model_config = ConfigDict(strict=True)

    reservation_id: str = Field(
        ...,
        description="Reservation to pay for",
        examples=["RES-2026-ABC123"],
    )
    success_url: str | None = Field(
        default=None,
        description="URL to redirect after successful payment",
        examples=["https://example.com/booking/success?session_id={CHECKOUT_SESSION_ID}"],
    )
    cancel_url: str | None = Field(
        default=None,
        description="URL to redirect if payment is cancelled",
        examples=["https://example.com/booking/cancel"],
    )
```

**Example Request**:
```json
{
  "reservation_id": "RES-2026-ABC123",
  "success_url": "https://summerhouse.example.com/booking/success?session_id={CHECKOUT_SESSION_ID}",
  "cancel_url": "https://summerhouse.example.com/booking/cancel"
}
```

---

### CheckoutSessionResponse

**File**: `api/models/payments.py` (NEW)
**Purpose**: Response with Stripe Checkout session details

```python
class CheckoutSessionResponse(BaseModel):
    """Response from creating a Stripe Checkout session."""

    model_config = ConfigDict(strict=True)

    payment_id: str = Field(
        ...,
        description="Internal payment ID for tracking",
        examples=["PAY-2026-ABC123"],
    )
    checkout_session_id: str = Field(
        ...,
        description="Stripe Checkout Session ID",
        examples=["cs_test_abc123def456"],
    )
    checkout_url: str = Field(
        ...,
        description="URL to redirect user to Stripe Checkout",
        examples=["https://checkout.stripe.com/c/pay/cs_test_abc123"],
    )
    expires_at: datetime = Field(
        ...,
        description="When the checkout session expires",
    )
    amount: int = Field(
        ...,
        ge=0,
        description="Payment amount in EUR cents",
        examples=[112500],
    )
    currency: str = Field(
        default="EUR",
        description="Currency code",
    )
```

**Example Response**:
```json
{
  "payment_id": "PAY-2026-ABC123",
  "checkout_session_id": "cs_test_abc123def456",
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_abc123def456",
  "expires_at": "2026-01-03T10:30:00Z",
  "amount": 112500,
  "currency": "EUR"
}
```

---

### RefundRequest

**File**: `api/models/payments.py` (NEW)
**Purpose**: Request to initiate a refund

```python
class RefundRequest(BaseModel):
    """Request to initiate a refund for a payment.

    Amount is optional - if not provided, full refund is assumed.
    Reason is optional but recommended for record-keeping.
    """

    model_config = ConfigDict(strict=True)

    amount: int | None = Field(
        default=None,
        ge=0,
        description="Refund amount in EUR cents. If not provided, refunds full amount.",
        examples=[56250],
    )
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Reason for refund",
        examples=["Customer cancelled 10 days before check-in (50% refund policy)"],
    )
```

**Example Request (partial refund)**:
```json
{
  "amount": 56250,
  "reason": "Customer cancelled 10 days before check-in (50% refund policy)"
}
```

**Example Request (full refund)**:
```json
{
  "reason": "Customer cancelled 20 days before check-in (full refund policy)"
}
```

---

### RefundResponse

**File**: `api/models/payments.py` (NEW)
**Purpose**: Response from refund operation

```python
class RefundResponse(BaseModel):
    """Response from initiating a refund."""

    model_config = ConfigDict(strict=True)

    payment_id: str = Field(
        ...,
        description="Original payment ID",
    )
    stripe_refund_id: str = Field(
        ...,
        description="Stripe Refund ID",
        examples=["re_3ABC123DEF456"],
    )
    amount: int = Field(
        ...,
        ge=0,
        description="Refunded amount in EUR cents",
    )
    status: str = Field(
        ...,
        description="Refund status: succeeded, pending, failed",
        examples=["succeeded"],
    )
    refunded_at: datetime = Field(
        ...,
        description="When refund was processed",
    )
```

**Example Response**:
```json
{
  "payment_id": "PAY-2026-ABC123",
  "stripe_refund_id": "re_3ABC123DEF456",
  "amount": 56250,
  "status": "succeeded",
  "refunded_at": "2026-01-03T14:30:00Z"
}
```

---

### PaymentStatusResponse

**File**: `api/models/payments.py` (NEW)
**Purpose**: Detailed payment status for reservation

```python
class PaymentStatusResponse(BaseModel):
    """Detailed payment status for a reservation.

    Includes full payment history and current state.
    """

    model_config = ConfigDict(strict=True)

    reservation_id: str
    payment: Payment | None = Field(
        default=None,
        description="Most recent/completed payment record",
    )
    has_completed_payment: bool = Field(
        ...,
        description="Whether a successful payment exists",
    )
    is_refunded: bool = Field(
        default=False,
        description="Whether payment has been refunded",
    )
    refund_amount: int | None = Field(
        default=None,
        description="Refund amount in EUR cents if refunded",
    )
    payment_attempts: int = Field(
        default=0,
        description="Number of payment attempts made",
    )
```

---

## DynamoDB Schema Changes

### Existing Table: `booking-{env}-payments`

**Current Schema** (unchanged):

| Attribute | Type | Description |
|-----------|------|-------------|
| `payment_id` | String (PK) | Unique payment ID |
| `reservation_id` | String | Foreign key to reservations |
| `amount` | Number | Amount in EUR cents |
| `currency` | String | Currency code (EUR) |
| `status` | String | Transaction status |
| `payment_method` | String | card/paypal/bank_transfer |
| `provider` | String | stripe/mock |
| `provider_transaction_id` | String | External transaction ID |
| `created_at` | String (ISO) | Creation timestamp |
| `completed_at` | String (ISO) | Completion timestamp |
| `error_message` | String | Error details |

**New Attributes** (add to existing table):

| Attribute | Type | Description |
|-----------|------|-------------|
| `stripe_checkout_session_id` | String | Checkout session ID |
| `stripe_payment_intent_id` | String | PaymentIntent ID |
| `stripe_refund_id` | String | Refund ID if refunded |
| `refund_amount` | Number | Refund amount in cents |
| `refunded_at` | String (ISO) | Refund timestamp |

**GSI**: `reservation_id-index` (existing) - no changes needed.

---

### New Table: `booking-{env}-stripe-webhook-events`

**Purpose**: Store webhook events for idempotency and auditing.

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| `event_id` | String | PK | Stripe event ID |
| `event_type` | String | GSI PK | Event type |
| `processed_at` | String | | ISO timestamp |
| `payload_hash` | String | | SHA-256 hash |
| `reservation_id` | String | | Associated reservation |
| `payment_id` | String | | Associated payment |
| `processing_result` | String | | success/duplicate/error |
| `error_message` | String | | Error details |
| `ttl` | Number | | TTL for auto-deletion |

**GSI**: `event_type-index`
- Partition Key: `event_type`
- Sort Key: `processed_at`
- Projection: ALL

**TTL**: 90 days (7776000 seconds from `processed_at`)

---

## SSM Parameters

Stripe API keys stored in AWS SSM Parameter Store (SecureString):

| Parameter Path | Type | Description |
|----------------|------|-------------|
| `/booking/{env}/stripe/publishable_key` | SecureString | Stripe publishable key (pk_test_xxx) |
| `/booking/{env}/stripe/secret_key` | SecureString | Stripe secret key (sk_test_xxx) |
| `/booking/{env}/stripe/webhook_secret` | SecureString | Webhook signing secret (whsec_xxx) |

---

## Model Relationships

```
┌─────────────────┐
│   Reservation   │
│  reservation_id │◄──────────────────┐
└────────┬────────┘                   │
         │                            │
         │ 1:N                        │
         ▼                            │
┌─────────────────┐                   │
│     Payment     │                   │
│   payment_id    │                   │
│ reservation_id ─┼───────────────────┘
│ stripe_*_id     │
└────────┬────────┘
         │
         │ referenced by
         ▼
┌────────────────────────┐
│  StripeWebhookEvent    │
│     event_id           │
│    payment_id ─────────┘
│  reservation_id        │
└────────────────────────┘
```

---

## Validation Rules

### Payment Validation

| Field | Validation | Error |
|-------|------------|-------|
| `amount` | >= 0 | "Amount must be non-negative" |
| `reservation_id` | Must exist | ERR_006 RESERVATION_NOT_FOUND |
| `payment_method` | card for Stripe | "Stripe only supports card payments" |

### Refund Validation

| Condition | Rule | Error |
|-----------|------|-------|
| Payment exists | Must have completed payment | "No payment found to refund" |
| Not already refunded | `stripe_refund_id` is null | "Payment already refunded" |
| Amount valid | <= original amount | "Refund amount exceeds payment" |

### Webhook Validation

| Check | Method | Action |
|-------|--------|--------|
| Signature valid | `Webhook.construct_event()` | Return 400 if invalid |
| Event not duplicate | Check `event_id` in DynamoDB | Return 200 (idempotent) |
| Reservation exists | Lookup by metadata | Log warning, skip processing |

---

## Migration Notes

1. **Backward Compatibility**: All new fields are optional (`None` default), so existing Payment records work without migration.

2. **No Schema Migration**: DynamoDB is schema-less. New attributes are simply added to new records.

3. **Provider Detection**: Use `provider == PaymentProvider.STRIPE` to determine if Stripe-specific fields should be populated.

4. **Idempotency**: The `stripe_checkout_session_id` field also serves as an idempotency key - creating a session for the same reservation reuses the existing session if still valid.
