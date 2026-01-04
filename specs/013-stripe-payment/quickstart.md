# Quickstart: Stripe Payment Integration

**Phase**: 1 | **Date**: 2026-01-03 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Overview

This guide covers development, testing, and deployment of Stripe Checkout payment integration. The implementation uses Stripe's hosted checkout page (not Elements) for reduced PCI scope and automatic 3D Secure handling.

**Agent is out of scope** - this feature focuses on backend API endpoints and payment infrastructure only.

---

## Prerequisites

```bash
# Backend dependencies
task backend:install

# Verify installation
task backend:test  # Should pass existing tests
```

**Required Environment**:
- Python 3.13+
- UV package manager
- AWS credentials (for SSM Parameter Store access)
- Stripe CLI (for local webhook testing)

---

## Stripe Sandbox Setup

### 1. Get Stripe Test Keys

1. Log in to [Stripe Dashboard](https://dashboard.stripe.com/test/apikeys)
2. Copy your test API keys:
   - `pk_test_...` (Publishable key)
   - `sk_test_...` (Secret key)

### 2. Store Keys in SSM Parameter Store

```bash
# Store Stripe keys (replace with your actual test keys)
aws ssm put-parameter \
  --name "/booking/dev/stripe/publishable_key" \
  --value "pk_test_..." \
  --type "SecureString" \
  --overwrite

aws ssm put-parameter \
  --name "/booking/dev/stripe/secret_key" \
  --value "sk_test_..." \
  --type "SecureString" \
  --overwrite

# Webhook secret (get from Stripe CLI or Dashboard)
aws ssm put-parameter \
  --name "/booking/dev/stripe/webhook_secret" \
  --value "whsec_..." \
  --type "SecureString" \
  --overwrite
```

### 3. Install Stripe CLI (for local testing)

```bash
# macOS
brew install stripe/stripe-cli/stripe

# Login to Stripe CLI
stripe login

# Forward webhooks to local server
stripe listen --forward-to localhost:3001/api/webhooks/stripe
```

The CLI will output a webhook signing secret like `whsec_...` - use this for local development.

---

## Project Structure

```text
backend/
├── api/src/api/
│   ├── routes/
│   │   ├── payments.py      # MODIFY: Add Stripe endpoints
│   │   └── webhooks.py      # NEW: Stripe webhook handler
│   └── dependencies.py      # MODIFY: Add Stripe service
│
├── shared/src/shared/
│   ├── models/
│   │   └── payment.py       # MODIFY: Add Stripe fields
│   ├── services/
│   │   ├── payment_service.py  # MODIFY: Integrate Stripe
│   │   └── stripe_service.py   # NEW: Stripe SDK wrapper
│   └── config/
│       └── stripe.py        # NEW: Stripe configuration
│
└── tests/
    ├── unit/api/
    │   ├── test_payments_checkout.py    # NEW
    │   ├── test_payments_status.py      # NEW
    │   └── test_webhooks_stripe.py      # NEW
    └── fixtures/
        └── stripe_events.py             # NEW: Webhook fixtures
```

---

## Development Workflow

### 1. Create Stripe Configuration Module

```python
# shared/src/shared/config/stripe.py
"""Stripe configuration with SSM Parameter Store retrieval."""

import os
from functools import lru_cache

import boto3


@lru_cache
def get_stripe_config() -> dict[str, str]:
    """Retrieve Stripe configuration from SSM Parameter Store."""
    env = os.environ.get("ENVIRONMENT", "dev")
    ssm = boto3.client("ssm")

    # Batch retrieve all Stripe parameters
    response = ssm.get_parameters(
        Names=[
            f"/booking/{env}/stripe/secret_key",
            f"/booking/{env}/stripe/publishable_key",
            f"/booking/{env}/stripe/webhook_secret",
        ],
        WithDecryption=True,
    )

    config = {}
    for param in response["Parameters"]:
        name = param["Name"].split("/")[-1]  # Get last part of path
        config[name] = param["Value"]

    return config


def get_stripe_secret_key() -> str:
    """Get Stripe secret key for API calls."""
    return get_stripe_config()["secret_key"]


def get_stripe_webhook_secret() -> str:
    """Get Stripe webhook signing secret."""
    return get_stripe_config()["webhook_secret"]
```

### 2. Create Stripe Service (Test-First)

```python
# tests/unit/services/test_stripe_service.py
"""Unit tests for Stripe service."""

import pytest
from unittest.mock import MagicMock, patch


class TestStripeServiceCreateCheckoutSession:
    """Tests for checkout session creation."""

    @patch("shared.services.stripe_service.stripe")
    def test_creates_checkout_session_with_correct_params(
        self,
        mock_stripe: MagicMock,
    ) -> None:
        """Creates Stripe Checkout session with reservation details."""
        from shared.services.stripe_service import StripeService

        mock_stripe.checkout.Session.create.return_value = MagicMock(
            id="cs_test_abc123",
            url="https://checkout.stripe.com/c/pay/cs_test_abc123",
        )

        service = StripeService(api_key="sk_test_xxx")
        result = service.create_checkout_session(
            reservation_id="RES-2026-ABC123",
            payment_id="PAY-2026-DEF456",
            amount_cents=112500,
            customer_email="guest@example.com",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        assert result.session_id == "cs_test_abc123"
        assert result.checkout_url == "https://checkout.stripe.com/c/pay/cs_test_abc123"

        # Verify idempotency key uses reservation_id (FR-004)
        mock_stripe.checkout.Session.create.assert_called_once()
        call_kwargs = mock_stripe.checkout.Session.create.call_args.kwargs
        assert call_kwargs["idempotency_key"] == "RES-2026-ABC123"


    @patch("shared.services.stripe_service.stripe")
    def test_uses_eur_currency(
        self,
        mock_stripe: MagicMock,
    ) -> None:
        """All payments use EUR currency."""
        from shared.services.stripe_service import StripeService

        mock_stripe.checkout.Session.create.return_value = MagicMock(
            id="cs_test_abc123",
            url="https://checkout.stripe.com/c/pay/cs_test_abc123",
        )

        service = StripeService(api_key="sk_test_xxx")
        service.create_checkout_session(
            reservation_id="RES-2026-ABC123",
            payment_id="PAY-2026-DEF456",
            amount_cents=112500,
            customer_email="guest@example.com",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        call_kwargs = mock_stripe.checkout.Session.create.call_args.kwargs
        assert call_kwargs["line_items"][0]["price_data"]["currency"] == "eur"
```

### 3. Implement Stripe Service

```python
# shared/src/shared/services/stripe_service.py
"""Stripe SDK wrapper for payment operations."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import stripe
from stripe import Webhook, StripeClient


@dataclass
class CheckoutSessionResult:
    """Result of creating a Stripe Checkout session."""
    session_id: str
    checkout_url: str
    expires_at: datetime


@dataclass
class RefundResult:
    """Result of processing a Stripe refund."""
    refund_id: str
    amount: int
    status: str


class StripeService:
    """Handles Stripe API interactions."""

    def __init__(self, api_key: str) -> None:
        self.client = StripeClient(api_key)

    def create_checkout_session(
        self,
        *,
        reservation_id: str,
        payment_id: str,
        amount_cents: int,
        customer_email: str,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSessionResult:
        """Create a Stripe Checkout session for reservation payment.

        Args:
            reservation_id: Used as idempotency key (FR-004)
            payment_id: Internal payment ID for metadata
            amount_cents: Payment amount in EUR cents
            customer_email: Guest email for receipt
            success_url: Redirect URL after successful payment
            cancel_url: Redirect URL if payment cancelled

        Returns:
            CheckoutSessionResult with session ID and checkout URL
        """
        session = self.client.checkout.sessions.create(
            mode="payment",
            payment_method_types=["card"],
            customer_email=customer_email,
            line_items=[
                {
                    "price_data": {
                        "currency": "eur",
                        "unit_amount": amount_cents,
                        "product_data": {
                            "name": "Quesada Apartment Booking",
                            "description": f"Reservation {reservation_id}",
                        },
                    },
                    "quantity": 1,
                },
            ],
            metadata={
                "reservation_id": reservation_id,
                "payment_id": payment_id,
            },
            success_url=success_url,
            cancel_url=cancel_url,
            expires_after=1800,  # 30 minutes (FR-003)
            idempotency_key=reservation_id,  # FR-004
        )

        return CheckoutSessionResult(
            session_id=session.id,
            checkout_url=session.url,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )

    def create_refund(
        self,
        *,
        payment_intent_id: str,
        amount_cents: int | None = None,
    ) -> RefundResult:
        """Create a Stripe refund.

        Args:
            payment_intent_id: Stripe PaymentIntent ID to refund
            amount_cents: Partial refund amount (None for full refund)

        Returns:
            RefundResult with refund ID and status
        """
        refund_params = {"payment_intent": payment_intent_id}
        if amount_cents is not None:
            refund_params["amount"] = amount_cents

        refund = self.client.refunds.create(**refund_params)

        return RefundResult(
            refund_id=refund.id,
            amount=refund.amount,
            status=refund.status,
        )

    @staticmethod
    def verify_webhook_signature(
        payload: bytes,
        signature: str,
        webhook_secret: str,
    ) -> dict:
        """Verify Stripe webhook signature and return event.

        Args:
            payload: Raw request body bytes
            signature: Stripe-Signature header value
            webhook_secret: Webhook signing secret from SSM

        Returns:
            Parsed webhook event dict

        Raises:
            ValueError: If signature is invalid
        """
        try:
            event = Webhook.construct_event(
                payload=payload,
                sig_header=signature,
                secret=webhook_secret,
            )
            return event
        except stripe.SignatureVerificationError as e:
            raise ValueError(f"Invalid webhook signature: {e}")
```

### 4. Create Webhook Handler Route

```python
# api/src/api/routes/webhooks.py
"""Webhook endpoints for external service callbacks."""

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from shared.config.stripe import get_stripe_webhook_secret
from shared.services.stripe_service import StripeService
from shared.services.payment_service import PaymentService
from shared.services.dynamodb import get_dynamodb_service

router = APIRouter(tags=["webhooks"])


class WebhookResponse(BaseModel):
    """Response for webhook processing."""
    received: bool
    event_id: str | None = None
    event_type: str | None = None
    processing_result: str | None = None
    message: str | None = None


@router.post(
    "/webhooks/stripe",
    summary="Stripe webhook endpoint",
    description="""
    Receives webhook events from Stripe.

    **Security**: Validates Stripe signature (FR-011)

    **Idempotency** (FR-014):
    - Stores event_id in DynamoDB
    - Returns 200 for duplicate events

    **Supported Events**:
    - checkout.session.completed (FR-012)
    - charge.refunded (FR-013)
    """,
    response_model=WebhookResponse,
)
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: str = Header(..., alias="Stripe-Signature"),
) -> WebhookResponse:
    """Process Stripe webhook events."""
    # Get raw body for signature verification
    payload = await request.body()

    # Verify signature (FR-011)
    try:
        event = StripeService.verify_webhook_signature(
            payload=payload,
            signature=stripe_signature,
            webhook_secret=get_stripe_webhook_secret(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    event_id = event["id"]
    event_type = event["type"]

    # Check for duplicate (FR-014)
    db = get_dynamodb_service()
    if db.webhook_event_exists(event_id):
        return WebhookResponse(
            received=True,
            event_id=event_id,
            event_type=event_type,
            processing_result="duplicate",
            message="Event already processed",
        )

    # Process based on event type
    payment_service = PaymentService(db=db)

    if event_type == "checkout.session.completed":
        # FR-012: Confirm payment
        session = event["data"]["object"]
        reservation_id = session["metadata"]["reservation_id"]
        payment_id = session["metadata"]["payment_id"]

        payment_service.complete_payment(
            payment_id=payment_id,
            stripe_payment_intent_id=session["payment_intent"],
            stripe_checkout_session_id=session["id"],
        )

        processing_result = "success"

    elif event_type == "charge.refunded":
        # FR-013: Update refund status
        charge = event["data"]["object"]
        payment_intent_id = charge["payment_intent"]
        refund = charge["refunds"]["data"][0]  # Latest refund

        payment_service.record_refund(
            stripe_payment_intent_id=payment_intent_id,
            stripe_refund_id=refund["id"],
            refund_amount=refund["amount"],
        )

        processing_result = "success"

    else:
        # Unhandled event type - acknowledge but skip
        processing_result = "skipped"

    # Store event for idempotency (FR-014)
    db.store_webhook_event(event_id=event_id, event_type=event_type)

    return WebhookResponse(
        received=True,
        event_id=event_id,
        event_type=event_type,
        processing_result=processing_result,
    )
```

### 5. Create Checkout Session Endpoint

```python
# api/src/api/routes/payments.py (additions)
"""Payment endpoints - Stripe integration additions."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.security import AuthScope, require_auth, SecurityRequirement
from api.dependencies import get_payment_service, get_stripe_service
from shared.models.payment import Payment, PaymentStatus
from shared.services.payment_service import PaymentService
from shared.services.stripe_service import StripeService

router = APIRouter(prefix="/payments", tags=["payments"])


class CheckoutSessionRequest(BaseModel):
    """Request to create a Stripe Checkout session."""
    reservation_id: str = Field(..., description="Reservation ID to pay for")
    success_url: str | None = Field(
        default=None,
        description="URL to redirect after successful payment",
    )
    cancel_url: str | None = Field(
        default=None,
        description="URL to redirect if payment cancelled",
    )


class CheckoutSessionResponse(BaseModel):
    """Response with Stripe Checkout session details."""
    payment_id: str
    checkout_session_id: str
    checkout_url: str
    expires_at: datetime
    amount: int = Field(..., ge=0, description="Amount in EUR cents")
    currency: str = "EUR"


@router.post(
    "/checkout-session",
    summary="Create Stripe Checkout session",
    description="""
    Creates a Stripe Checkout session for a reservation payment.

    **Authentication**: JWT required (reservation owner only)

    **Idempotency**: Uses reservation_id as idempotency key.

    **Session Expiry**: 30 minutes from creation (FR-003)
    """,
    response_model=CheckoutSessionResponse,
    status_code=201,
)
async def create_checkout_session(
    request_body: CheckoutSessionRequest,
    request: Request,
    auth: SecurityRequirement = Depends(require_auth([AuthScope.OPENID])),
    payment_service: PaymentService = Depends(get_payment_service),
    stripe_service: StripeService = Depends(get_stripe_service),
) -> CheckoutSessionResponse:
    """Create a Stripe Checkout session for reservation payment."""
    user_sub = request.headers.get("x-user-sub")
    if not user_sub:
        raise HTTPException(status_code=401, detail="Missing user identity")

    # Validate reservation ownership and payable state
    reservation = payment_service.get_reservation(request_body.reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    if reservation.customer_id != user_sub:
        raise HTTPException(
            status_code=403,
            detail="You can only pay for your own reservations",
        )

    if reservation.status == "confirmed":
        raise HTTPException(
            status_code=400,
            detail="Reservation is already paid",
        )

    if reservation.status == "cancelled":
        raise HTTPException(
            status_code=400,
            detail="Cannot pay for cancelled reservations",
        )

    # Create payment record
    payment = payment_service.create_pending_payment(
        reservation_id=request_body.reservation_id,
        amount_cents=reservation.total_price,
    )

    # Default URLs if not provided
    base_url = "https://summerhouse.example"  # From config
    success_url = request_body.success_url or f"{base_url}/booking/success"
    cancel_url = request_body.cancel_url or f"{base_url}/booking/cancel"

    # Create Stripe Checkout session
    session = stripe_service.create_checkout_session(
        reservation_id=request_body.reservation_id,
        payment_id=payment.payment_id,
        amount_cents=reservation.total_price,
        customer_email=reservation.customer_email,
        success_url=success_url,
        cancel_url=cancel_url,
    )

    # Update payment with Stripe session ID
    payment_service.update_payment_session(
        payment_id=payment.payment_id,
        stripe_checkout_session_id=session.session_id,
    )

    return CheckoutSessionResponse(
        payment_id=payment.payment_id,
        checkout_session_id=session.session_id,
        checkout_url=session.checkout_url,
        expires_at=session.expires_at,
        amount=reservation.total_price,
        currency="EUR",
    )
```

---

## Testing Patterns

### Testing with Stripe Mocks

```python
# tests/unit/api/test_payments_checkout.py
"""Tests for checkout session creation."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from moto import mock_aws


class TestCreateCheckoutSession:
    """Tests for POST /payments/checkout-session."""

    @mock_aws
    @patch("api.routes.payments.get_stripe_service")
    def test_creates_checkout_session_for_valid_reservation(
        self,
        mock_stripe_service: MagicMock,
        create_tables,
        sample_reservation,
        auth_headers,
    ) -> None:
        """Creates Stripe Checkout session for pending reservation."""
        from api.main import app

        # Setup mock Stripe response
        mock_service = MagicMock()
        mock_service.create_checkout_session.return_value = MagicMock(
            session_id="cs_test_abc123",
            checkout_url="https://checkout.stripe.com/c/pay/cs_test_abc123",
            expires_at="2026-01-03T10:30:00Z",
        )
        mock_stripe_service.return_value = mock_service

        client = TestClient(app)
        response = client.post(
            "/api/payments/checkout-session",
            json={"reservation_id": sample_reservation.reservation_id},
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert "checkout_url" in data
        assert "payment_id" in data
        assert data["currency"] == "EUR"
```

### Testing Webhook Signature Validation

```python
# tests/unit/api/test_webhooks_stripe.py
"""Tests for Stripe webhook handler."""

import pytest
import json
import hmac
import hashlib
import time
from fastapi.testclient import TestClient
from moto import mock_aws


def generate_stripe_signature(payload: str, secret: str) -> str:
    """Generate valid Stripe webhook signature for testing."""
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload}"
    signature = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


class TestStripeWebhook:
    """Tests for POST /webhooks/stripe."""

    @mock_aws
    def test_rejects_invalid_signature(self, create_tables) -> None:
        """Returns 400 for invalid Stripe signature."""
        from api.main import app

        client = TestClient(app)
        response = client.post(
            "/api/webhooks/stripe",
            content=json.dumps({"id": "evt_test", "type": "test"}),
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": "invalid_signature",
            },
        )

        assert response.status_code == 400

    @mock_aws
    def test_handles_duplicate_events_idempotently(
        self,
        create_tables,
        sample_webhook_event,
    ) -> None:
        """Returns 200 and skips duplicate event processing."""
        from api.main import app

        # First call processes the event
        # Second call should return duplicate status
        # (Implementation stores event_id in DynamoDB)
        pass  # Implement with proper fixtures
```

---

## Stripe Test Cards

Use these test card numbers in Stripe Checkout:

| Card Number | Description |
|-------------|-------------|
| `4242 4242 4242 4242` | Succeeds and immediately processes |
| `4000 0025 0000 3155` | Requires 3D Secure authentication |
| `4000 0000 0000 9995` | Declined (insufficient funds) |
| `4000 0000 0000 0002` | Declined (generic) |
| `4000 0000 0000 3220` | 3DS required, then succeeds |

**Expiry**: Any future date | **CVC**: Any 3 digits | **ZIP**: Any 5 digits

---

## Local Development

### Running the API with Stripe

```bash
# Terminal 1: Start FastAPI dev server
task backend:dev

# Terminal 2: Forward Stripe webhooks to local server
stripe listen --forward-to localhost:3001/api/webhooks/stripe
```

### Testing Payment Flow Manually

```bash
# 1. Create a checkout session
curl -X POST http://localhost:3001/api/payments/checkout-session \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt_token>" \
  -d '{"reservation_id": "RES-2026-ABC123"}'

# Response includes checkout_url - open in browser to complete payment

# 2. Check payment status
curl http://localhost:3001/api/payments/RES-2026-ABC123/status

# 3. Process refund (after payment completes)
curl -X POST http://localhost:3001/api/payments/PAY-2026-DEF456/refund \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt_token>" \
  -d '{"reason": "Customer requested cancellation"}'
```

### Triggering Test Webhooks

```bash
# Trigger checkout.session.completed event
stripe trigger checkout.session.completed

# Trigger charge.refunded event
stripe trigger charge.refunded
```

---

## Deployment

### 1. Store Production Keys

```bash
# Production Stripe keys (live mode)
aws ssm put-parameter \
  --name "/booking/prod/stripe/publishable_key" \
  --value "pk_live_..." \
  --type "SecureString" \
  --overwrite

aws ssm put-parameter \
  --name "/booking/prod/stripe/secret_key" \
  --value "sk_live_..." \
  --type "SecureString" \
  --overwrite

aws ssm put-parameter \
  --name "/booking/prod/stripe/webhook_secret" \
  --value "whsec_..." \
  --type "SecureString" \
  --overwrite
```

### 2. Configure Stripe Webhook in Dashboard

1. Go to [Stripe Webhooks](https://dashboard.stripe.com/webhooks)
2. Add endpoint: `https://api.booking.example/api/webhooks/stripe`
3. Select events:
   - `checkout.session.completed`
   - `charge.refunded`
4. Copy the signing secret to SSM

### 3. Apply Infrastructure

```bash
task tf:plan:prod
task tf:apply:prod
```

---

## Checklist

### Setup Checklist

- [ ] Store Stripe test keys in SSM Parameter Store (dev)
- [ ] Install Stripe CLI for local webhook testing
- [ ] Verify webhook forwarding works locally

### Implementation Checklist

- [ ] **Stripe Config** - SSM Parameter retrieval (`shared/config/stripe.py`)
- [ ] **Stripe Service** - SDK wrapper (`shared/services/stripe_service.py`)
- [ ] **Checkout Endpoint** - POST `/payments/checkout-session` (FR-027)
- [ ] **Status Endpoint** - GET `/payments/{reservation_id}/status` (FR-028)
- [ ] **Retry Endpoint** - POST `/payments/{reservation_id}/retry` (FR-029)
- [ ] **Refund Endpoint** - POST `/payments/{payment_id}/refund` (FR-030)
- [ ] **Webhook Handler** - POST `/webhooks/stripe` (FR-010 to FR-014)
- [ ] **Payment Model** - Add Stripe fields to existing model
- [ ] **Webhook Event Table** - DynamoDB table for idempotency

### Testing Checklist

- [ ] Unit tests for all new endpoints
- [ ] Webhook signature validation tests
- [ ] Idempotency tests (duplicate webhook handling)
- [ ] Contract tests for OpenAPI spec
- [ ] Manual E2E test with Stripe test cards

### Deployment Checklist

- [ ] Store production Stripe keys in SSM
- [ ] Configure production webhook in Stripe Dashboard
- [ ] Verify webhook endpoint is accessible
- [ ] Test with real (test mode) payments

---

## Troubleshooting

### Common Issues

**"SSM parameter not found"**
- Verify parameter path matches: `/booking/{env}/stripe/...`
- Check AWS credentials have `ssm:GetParameter` permission
- Ensure `ENVIRONMENT` env var is set correctly

**"Invalid webhook signature"**
- Verify webhook secret is correct in SSM
- Ensure raw body is passed (not parsed JSON)
- Check `Stripe-Signature` header is present

**"Duplicate payment intent"**
- Idempotency key collision - verify reservation_id is unique
- Check for existing pending payments for same reservation

**"Checkout session expired"**
- Sessions expire after 30 minutes
- Create a new session with `/payments/checkout-session`

**"Refund failed - charge already refunded"**
- Payment was already refunded (check payment status first)
- Stripe prevents duplicate refunds automatically

---

## References

- [Data Model](./data-model.md) - Payment schemas with Stripe fields
- [API Contracts](./contracts/) - OpenAPI specifications
- [Research](./research.md) - Architecture decisions
- [Spec](./spec.md) - Functional requirements
- [Plan](./plan.md) - Implementation plan
- [Stripe Checkout Docs](https://stripe.com/docs/payments/checkout)
- [Stripe Webhooks Docs](https://stripe.com/docs/webhooks)
