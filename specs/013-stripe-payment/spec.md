# Feature Specification: Stripe Payment Integration

**Feature Branch**: `013-stripe-payment`
**Created**: 2026-01-03
**Status**: Draft
**Input**: User description: "Implement payment feature using Stripe sandbox account"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Complete Booking Payment (Priority: P1)

A guest has created a reservation and needs to pay to confirm their booking. They click a "Pay Now" button, provide their card details through a secure Stripe Checkout form, and complete the transaction. The system confirms the payment and updates the reservation status.

**Why this priority**: This is the core value proposition - without payment processing, reservations cannot be confirmed and the business cannot generate revenue. This unlocks the full booking funnel.

**Independent Test**: Can be fully tested by creating a reservation, initiating payment with Stripe test card numbers (e.g., 4242 4242 4242 4242), and verifying the reservation status changes to "confirmed" with a stored payment record.

**Acceptance Scenarios**:

1. **Given** a guest has a pending reservation, **When** they click "Pay Now", **Then** the system redirects them to a Stripe Checkout page.

2. **Given** a guest is on the Stripe Checkout page, **When** they enter valid card details and submit, **Then** payment is processed successfully and they are redirected to a confirmation page.

3. **Given** a successful payment is processed, **When** the payment webhook is received, **Then** the reservation status updates to "confirmed" and the payment record is stored.

4. **Given** a successful payment, **When** the guest views their reservation, **Then** the system shows confirmed status with booking details.

5. **Given** a payment fails (e.g., declined card), **When** the guest is redirected back, **Then** the system shows an error message and offers to retry.

---

### User Story 2 - View Payment Status (Priority: P2)

A guest who previously started a booking wants to check if their payment was successful or if they still need to pay. They view their reservation details and see clear information about the payment state.

**Why this priority**: Essential for customer service and reducing support inquiries. Guests need visibility into their booking status.

**Independent Test**: Can be tested by checking payment status for reservations in various states (pending, paid, refunded).

**Acceptance Scenarios**:

1. **Given** a guest has a paid reservation, **When** they view their reservation, **Then** the system shows payment confirmation with transaction reference and amount.

2. **Given** a guest has an unpaid reservation, **When** they view their reservation, **Then** the system shows the amount due and a "Pay Now" button.

3. **Given** a guest has a refunded reservation, **When** they view their reservation, **Then** the system shows refund details including amount and date.

---

### User Story 3 - Process Refunds (Priority: P3)

A guest cancels their reservation within the refund window, and the system processes a refund according to the cancellation policy. The refund is processed through Stripe and the guest receives their money back.

**Why this priority**: Refunds are essential for customer trust and compliance with cancellation policies. Required for handling cancellations gracefully.

**Independent Test**: Can be tested by cancelling a paid reservation and verifying the refund is processed in Stripe and recorded in the system.

**Acceptance Scenarios**:

1. **Given** a guest cancels 14+ days before check-in, **When** the cancellation is processed, **Then** a full refund is issued via Stripe.

2. **Given** a guest cancels 7-14 days before check-in, **When** the cancellation is processed, **Then** a 50% refund is issued via Stripe.

3. **Given** a guest cancels less than 7 days before check-in, **When** the cancellation is processed, **Then** no refund is issued and the guest is informed of the policy.

4. **Given** a refund is processed successfully, **When** the Stripe webhook is received, **Then** the payment record is updated with refund details.

---

### User Story 4 - Retry Failed Payment (Priority: P4)

A guest's payment failed due to a declined card or network error. They want to try again with the same or a different card. The system allows them to retry without losing their reservation.

**Why this priority**: Payment failures are inevitable; a smooth retry experience prevents lost bookings.

**Independent Test**: Can be tested by simulating a failed payment (using Stripe test cards for decline scenarios) and then successfully retrying.

**Acceptance Scenarios**:

1. **Given** a payment failed, **When** the guest clicks "Try Again", **Then** the system creates a new Stripe Checkout session.

2. **Given** multiple payment failures, **When** the guest retries, **Then** the system allows up to 3 attempts before suggesting alternative methods.

3. **Given** a failed payment attempt, **When** the reservation is still within hold window, **Then** the availability remains reserved for the guest.

---

### Edge Cases

- What happens if a user closes the browser during payment? (Payment session expires after 30 minutes; reservation returns to pending; availability remains held for 24 hours)
- What happens if webhook delivery fails? (Stripe retries webhooks; system reconciles payment status on next reservation query)
- What happens if Stripe is unavailable? (System shows error message and asks guest to try again shortly)
- What happens if the same payment is processed twice? (Idempotency keys prevent duplicate charges; second attempt returns existing payment)
- What happens if a refund fails in Stripe? (Error is logged; manual refund process triggered; guest is informed of delay)
- What happens with 3D Secure authentication? (Stripe Checkout handles 3DS automatically; user completes authentication before payment confirmation)
- What happens with currency conversion? (All payments are in EUR; no currency conversion supported in MVP)

## Requirements *(mandatory)*

### Functional Requirements

**Payment Session Creation**

- **FR-001**: System MUST create a Stripe Checkout session when a guest is ready to pay for their reservation
- **FR-002**: Payment sessions MUST include the reservation amount, description, and customer email
- **FR-003**: Payment sessions MUST expire after 30 minutes if not completed
- **FR-004**: System MUST use idempotency keys based on reservation ID to prevent duplicate charges

**Payment Processing**

- **FR-005**: System MUST accept payments via Stripe Checkout (card payments)
- **FR-006**: System MUST store Stripe test API keys (pk_test, sk_test) securely in AWS SSM Parameter Store (SecureString)
- **FR-007**: System MUST update reservation status to "confirmed" upon successful payment
- **FR-008**: System MUST create a Payment record with Stripe transaction ID (PaymentIntent ID)
- **FR-009**: System MUST handle 3D Secure authentication automatically via Stripe Checkout

**Webhook Processing**

- **FR-010**: System MUST expose a webhook endpoint to receive Stripe events
- **FR-011**: System MUST validate webhook signatures using the Stripe webhook secret (stored in SSM Parameter Store at `/booking/{env}/stripe/webhook_secret`)
- **FR-012**: System MUST process `checkout.session.completed` events to confirm payments
- **FR-013**: System MUST process `charge.refunded` events to update refund status
- **FR-014**: System MUST be idempotent - processing the same webhook twice must not cause issues

**Refund Processing**

- **FR-015**: System MUST support full refunds via Stripe when cancellation policy allows
- **FR-016**: System MUST support partial refunds (50%) via Stripe for 7-14 day cancellations
- **FR-017**: Refund amounts MUST be calculated in EUR cents
- **FR-018**: System MUST store refund transaction ID from Stripe

**Frontend Integration**

> **Note**: FR-019 through FR-021 are satisfied by Stripe Checkout's hosted payment page.
> The backend returns a `checkout_url`; the frontend simply redirects to it.
> No custom payment UI code is required in this feature scope.

- **FR-019**: Frontend MUST redirect users to Stripe Checkout for payment *(satisfied by Stripe Checkout redirect)*
- **FR-020**: Frontend MUST handle success and cancel return URLs *(satisfied by Stripe Checkout return URLs)*
- **FR-021**: System MUST display appropriate messages based on payment outcome *(satisfied by existing reservation status display)*
- **FR-022**: System MUST NOT store or transmit raw card data (PCI compliance via Stripe)

**Error Handling**

- **FR-023**: System MUST handle Stripe API errors gracefully with user-friendly messages
- **FR-024**: System MUST log all payment errors with Stripe error codes for debugging
- **FR-025**: System MUST allow payment retry after failure (up to 3 attempts)
- **FR-026**: System MUST not confirm reservations if payment fails

**Backend API Endpoints**

- **FR-027**: POST `/payments/checkout-session` endpoint MUST create a Stripe Checkout session and return the session URL
- **FR-028**: GET `/payments/{reservation_id}/status` endpoint MUST return current payment status including Stripe transaction ID
- **FR-029**: POST `/payments/{reservation_id}/retry` endpoint MUST create a new Stripe session for failed payments
- **FR-030**: POST `/payments/{payment_id}/refund` endpoint MUST initiate refunds via Stripe API

**Out of Scope**

- Agent tool implementations (`@tool` decorators) - handled in a separate feature
- Agent conversation flows for payment
- Agent prompts related to payment

### Key Entities

- **Payment**: Enhanced to include Stripe-specific fields: `stripe_payment_intent_id`, `stripe_checkout_session_id`, `stripe_refund_id`. Provider changes from "mock" to "stripe".

- **StripeWebhookEvent**: Log of received webhook events. Contains event_id, event_type, processed_at, payload_hash (for deduplication).

- **PaymentSession**: Transient Stripe Checkout session. Contains session_id, reservation_id, amount_cents, expires_at, status (pending/completed/expired).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 95% of payment attempts complete successfully on first try (measured via payment success rate)
- **SC-002**: Guests can complete payment in under 2 minutes from clicking "pay" to confirmation
- **SC-003**: All successful Stripe payments result in confirmed reservations within 10 seconds
- **SC-004**: Refunds are processed and reflected in guest's account within 5-10 business days (Stripe standard)
- **SC-005**: Zero double-charges occur (idempotency verification)
- **SC-006**: System handles 50 concurrent payment sessions without degradation (p99 response time < 3 seconds, error rate < 1%)
- **SC-007**: Webhook processing completes within 5 seconds of receipt
- **SC-008**: 100% of refund requests within policy are processed successfully

## Assumptions

- Stripe sandbox credentials provided by user are valid and active
- All payments are in EUR (single currency)
- Stripe Checkout is the payment method (not Stripe Elements for inline forms in MVP)
- Webhook endpoint will be publicly accessible (via API Gateway)
- AWS SSM Parameter Store is available for storing Stripe API keys (SecureString type)
- Cancellation policy follows existing spec: full refund 14+ days, 50% refund 7-14 days, no refund under 7 days
- 3D Secure authentication is handled by Stripe Checkout (no additional implementation required)

## Clarifications

### Session 2026-01-03

- Q: Should we use Stripe Checkout or Stripe Elements? -> A: **Stripe Checkout**. Provides hosted payment page, handles 3DS automatically, reduces PCI scope, faster to implement. Stripe Elements can be added later for inline forms if needed.
- Q: How should Stripe API keys be stored? -> A: **AWS SSM Parameter Store** (SecureString). Parameter paths: `/booking/{env}/stripe/publishable_key` and `/booking/{env}/stripe/secret_key`. Lambda functions retrieve at runtime via SSM GetParameter API.
- Q: Should webhook endpoint require authentication? -> A: **Stripe signature validation only**. Webhook endpoint is public but validates Stripe signatures to ensure authenticity. No additional auth needed.
- Q: What happens to held availability if payment never completes? -> A: **24-hour hold**. Reservation holds availability for 24 hours. After 24 hours without payment, reservation expires and availability is released. Cron/EventBridge rule to clean up.
- Q: Is the agent in scope for this feature? -> A: **No, agent is out of scope**. This feature focuses on backend API endpoints and payment infrastructure only. Agent tools (`@tool` decorators) and agent conversation flows will be handled in a separate feature.
- Q: Where should the Stripe webhook secret be stored? -> A: **SSM Parameter Store** at `/booking/{env}/stripe/webhook_secret`, consistent with API key storage.
