# Research: Stripe Payment Integration

**Phase**: 0 | **Date**: 2026-01-03 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Executive Summary

This research documents the existing payment patterns, Stripe SDK integration approach, and architectural decisions for replacing the mock payment provider with Stripe Checkout. The key finding is that the codebase already has a `PaymentService` with mock implementation and `PaymentProvider.STRIPE` enum value - we can extend the existing service rather than replacing it entirely.

---

## 1. Architecture Overview

### Current Payment Layer Structure

```
┌─────────────────────────────────────────────────────────────┐
│                    API Layer                                 │
│  (api/routes/payments.py - REST endpoints)                  │
│  POST /payments, GET /payments/{id}, POST /retry            │
├─────────────────────────────────────────────────────────────┤
│                   Service Layer                              │
│  (shared/services/payment_service.py - PaymentService)      │
│  process_payment(), process_refund(), get_payment()         │
│  Currently uses PaymentProvider.MOCK (always succeeds)      │
├─────────────────────────────────────────────────────────────┤
│                    Model Layer                               │
│  (shared/models/payment.py, enums.py)                       │
│  Payment, PaymentCreate, PaymentResult, PaymentProvider     │
│  PaymentProvider.STRIPE already exists!                     │
├─────────────────────────────────────────────────────────────┤
│                  Database Layer                              │
│  (DynamoDB: booking-{env}-payments)                         │
│  GSI: reservation-index for lookups by reservation_id       │
└─────────────────────────────────────────────────────────────┘
```

### Target Architecture (Stripe Integration)

```
┌─────────────────────────────────────────────────────────────┐
│                    API Layer (Extended)                      │
│  NEW: POST /payments/checkout-session (→ Stripe Checkout)   │
│  NEW: POST /webhooks/stripe (← Stripe webhook events)       │
│  NEW: POST /payments/{id}/refund                            │
│  MODIFIED: GET /payments/{reservation_id}/status            │
├─────────────────────────────────────────────────────────────┤
│                   Service Layer (Extended)                   │
│  NEW: SSMService for secure credential retrieval            │
│  MODIFIED: PaymentService → create_checkout_session()       │
│                           → process_webhook()               │
│                           → process_refund() (Stripe API)   │
├─────────────────────────────────────────────────────────────┤
│                External Services (NEW)                       │
│  Stripe API: Checkout Sessions, PaymentIntents, Refunds     │
│  AWS SSM: /booking/{env}/stripe/secret_key                  │
│          /booking/{env}/stripe/webhook_secret               │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Existing Code Analysis

### 2.1 Payment Model (Ready to Extend)

**Source**: `backend/shared/src/shared/models/payment.py`

```python
class Payment(BaseModel):
    """A payment transaction for a reservation."""
    model_config = ConfigDict(strict=True)

    payment_id: str = Field(..., description="Unique payment ID")
    reservation_id: str
    amount: int = Field(..., ge=0, description="Amount in EUR cents")
    currency: str = Field(default="EUR")
    status: TransactionStatus
    payment_method: PaymentMethod
    provider: PaymentProvider  # MOCK or STRIPE
    provider_transaction_id: str | None  # Can store Stripe PaymentIntent ID
    # ...
```

**Key observation**: The model already has `provider_transaction_id` which can store Stripe's `payment_intent_id`. We need to ADD:
- `stripe_checkout_session_id: str | None` - For tracking Checkout session
- `stripe_refund_id: str | None` - For tracking refund reference

### 2.2 PaymentProvider Enum (Stripe Already Defined)

**Source**: `backend/shared/src/shared/models/enums.py`

```python
class PaymentProvider(str, Enum):
    """Payment processing providers."""
    STRIPE = "stripe"  # ✅ Already exists!
    MOCK = "mock"
```

No enum changes needed - `STRIPE` provider is pre-defined.

### 2.3 PaymentService (Extension Points)

**Source**: `backend/shared/src/shared/services/payment_service.py`

Current mock implementation:

```python
def process_payment(self, data: PaymentCreate) -> PaymentResult:
    """Process a payment for a reservation.

    This is a mock implementation that always succeeds.
    In production, this would integrate with Stripe, PayPal, etc.
    """
    # MOCK: Simulate payment processing
    payment_success = True  # Always succeeds

    payment = Payment(
        provider=PaymentProvider.MOCK,
        provider_transaction_id=f"MOCK-{uuid.uuid4().hex[:8]}",
        # ...
    )
```

**Extension strategy**:
1. Add `StripePaymentProvider` class with Stripe SDK calls
2. Modify `PaymentService` to use provider based on configuration
3. Keep mock implementation for testing/development

### 2.4 Existing Payment Routes

**Source**: `backend/api/src/api/routes/payments.py`

| Endpoint | Current Implementation | Stripe Changes Needed |
|----------|----------------------|----------------------|
| `POST /payments` | Immediate mock payment | → Create Checkout Session, redirect |
| `GET /payments/{reservation_id}` | Query by reservation | Add Stripe metadata fields |
| `POST /payments/{reservation_id}/retry` | Re-process mock | → Create new Checkout Session |

**New endpoints needed**:
- `POST /payments/checkout-session` - Create Stripe Checkout session
- `POST /webhooks/stripe` - Handle Stripe webhook events
- `POST /payments/{payment_id}/refund` - Initiate Stripe refund

---

## 3. Stripe SDK Patterns

### 3.1 Client Initialization

**From Context7 research** (stripe-python library):

```python
from stripe import StripeClient

# Initialize with API key from SSM
client = StripeClient(api_key=ssm_service.get_stripe_secret_key())
```

### 3.2 Checkout Session Creation

```python
from stripe import StripeClient

client = StripeClient("sk_test_...")

# Create Checkout Session for a reservation
session = client.v1.checkout.sessions.create(
    params={
        "line_items": [{
            "price_data": {
                "currency": "eur",
                "unit_amount": 25000,  # €250.00 in cents
                "product_data": {"name": "Quesada Apartment - 5 nights"},
            },
            "quantity": 1,
        }],
        "mode": "payment",
        "success_url": "https://booking.example.com/payment/success?session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": "https://booking.example.com/payment/cancel",
        "expires_at": int(time.time()) + 1800,  # 30 minutes (FR-003)
        "metadata": {"reservation_id": "RES-2025-ABC123"},  # Link to reservation
    },
    options={"idempotency_key": f"checkout-{reservation_id}"},  # FR-004
)

# Return session.url for redirect
```

### 3.3 Webhook Signature Validation (FR-011)

```python
from stripe import Webhook, SignatureVerificationError

def process_stripe_webhook(payload: bytes, sig_header: str) -> dict:
    """Validate and process Stripe webhook event."""
    webhook_secret = ssm_service.get_stripe_webhook_secret()

    try:
        event = Webhook.construct_event(
            payload=payload,
            received_sig=sig_header,
            secret=webhook_secret,
            api_key=ssm_service.get_stripe_secret_key(),  # Required for V2
        )
    except SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Process event based on type
    if event.type == "checkout.session.completed":
        session = event.data.object
        reservation_id = session.metadata.get("reservation_id")
        # Update payment record, confirm reservation
    elif event.type == "charge.refunded":
        # Update refund status

    return {"received": True}
```

### 3.4 Refund Processing (FR-015, FR-016)

```python
from stripe import StripeClient

client = StripeClient("sk_test_...")

# Full refund
refund = client.v1.refunds.create(
    params={
        "payment_intent": "pi_xxx",  # From original payment
    }
)

# Partial refund (50% for 7-14 day cancellation)
refund = client.v1.refunds.create(
    params={
        "payment_intent": "pi_xxx",
        "amount": 12500,  # Half of €250.00 = €125.00 in cents
    }
)
```

### 3.5 Error Handling

```python
from stripe import StripeError

try:
    session = client.v1.checkout.sessions.create(params={...})
except StripeError as e:
    # Log error with Stripe error code (FR-024)
    logger.error(
        "Stripe API error",
        extra={
            "stripe_error_code": e.code,
            "stripe_error_message": str(e),
            "reservation_id": reservation_id,
        }
    )
    raise BookingError(
        code=ErrorCode.PAYMENT_FAILED,
        details={"stripe_error": str(e)},
    )
```

---

## 4. SSM Parameter Store Integration

### 4.1 Parameter Paths (from spec clarifications)

| Parameter | Path | Type |
|-----------|------|------|
| Publishable Key | `/booking/{env}/stripe/publishable_key` | SecureString |
| Secret Key | `/booking/{env}/stripe/secret_key` | SecureString |
| Webhook Secret | `/booking/{env}/stripe/webhook_secret` | SecureString |

### 4.2 SSM Service Pattern (NEW)

Create `backend/shared/src/shared/services/ssm_service.py`:

```python
"""SSM Parameter Store service for secure credential retrieval."""

import boto3
from functools import lru_cache
import os

_ssm_client = None

def _get_ssm_client():
    """Get or create singleton SSM client."""
    global _ssm_client
    if _ssm_client is None:
        _ssm_client = boto3.client("ssm")
    return _ssm_client


class SSMService:
    """Service for retrieving parameters from AWS SSM Parameter Store."""

    def __init__(self, environment: str | None = None):
        self.environment = environment or os.environ.get("ENVIRONMENT", "dev")
        self.client = _get_ssm_client()
        self._cache: dict[str, str] = {}  # Cache within Lambda invocation

    def get_parameter(self, name: str, decrypt: bool = True) -> str:
        """Get a parameter value from SSM."""
        if name in self._cache:
            return self._cache[name]

        response = self.client.get_parameter(
            Name=name,
            WithDecryption=decrypt,
        )
        value = response["Parameter"]["Value"]
        self._cache[name] = value
        return value

    def get_stripe_secret_key(self) -> str:
        """Get Stripe secret key from SSM."""
        return self.get_parameter(f"/booking/{self.environment}/stripe/secret_key")

    def get_stripe_webhook_secret(self) -> str:
        """Get Stripe webhook signing secret from SSM."""
        return self.get_parameter(f"/booking/{self.environment}/stripe/webhook_secret")


# Singleton accessor
_ssm_service_instance: SSMService | None = None

def get_ssm_service(environment: str | None = None) -> SSMService:
    """Get or create singleton SSM service instance."""
    global _ssm_service_instance
    if _ssm_service_instance is None:
        _ssm_service_instance = SSMService(environment)
    return _ssm_service_instance
```

### 4.3 Infrastructure Changes Required

**`infrastructure/modules/gateway-v2/main.tf`** needs SSM read permissions:

```hcl
# Add to Lambda IAM policy
{
  Sid    = "SSMStripeParameters"
  Effect = "Allow"
  Action = [
    "ssm:GetParameter",
    "ssm:GetParameters"
  ]
  Resource = [
    "arn:aws:ssm:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:parameter/booking/${module.label.environment}/stripe/*"
  ]
}
```

---

## 5. Webhook Processing Design

### 5.1 Idempotency Strategy (FR-014)

Store processed event IDs to prevent duplicate processing:

```python
class StripeWebhookEvent(BaseModel):
    """Log of received Stripe webhook events for idempotency."""
    model_config = ConfigDict(strict=True)

    event_id: str = Field(..., description="Stripe event ID (evt_xxx)")
    event_type: str = Field(..., description="e.g., checkout.session.completed")
    processed_at: datetime
    payload_hash: str = Field(..., description="SHA256 of payload for deduplication")
```

Check before processing:
```python
def is_event_processed(event_id: str) -> bool:
    """Check if webhook event was already processed."""
    item = db.get_item("webhook_events", {"event_id": event_id})
    return item is not None
```

### 5.2 Webhook Event Types to Handle (FR-012, FR-013)

| Event Type | Action |
|------------|--------|
| `checkout.session.completed` | Mark payment completed, confirm reservation |
| `charge.refunded` | Update payment record with refund details |
| `checkout.session.expired` | Log expired session (no action needed) |

### 5.3 Webhook Endpoint Pattern

```python
@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    payment_service: PaymentService = Depends(get_payment_service),
) -> dict:
    """Handle Stripe webhook events.

    **No JWT authentication** - uses Stripe signature validation instead.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing signature")

    return payment_service.process_webhook(payload, sig_header)
```

---

## 6. Checkout Session Flow

### 6.1 Sequence Diagram

```
┌────────┐    ┌────────────┐    ┌────────────┐    ┌──────────┐
│Frontend│    │ API Lambda │    │   Stripe   │    │ DynamoDB │
└───┬────┘    └─────┬──────┘    └─────┬──────┘    └────┬─────┘
    │               │                 │                 │
    │ POST /payments/checkout-session │                 │
    │──────────────>│                 │                 │
    │               │                 │                 │
    │               │ Create Checkout │                 │
    │               │     Session     │                 │
    │               │────────────────>│                 │
    │               │                 │                 │
    │               │  session.url    │                 │
    │               │<────────────────│                 │
    │               │                 │                 │
    │               │ Store pending   │                 │
    │               │    payment      │                 │
    │               │─────────────────────────────────>│
    │               │                 │                 │
    │  { url: "https://checkout.stripe.com/..." }      │
    │<──────────────│                 │                 │
    │               │                 │                 │
    │ Redirect to   │                 │                 │
    │ Stripe        │                 │                 │
    │──────────────────────────────>│                 │
    │               │                 │                 │
    │               │                 │                 │
    │   (User completes payment)     │                 │
    │               │                 │                 │
    │               │ Webhook: checkout.session.completed│
    │               │<────────────────│                 │
    │               │                 │                 │
    │               │ Update payment  │                 │
    │               │ Confirm reserv. │                 │
    │               │─────────────────────────────────>│
    │               │                 │                 │
```

### 6.2 Success/Cancel URLs

```python
# FR-020: Handle success and cancel return URLs
success_url = f"{frontend_url}/booking/success?session_id={{CHECKOUT_SESSION_ID}}"
cancel_url = f"{frontend_url}/booking/cancel?reservation_id={reservation_id}"
```

---

## 7. Error Handling Strategy

### 7.1 HTTP Status Code Mapping

| Stripe Scenario | HTTP Status | Error Code |
|-----------------|-------------|------------|
| Checkout session creation fails | 502 | PAYMENT_FAILED |
| Webhook signature invalid | 400 | N/A (not BookingError) |
| Refund amount exceeds original | 400 | PAYMENT_FAILED |
| Stripe API rate limited | 503 | PAYMENT_FAILED |
| Payment already refunded | 409 | PAYMENT_FAILED |

### 7.2 Structured Error Logging (FR-024)

```python
logger.error(
    "stripe_api_error",
    extra={
        "correlation_id": correlation_id,
        "reservation_id": reservation_id,
        "stripe_error_code": e.code if hasattr(e, 'code') else None,
        "stripe_error_type": type(e).__name__,
        "stripe_request_id": e.request_id if hasattr(e, 'request_id') else None,
    }
)
```

---

## 8. Data Model Extensions

### 8.1 Payment Model Extensions

Add to `shared/models/payment.py`:

```python
class Payment(BaseModel):
    # Existing fields...

    # NEW: Stripe-specific fields
    stripe_checkout_session_id: str | None = Field(
        default=None,
        description="Stripe Checkout session ID (cs_xxx)"
    )
    stripe_payment_intent_id: str | None = Field(
        default=None,
        description="Stripe PaymentIntent ID (pi_xxx)"
    )
    stripe_refund_id: str | None = Field(
        default=None,
        description="Stripe Refund ID (re_xxx)"
    )
```

### 8.2 Checkout Session Request Model

```python
class CheckoutSessionRequest(BaseModel):
    """Request to create a Stripe Checkout session."""
    model_config = ConfigDict(strict=True)

    reservation_id: str = Field(..., description="Reservation to pay for")
    success_url: str | None = Field(
        default=None,
        description="Override default success URL"
    )
    cancel_url: str | None = Field(
        default=None,
        description="Override default cancel URL"
    )
```

### 8.3 Checkout Session Response Model

```python
class CheckoutSessionResponse(BaseModel):
    """Response with Stripe Checkout session details."""
    model_config = ConfigDict(strict=True)

    session_id: str = Field(..., description="Stripe Checkout session ID")
    url: str = Field(..., description="Redirect URL for Stripe Checkout")
    expires_at: datetime = Field(..., description="Session expiration time")
    amount: int = Field(..., description="Amount in EUR cents")
```

---

## 9. Testing Strategy

### 9.1 Unit Tests with stripe-mock

Use Stripe's official test server:

```python
@pytest.fixture
def stripe_mock():
    """Start stripe-mock for testing."""
    # stripe-mock runs on port 12111 by default
    # Configure StripeClient to use mock endpoint
    client = StripeClient(
        api_key="sk_test_xxx",
        base_url="http://localhost:12111",
    )
    return client

def test_create_checkout_session(stripe_mock, payment_service):
    """Test Checkout session creation with mock Stripe."""
    result = payment_service.create_checkout_session(
        reservation_id="RES-2025-TEST",
        amount=25000,
    )
    assert result.session_id.startswith("cs_")
    assert "checkout.stripe.com" in result.url
```

### 9.2 Webhook Testing

```python
def test_webhook_signature_validation():
    """Test invalid webhook signatures are rejected."""
    response = client.post(
        "/api/webhooks/stripe",
        content=b'{"type": "fake"}',
        headers={"stripe-signature": "invalid_sig"},
    )
    assert response.status_code == 400

def test_checkout_completed_webhook(stripe_mock, db_session):
    """Test checkout.session.completed updates payment status."""
    # Create pending payment first
    payment = create_pending_payment(db_session)

    # Simulate webhook
    payload = create_webhook_payload("checkout.session.completed", {
        "metadata": {"reservation_id": payment.reservation_id}
    })
    sig = generate_test_signature(payload)

    response = client.post(
        "/api/webhooks/stripe",
        content=payload,
        headers={"stripe-signature": sig},
    )

    assert response.status_code == 200

    # Verify payment updated
    updated = get_payment(payment.payment_id)
    assert updated.status == TransactionStatus.COMPLETED
```

### 9.3 Integration Test Flow

```python
def test_full_payment_flow(client, stripe_mock, db_session):
    """Test complete payment flow from checkout to confirmation."""
    # 1. Create reservation
    reservation = create_test_reservation(db_session)

    # 2. Create checkout session
    response = client.post(
        "/api/payments/checkout-session",
        json={"reservation_id": reservation.reservation_id},
        headers=auth_headers,
    )
    assert response.status_code == 201
    session = response.json()

    # 3. Simulate webhook (Stripe would call this)
    webhook_response = simulate_checkout_completed(session["session_id"])
    assert webhook_response.status_code == 200

    # 4. Verify reservation confirmed
    reservation = get_reservation(reservation.reservation_id)
    assert reservation.status == ReservationStatus.CONFIRMED
```

---

## 10. Performance Considerations

### 10.1 Cold Start Impact

| Component | Cold Start Addition | Mitigation |
|-----------|-------------------|------------|
| SSM GetParameter | ~50-100ms | Cache in Lambda container |
| Stripe SDK init | ~20ms | Singleton pattern |
| Webhook validation | <10ms | Signature only, no API call |

### 10.2 Response Time Targets (from SC-007)

| Operation | Target | Strategy |
|-----------|--------|----------|
| Create Checkout Session | <1s | Single Stripe API call |
| Webhook Processing | <5s | Async DB writes, quick ACK |
| Payment Status Query | <200ms | DynamoDB single item read |

---

## 11. Open Questions (Resolved)

| Question | Resolution |
|----------|------------|
| Where to store Stripe keys? | **SSM Parameter Store** (SecureString) at `/booking/{env}/stripe/*` |
| Stripe Checkout vs Elements? | **Stripe Checkout** - hosted page, handles 3DS, reduces PCI scope |
| Webhook authentication? | **Stripe signature validation only** - no JWT required |
| How to handle webhook retries? | Store event IDs in DynamoDB, check before processing |
| Agent tools in scope? | **No** - this feature is REST API only |

---

## 12. Dependencies

### 12.1 Python Packages

Add to `backend/requirements-api.txt`:
```
stripe>=10.0.0  # Stripe Python SDK
```

### 12.2 Infrastructure

- Lambda IAM policy: Add SSM `GetParameter` permission
- SSM Parameters: Create `/booking/{env}/stripe/*` parameters manually
- API Gateway: No changes (REST API already configured)

---

## 13. References

- [Stripe Python SDK](https://github.com/stripe/stripe-python)
- [Stripe Checkout Integration](https://stripe.com/docs/checkout/quickstart)
- [Stripe Webhooks](https://stripe.com/docs/webhooks)
- [Stripe Test Cards](https://stripe.com/docs/testing)
- [AWS SSM Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)
- Existing codebase: `backend/shared/src/shared/services/payment_service.py`
