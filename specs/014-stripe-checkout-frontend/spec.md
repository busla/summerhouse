# Feature Specification: Stripe Checkout Frontend Integration

**Feature Branch**: `014-stripe-checkout-frontend`
**Created**: 2026-01-04
**Status**: Draft
**Input**: User description: "Implement complete frontend checkout and payment flow with Stripe API integration and E2E Playwright tests"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Complete Payment via Stripe Checkout (Priority: P1)

A guest has filled out their booking details (dates, guest information) and is ready to pay. They click "Proceed to Payment" and are redirected to Stripe's hosted checkout page. After entering their card details on Stripe's secure page and completing payment, they are automatically redirected back to the booking platform and see a confirmation that their reservation is confirmed and paid.

**Why this priority**: This is the core payment experience. Without payment integration, reservations cannot be finalized and revenue cannot be collected. This unlocks the full booking funnel from inquiry to paid confirmation.

**Independent Test**: Can be fully tested by completing the booking form flow, clicking "Proceed to Payment", entering Stripe test card (4242 4242 4242 4242) on the Stripe Checkout page, and verifying return to a success page showing payment confirmation with reservation ID.

**Acceptance Scenarios**:

1. **Given** a guest has completed date selection and guest details, **When** they click "Proceed to Payment", **Then** the system creates a Stripe Checkout session and redirects them to Stripe's hosted payment page.

2. **Given** a guest is on the Stripe Checkout page, **When** they enter valid card details and submit payment, **Then** they are redirected to the booking platform's success page.

3. **Given** a guest has successfully paid via Stripe, **When** they arrive at the success page, **Then** they see confirmation with reservation ID, booking dates, total amount paid, and payment status "paid".

4. **Given** a guest completes payment, **When** they view the confirmation, **Then** the reservation status is "confirmed" (not "pending").

---

### User Story 2 - Handle Payment Cancellation (Priority: P2)

A guest decides not to complete their payment on the Stripe Checkout page. They click the back button or close the payment page. The system handles this gracefully, returning them to the booking flow where they can retry payment or modify their booking.

**Why this priority**: Payment abandonment is common (industry average ~70%). Graceful handling of cancellation prevents lost bookings and improves user experience by allowing retry.

**Independent Test**: Can be tested by initiating checkout, then clicking "Back" or closing the Stripe page, and verifying the user returns to the booking page with their details preserved and a clear option to retry.

**Acceptance Scenarios**:

1. **Given** a guest is on the Stripe Checkout page, **When** they click the back/cancel button, **Then** they are redirected to the booking platform's cancel return URL.

2. **Given** a guest returns from cancelled payment, **When** they view the booking page, **Then** their previously entered dates and guest details are still preserved.

3. **Given** a guest cancelled payment, **When** they view the booking page, **Then** they see a message explaining the payment was not completed and a "Try Again" button.

4. **Given** a guest cancelled payment, **When** they click "Try Again", **Then** a new checkout session is created (see US4 for retry mechanics and attempt limits).

---

### User Story 3 - Payment Status Display (Priority: P3)

A guest wants to check if their payment went through. They view their reservation details and see clear visual indication of the payment status (pending, paid, failed) with appropriate messaging for each state.

**Why this priority**: Payment visibility reduces support inquiries and builds trust. Guests need confidence their payment was processed correctly.

**Independent Test**: Can be tested by viewing reservations with different payment states and verifying correct status badges and messaging appear.

**Acceptance Scenarios**:

1. **Given** a guest has a paid reservation, **When** they view their booking confirmation, **Then** they see a "Paid" status badge with payment amount and confirmation details.

2. **Given** a guest has an unpaid/pending reservation, **When** they view their booking, **Then** they see a "Payment Required" status with a "Complete Payment" button.

3. **Given** a guest's payment failed, **When** they view their booking, **Then** they see a "Payment Failed" status with a "Retry Payment" button and guidance.

---

### User Story 4 - Payment Retry After Failure (Priority: P4)

A guest's card was declined or had insufficient funds. They want to try again with a different card without losing their reservation. The system allows multiple retry attempts with clear error messaging.

**Why this priority**: Payment failures happen; a smooth retry experience converts potentially lost bookings. Up to 3 retry attempts prevents abuse while allowing genuine retries.

**Independent Test**: Can be tested using Stripe test card for decline (4000000000000002), verifying error message appears, then retrying with valid test card and completing payment successfully.

**Acceptance Scenarios**:

1. **Given** a payment has failed, **When** the guest is returned to the booking platform, **Then** they see a clear error message explaining the failure (e.g., "Card declined").

2. **Given** a payment failed, **When** the guest clicks "Try Again", **Then** a new Stripe Checkout session is created and they can enter different card details.

3. **Given** a guest has made 3 failed payment attempts, **When** they try to pay again, **Then** they see a message to contact support or use alternative payment.

4. **Given** a payment failed but the guest retries successfully, **When** payment completes, **Then** the reservation is confirmed and shows paid status.

---

### Edge Cases

- What happens if user closes browser during Stripe payment? (Session expires after 30 minutes; return to booking page shows payment incomplete; can retry)
- What happens if Stripe redirects back but webhook hasn't processed yet? (Show "Processing..." state; **poll** `GET /payments/{reservation_id}/status` every 2s for up to 30s; confirm when status becomes 'paid')
- What happens with slow network on redirect back from Stripe? (Show loading state; retry API status check; graceful timeout message)
- What happens if user navigates away mid-checkout? (Form state persisted in sessionStorage; Stripe session remains valid for 30 minutes)
- What happens with 3D Secure authentication? (Stripe Checkout handles 3DS inline; no additional frontend implementation needed)
- What happens if user opens checkout in multiple tabs? (Each tab creates separate session; only one can complete successfully via idempotency)
- What happens if reservation expires during payment? (Backend validates reservation is still valid before payment; shows error if expired)

## Requirements *(mandatory)*

### Functional Requirements

**Checkout Flow Integration**

- **FR-001**: System MUST add a "Payment" step between "Guest Details" and "Confirmation" in the booking flow
- **FR-002**: System MUST call `POST /payments/checkout-session` API when user clicks "Proceed to Payment"
- **FR-003**: System MUST redirect user to Stripe Checkout URL received from API response
- **FR-004**: System MUST preserve booking form state in sessionStorage during Stripe redirect
- **FR-005**: System MUST handle both success and cancel return URLs from Stripe Checkout

**Success Flow**

- **FR-006**: System MUST create a `/booking/success` route to handle successful payment returns
- **FR-007**: Success page MUST display reservation ID, booking dates, guest name, and total paid
- **FR-008**: Success page MUST show payment confirmation status (paid/confirmed)
- **FR-009**: Success page MUST clear persisted form state after displaying confirmation
- **FR-010**: System MUST call `GET /payments/{reservation_id}/status` to verify payment status

**Cancel/Failure Flow**

- **FR-011**: System MUST create a `/booking/cancel` route to handle payment cancellation returns
- **FR-012**: Cancel page MUST preserve form state and allow user to retry payment
- **FR-013**: System MUST display user-friendly error message explaining payment was not completed
- **FR-014**: System MUST provide clear "Try Again" option to create new checkout session

**Payment Status Display**

- **FR-015**: System MUST display payment status badge (Pending, Paid, Failed) on booking confirmation
- **FR-016**: System MUST conditionally show "Complete Payment" or "Retry Payment" buttons based on status
- **FR-017**: System MUST show payment amount and currency (EUR) on all payment-related UI

**Error Handling**

- **FR-018**: System MUST handle API errors gracefully with user-friendly error messages
- **FR-019**: System MUST handle Stripe redirect failures (show fallback message, provide retry option)
- **FR-020**: System MUST track retry count and enforce maximum of 3 payment attempts (frontend UX control; backend creates new sessions regardless—abuse prevention is out of scope for MVP)
- **FR-021**: System MUST display loading states during API calls and redirects

**E2E Testing Requirements**

- **FR-022**: System MUST include Playwright E2E tests for complete checkout flow using real Stripe test mode redirects
- **FR-023**: System MUST test success path: booking form → real Stripe Checkout page → success page
- **FR-024**: System MUST test cancel path: booking form → cancel return → retry option
- **FR-025**: System MUST test error handling: API failure → error display → recovery options
- **FR-026**: E2E tests MUST use Stripe test card numbers (e.g., 4242424242424242) on actual Stripe test pages

**Out of Scope**

- Backend payment API implementation (already completed in 013-stripe-payment)
- Agent/chatbot payment flows (separate feature)
- Refund UI (view-only for MVP; admin manages refunds)
- Inline card input (Stripe Elements) - using hosted Checkout only
- Payment method management/saved cards
- Invoice/receipt PDF generation

### Key Entities

- **CheckoutSession**: Transient object containing `checkout_url` (Stripe hosted page URL), `session_id`, `reservation_id`, `expires_at`. Frontend redirects user to `checkout_url`.

- **PaymentStatus**: Display state for frontend: "pending" (awaiting payment), "processing" (redirect complete, verifying), "paid" (confirmed), "failed" (declined or error).

- **BookingFormState**: Enhanced to include `paymentAttempts` (number), `lastPaymentError` (string or null), and `stripeSessionId` (stored before redirect; used on success page to validate the returning session_id matches the initiated checkout).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can complete the full booking-to-payment flow in under 4 minutes (measured: E2E test timing from `/book` page load to `/booking/success` confirmation visible)
- **SC-002**: 95% of users who reach the payment step successfully redirect to Stripe Checkout (measured: post-MVP analytics; for MVP, validated by E2E test success rate)
- **SC-003**: 90% of users who abandon payment can successfully return and retry (measured: E2E test validates form state restoration; production metrics post-MVP)
- **SC-004**: All E2E Playwright tests pass: success flow, cancel flow, error handling, retry flow
- **SC-005**: Zero console errors during normal checkout flow (measured via Playwright test assertions)
- **SC-006**: Payment status is correctly displayed within 5 seconds of returning from Stripe
- **SC-007**: Mobile users can complete payment flow (responsive design works on 375px viewport)
- **SC-008**: Users with 3+ failed attempts see appropriate messaging (prevents infinite retry loops)

## Assumptions

- Backend payment APIs from 013-stripe-payment are deployed and functional
- Stripe test mode is configured in backend (pk_test, sk_test keys)
- Existing booking flow (DateRangePicker, GuestDetailsForm) remains unchanged
- sessionStorage is available in all target browsers (modern browsers)
- API returns checkout_url that can be directly used for redirect
- Frontend environment variables include API base URL
- Stripe Checkout handles 3D Secure automatically (no frontend implementation needed)
- EUR is the only supported currency (matching backend)
- Users are authenticated via existing Cognito flow before reaching payment (if session expires mid-payment, existing auth middleware redirects to login; form state in sessionStorage survives for retry after re-auth)

## Dependencies

- **013-stripe-payment**: Backend payment endpoints (POST /payments/checkout-session, GET /payments/{reservation_id}/status, POST /payments/{reservation_id}/retry)
- **Existing booking flow**: /book page with DateRangePicker, GuestDetailsForm components
- **Existing API client**: Generated TypeScript client from OpenAPI spec
- **Playwright**: Already configured in frontend/tests/e2e/

## Clarifications

### Session 2026-01-04

- Q: Should E2E tests use mocked Stripe responses or real Stripe test mode redirects? → A: Real Stripe test mode - actually redirect to Stripe test pages with test cards for true end-to-end validation
