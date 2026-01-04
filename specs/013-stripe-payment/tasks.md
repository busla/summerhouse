# Tasks: Stripe Payment Integration

**Input**: Design documents from `/specs/013-stripe-payment/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Tests included as per TDD constitution principle (Principle I: Test-First Development)

**Organization**: Tasks grouped by user story for independent implementation and testing

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Exact file paths included in descriptions

---

## Phase 1: Setup

**Purpose**: Dependencies and project structure verification

- [X] T001 Add `stripe>=8.0.0` to `backend/api/pyproject.toml` dependencies
- [X] T002 [P] Verify existing SSM permissions structure in `infrastructure/modules/gateway-v2/main.tf` (confirms infrastructure pattern; T008 will add Stripe-specific paths)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Models

- [X] T003 [P] Extend `Payment` model with Stripe fields in `backend/shared/src/shared/models/payment.py` (add `stripe_checkout_session_id`, `stripe_payment_intent_id`, `stripe_refund_id`, `refund_amount`, `refunded_at`)
- [X] T004 [P] Create `StripeWebhookEvent` model in `backend/shared/src/shared/models/stripe_webhook.py` (fields: `event_id`, `event_type`, `processed_at`, `payload_hash`, `reservation_id`, `payment_id`, `processing_result`, `error_message`)
- [X] T005 [P] Create API request/response models in `backend/api/src/api/models/payments.py` (`CheckoutSessionRequest`, `CheckoutSessionResponse`, `RefundRequest`, `RefundResponse`, `PaymentStatusResponse`)

### Services

- [X] T006 Create `SSMService` in `backend/shared/src/shared/services/ssm_service.py` with `get_parameter()` method for SecureString retrieval and caching
- [X] T007 Create `StripeService` in `backend/shared/src/shared/services/stripe_service.py` with `StripeClient` initialization from SSM credentials

### Infrastructure

- [X] T008 Add SSM read permissions to Lambda execution role in `infrastructure/modules/gateway-v2/main.tf` for paths `/booking/{env}/stripe/*`
- [X] T009 [P] Create DynamoDB table `booking-{env}-stripe-webhook-events` in infrastructure (PK: `event_id`, GSI: `event_type-index`, TTL: 90 days)

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Complete Booking Payment (Priority: P1) 🎯 MVP

**Goal**: Enable guests to pay for reservations via Stripe Checkout and have bookings confirmed automatically

**Independent Test**: Create reservation → initiate checkout → complete payment with test card 4242424242424242 → verify reservation status changes to "confirmed" with stored payment record

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T010 [P] [US1] Contract test for POST `/payments/checkout-session` in `backend/tests/contract/test_checkout_session_contract.py`
- [X] T011 [P] [US1] Contract test for POST `/webhooks/stripe` in `backend/tests/contract/test_webhook_contract.py`
- [X] T012 [P] [US1] Unit test for `StripeService.create_checkout_session()` in `backend/tests/unit/test_stripe_service.py`
- [X] T013 [P] [US1] Unit test for webhook signature validation in `backend/tests/unit/test_stripe_webhooks.py`
- [X] T014 [P] [US1] Unit test for `checkout.session.completed` event handling in `backend/tests/unit/test_stripe_webhooks.py`
- [X] T015 [US1] Integration test for complete payment flow in `backend/tests/integration/test_payment_flow.py` (include FR-026 negative test: verify failed payments do NOT confirm reservations)

### Implementation for User Story 1

- [X] T016 [US1] Implement `StripeService.create_checkout_session()` in `backend/shared/src/shared/services/stripe_service.py` (FR-001, FR-002, FR-003, FR-004)
- [X] T017 [US1] Add idempotency key handling based on `reservation_id` in `StripeService` (FR-004)
  > **Note**: T016 and T017 may be implemented together since idempotency is integral to session creation. Keep separate for tracking granularity.
- [X] T018 [US1] Create webhook handler route in `backend/api/src/api/routes/webhooks.py` with signature validation (FR-010, FR-011)
- [X] T019 [US1] Implement `checkout.session.completed` event processing (FR-012) - update reservation to "confirmed", create/update Payment record
- [X] T020 [US1] Create POST `/payments/checkout-session` endpoint in `backend/api/src/api/routes/payments.py` (FR-027)
- [X] T021 [US1] Add idempotent webhook event storage in DynamoDB (FR-014) using `event_id` as key
- [X] T022 [US1] Update `PaymentService.create_payment()` to handle Stripe provider with checkout session details
- [X] T023 [US1] Add structured logging with correlation IDs for payment operations

**Checkpoint**: User Story 1 complete - guests can make payments and reservations are confirmed

---

## Phase 4: User Story 2 - View Payment Status (Priority: P2)

**Goal**: Allow guests to check payment status for their reservations

**Independent Test**: Query payment status for reservations in various states (pending, completed, refunded) and verify correct response structure

### Tests for User Story 2

- [X] T024 [P] [US2] Contract test for GET `/payments/{reservation_id}/status` in `backend/tests/contract/test_payment_status_contract.py`
- [X] T025 [P] [US2] Unit test for `PaymentService.get_payment_status()` in `backend/tests/unit/test_payment_service.py`

### Implementation for User Story 2

- [X] T026 [US2] Implement `PaymentService.get_payment_status()` in `backend/shared/src/shared/services/payment_service.py`
- [X] T027 [US2] Create GET `/payments/{reservation_id}/status` endpoint in `backend/api/src/api/routes/payments.py` (FR-028)
- [X] T028 [US2] Return payment history including attempt count and refund details

**Checkpoint**: User Story 2 complete - guests can view payment status

---

## Phase 5: User Story 3 - Process Refunds (Priority: P3)

**Goal**: Process refunds via Stripe according to cancellation policy (full refund 14+ days, 50% 7-14 days, none <7 days)

**Independent Test**: Cancel a paid reservation 15 days before check-in → verify full refund processed in Stripe → verify payment record updated with refund details

### Tests for User Story 3

- [X] T029 [P] [US3] Contract test for POST `/payments/{payment_id}/refund` in `backend/tests/contract/test_refund_contract.py`
- [X] T030 [P] [US3] Unit test for `StripeService.create_refund()` in `backend/tests/unit/test_stripe_service.py`
- [X] T031 [P] [US3] Unit test for refund policy calculation (full, 50%, none) in `backend/tests/unit/test_refund_policy.py`
- [X] T032 [P] [US3] Unit test for `charge.refunded` webhook event handling in `backend/tests/unit/test_stripe_webhooks.py`

### Implementation for User Story 3

- [X] T033 [US3] Implement `RefundPolicyService.calculate_refund_amount()` in `backend/shared/src/shared/services/refund_policy_service.py` (FR-015, FR-016, FR-017)
- [X] T034 [US3] Implement `StripeService.create_refund()` in `backend/shared/src/shared/services/stripe_service.py` (FR-015, FR-016, FR-018)
- [X] T035 [US3] Create POST `/payments/{payment_id}/refund` endpoint in `backend/api/src/api/routes/payments.py` (FR-030)
- [X] T036 [US3] Implement `charge.refunded` webhook event processing (FR-013) - update Payment record with refund details
- [X] T037 [US3] Add authorization check: only reservation owner or admin can request refund

**Checkpoint**: User Story 3 complete - refunds process correctly per cancellation policy

---

## Phase 6: User Story 4 - Retry Failed Payment (Priority: P4)

**Goal**: Allow guests to retry payment after a failure without losing their reservation

**Independent Test**: Simulate failed payment with Stripe decline card → retry with valid test card → verify new checkout session created and payment succeeds

### Tests for User Story 4

- [X] T038 [P] [US4] Contract test for POST `/payments/{reservation_id}/retry` in `backend/tests/contract/test_payment_retry_contract.py`
- [X] T039 [P] [US4] Unit test for retry limit enforcement (max 3 attempts) in `backend/tests/unit/test_payment_retry.py`

### Implementation for User Story 4

- [X] T040 [US4] Implement retry attempt tracking in `PaymentService` (FR-025)
- [X] T041 [US4] Create POST `/payments/{reservation_id}/retry` endpoint in `backend/api/src/api/routes/payments.py` (FR-029)
- [X] T042 [US4] Validate retry constraints: max 3 attempts, reservation still in pending state, within 24-hour hold window
- [X] T043 [US4] Create new Stripe Checkout session for retry with incremented attempt number

**Checkpoint**: User Story 4 complete - guests can retry failed payments

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Error handling, documentation, and validation

- [X] T044 [P] Add Stripe-specific error codes to `backend/shared/src/shared/models/errors.py` (ERR_STRIPE, ERR_WEBHOOK)
- [X] T045 [P] Handle Stripe API errors gracefully with user-friendly messages (FR-023, FR-024)
- [X] T046 [P] Add retry logic for transient Stripe API failures
- [X] T047 Update OpenAPI spec with new payment endpoints
- [X] T048 Run `quickstart.md` validation to verify setup instructions
- [X] T049 Security review: verify webhook signature validation, SSM SecureString usage, no card data handling (FR-022)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies - can start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 - BLOCKS all user stories
- **Phase 3-6 (User Stories)**: All depend on Phase 2 completion
  - User stories can proceed in parallel (if staffed) or sequentially by priority
- **Phase 7 (Polish)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 - No dependencies on other stories
- **US2 (P2)**: Can start after Phase 2 - Uses Payment model from US1 but independently testable
- **US3 (P3)**: Can start after Phase 2 - Requires completed payment to refund (integration with US1)
- **US4 (P4)**: Can start after Phase 2 - Requires failed payment scenario (independent)

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD)
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

Tasks marked [P] within the same phase can run in parallel:

- **Phase 2**: T003, T004, T005 (models) can run in parallel
- **US1 Tests**: T010-T014 can run in parallel
- **US2 Tests**: T024, T025 can run in parallel
- **US3 Tests**: T029-T032 can run in parallel
- **US4 Tests**: T038, T039 can run in parallel
- **Phase 7**: T044-T046 can run in parallel

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test payment flow with Stripe test cards
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → Test independently → Deploy (MVP - payments work!)
3. Add US2 → Test independently → Deploy (status visibility)
4. Add US3 → Test independently → Deploy (refunds work!)
5. Add US4 → Test independently → Deploy (retry support)

---

## Stripe Test Cards

For testing during development:

| Scenario | Card Number | Expected Result |
|----------|-------------|-----------------|
| Success | 4242424242424242 | Payment succeeds |
| Decline | 4000000000000002 | Card declined |
| 3D Secure | 4000000000003220 | 3DS authentication required |
| Insufficient funds | 4000000000009995 | Insufficient funds error |

---

## Notes

- All amounts in EUR cents (e.g., €1,125.00 = 112500 cents)
- Webhook endpoint must be publicly accessible via API Gateway
- SSM parameters: `/booking/{env}/stripe/secret_key`, `/booking/{env}/stripe/publishable_key`, `/booking/{env}/stripe/webhook_secret`
- Agent tools are out of scope for this feature
- 3D Secure handled automatically by Stripe Checkout
