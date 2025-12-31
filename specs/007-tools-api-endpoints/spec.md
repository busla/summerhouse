# Feature Specification: Tools REST API Endpoints

**Feature Branch**: `007-tools-api-endpoints`
**Created**: 2025-12-31
**Status**: Draft
**Input**: User description: "Research the backend/agent Strands tools, and implement them as FastAPI endpoints in backend/api. Do not modify the agent code, only implement the tools functionality as API resources"

## Overview

Expose the business logic from existing Strands agent tools as REST API endpoints in the FastAPI application (`backend/api`). This enables direct API access for frontend applications, third-party integrations, and administrative tooling without requiring agent conversation context.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Check Property Availability (Priority: P1)

A prospective guest wants to check if the property is available for their desired dates before starting a booking conversation. The frontend application calls the availability API directly to show available dates on a calendar interface.

**Why this priority**: Core booking functionality - guests cannot proceed with reservations without knowing availability. This is the most frequently used operation.

**Independent Test**: Can be fully tested by calling GET /api/availability with check-in and check-out dates and receiving availability status with pricing estimate.

**Acceptance Scenarios**:

1. **Given** a guest viewing the booking page, **When** they submit check-in and check-out dates for an available period, **Then** they receive confirmation of availability with estimated total price
2. **Given** a guest viewing the booking page, **When** they submit dates that overlap with existing bookings, **Then** they receive a list of unavailable dates and suggested alternative periods
3. **Given** a guest viewing the booking page, **When** they request a monthly calendar view, **Then** they receive categorized dates (available, booked, blocked, past)

---

### User Story 2 - View Pricing and Rates (Priority: P1)

A prospective guest wants to understand the pricing structure before committing to a booking. The frontend displays seasonal rates, calculates totals, and shows minimum stay requirements.

**Why this priority**: Essential for booking decisions - guests need transparent pricing to make informed choices.

**Independent Test**: Can be fully tested by calling GET /api/pricing endpoints and receiving seasonal rates with accurate calculations.

**Acceptance Scenarios**:

1. **Given** a guest on the pricing page, **When** they request pricing for specific dates, **Then** they receive nightly rate, cleaning fee, subtotal, and total with seasonal context
2. **Given** a guest exploring booking options, **When** they request all seasonal rates, **Then** they receive complete rate schedule with date ranges and minimum night requirements
3. **Given** a guest selecting dates, **When** their stay is shorter than the seasonal minimum, **Then** they receive clear error with minimum nights required and suggested checkout date

---

### User Story 3 - Manage Reservations (Priority: P1)

An authenticated guest wants to create, modify, view, or cancel their reservations directly through the API without agent interaction.

**Why this priority**: Core transactional functionality - allows guests to manage their bookings independently.

**Independent Test**: Can be fully tested by authenticating, creating a reservation, viewing it, modifying dates, and canceling - each operation independent.

**Acceptance Scenarios**:

1. **Given** an authenticated guest with valid dates, **When** they submit a reservation request, **Then** a reservation is created with unique ID and dates are marked as booked
2. **Given** an authenticated guest with an existing reservation, **When** they request to change dates to available period, **Then** reservation is updated with new pricing calculated
3. **Given** an authenticated guest, **When** they cancel a reservation, **Then** dates are released and refund amount calculated based on cancellation policy
4. **Given** an authenticated guest, **When** they request their reservations, **Then** they receive all their booking history with status

---

### User Story 4 - Process Payments (Priority: P2)

A guest with a pending reservation wants to complete payment through the API. The system processes payment (mock in MVP) and confirms the reservation.

**Why this priority**: Required for reservation confirmation but depends on reservation creation (P1).

**Independent Test**: Can be fully tested by creating a reservation then calling payment endpoint to see status change from PENDING to CONFIRMED.

**Acceptance Scenarios**:

1. **Given** a guest with a pending reservation, **When** they submit payment with valid method, **Then** payment is processed and reservation status changes to confirmed
2. **Given** a guest checking payment status, **When** they query with reservation ID, **Then** they receive payment status with transaction details if paid
3. **Given** a guest with a failed payment, **When** they retry with a different method, **Then** payment is reprocessed and updated accordingly

---

### User Story 5 - Guest Verification (Priority: P2)

A new guest wants to verify their email to create an account before making a reservation. The system sends verification codes and creates/updates guest profiles.

**Why this priority**: Required for authenticated operations but can use existing Cognito OAuth2 flow as alternative.

**Independent Test**: Can be fully tested by initiating verification, receiving code, and verifying to create guest profile.

**Acceptance Scenarios**:

1. **Given** a new guest starting verification, **When** they submit their email, **Then** they receive a verification code (mocked to console in dev)
2. **Given** a guest with verification code, **When** they submit correct code within 10 minutes, **Then** guest record is created/updated and they receive guest_id
3. **Given** an existing guest, **When** they look up their profile by email, **Then** they receive their profile information
4. **Given** a verified guest, **When** they update their profile, **Then** their name/phone/language preferences are saved

---

### User Story 6 - Property Information (Priority: P2)

A prospective guest wants to learn about the property details, amenities, and view photos before booking.

**Why this priority**: Supports booking decisions but not transactional - informational only.

**Independent Test**: Can be fully tested by calling property endpoints and receiving complete property details and photos.

**Acceptance Scenarios**:

1. **Given** a guest on property page, **When** they request property details, **Then** they receive complete property information including amenities, rules, and highlights
2. **Given** a guest browsing photos, **When** they request photos with optional category filter, **Then** they receive photo URLs with captions organized by category

---

### User Story 7 - Local Area Information (Priority: P3)

A guest wants to explore local attractions, restaurants, and activities near the property.

**Why this priority**: Value-add feature for guest experience but not essential for booking.

**Independent Test**: Can be fully tested by calling area info endpoints and receiving local recommendations.

**Acceptance Scenarios**:

1. **Given** a guest exploring the area, **When** they request area information, **Then** they receive categorized local places sorted by distance
2. **Given** a guest with specific interests, **When** they request personalized recommendations, **Then** they receive filtered suggestions matching their preferences

---

### Edge Cases

- What happens when dates span across seasonal boundaries (different rates per night)?
- How does system handle concurrent booking attempts for same dates?
- What happens when verification code expires mid-submission?
- How does system handle payment for already-paid reservations?
- What happens when modifying reservation to dates already booked by same guest?
- How does system handle timezone differences for date calculations?

## Requirements *(mandatory)*

### Functional Requirements

**Availability**
- **FR-001**: System MUST provide endpoint to check availability for date range
- **FR-002**: System MUST provide endpoint to get monthly calendar view with date categorization
- **FR-003**: System MUST suggest alternative available dates when requested dates are unavailable

**Pricing**
- **FR-004**: System MUST provide endpoint to get detailed pricing for date range
- **FR-005**: System MUST provide endpoint to calculate total cost with optional breakdown
- **FR-006**: System MUST provide endpoint to retrieve all seasonal rates
- **FR-007**: System MUST provide endpoint to validate minimum stay requirements
- **FR-008**: System MUST provide endpoint to get minimum stay info for specific date

**Reservations (Protected)**
- **FR-009**: System MUST provide authenticated endpoint to create reservations with double-booking prevention
- **FR-010**: System MUST provide authenticated endpoint to modify existing reservations
- **FR-011**: System MUST provide authenticated endpoint to cancel reservations with refund calculation
- **FR-012**: System MUST provide authenticated endpoint to list user's reservations
- **FR-013**: System MUST provide public endpoint to view single reservation by ID

**Payments**
- **FR-014**: System MUST provide endpoint to process payment for reservation
- **FR-015**: System MUST provide endpoint to check payment status
- **FR-016**: System MUST provide endpoint to retry failed payments

**Guest Verification**
- **FR-017**: System MUST provide endpoint to initiate email verification
- **FR-018**: System MUST provide endpoint to verify code and create/update guest
- **FR-019**: System MUST provide endpoint to get guest profile by email
- **FR-020**: System MUST provide endpoint to update guest profile

**Property Information**
- **FR-021**: System MUST provide endpoint to get property details
- **FR-022**: System MUST provide endpoint to get property photos with optional category filter

**Area Information**
- **FR-023**: System MUST provide endpoint to get local area information with optional category filter
- **FR-024**: System MUST provide endpoint to get personalized recommendations based on interests

**Cross-Cutting**
- **FR-025**: Protected endpoints MUST require valid JWT authentication via API Gateway
- **FR-026**: All endpoints MUST return consistent error format using ToolError structure
- **FR-027**: All endpoints MUST use shared services (DynamoDB singleton) for data access
- **FR-028**: All endpoints MUST validate input parameters and return appropriate error codes

**API Documentation Quality**
- **FR-029**: All route descriptions MUST be written for agent consumption (clear, unambiguous, action-oriented)
- **FR-030**: All endpoints MUST include OpenAPI request/response examples for Swagger UI
- **FR-031**: Route docstrings MUST describe parameters, return types, and error conditions explicitly
- **FR-032**: Endpoint summaries MUST use consistent verb-noun format (e.g., "Check availability for date range")

### Key Entities

- **Availability**: Date-based availability status (available, booked, blocked)
- **Pricing**: Seasonal rates with date ranges, nightly rates, and minimum stays
- **Reservation**: Booking record linking guest to dates with payment status
- **Guest**: User profile with contact info and verification status
- **Payment**: Transaction record with amount, method, and status
- **Property**: Property details with amenities, rules, and photos
- **AreaInfo**: Local attractions with categories, distances, and recommendations

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 21 tool functionalities are exposed as REST endpoints with equivalent behavior
- **SC-002**: API response times under 500ms for availability and pricing queries (cached data)
- **SC-003**: API response times under 1000ms for reservation operations (database writes)
- **SC-004**: Protected endpoints correctly reject unauthenticated requests with 401 status
- **SC-005**: All endpoints return standardized error responses matching ToolError format
- **SC-006**: Frontend can perform complete booking flow using only REST APIs (no agent required)
- **SC-007**: Concurrent availability checks handle 100 simultaneous requests without errors
- **SC-008**: Double-booking prevention works correctly under concurrent reservation attempts

## Assumptions

- Agent tools are POC code for reference only; API implementation will be rewritten following FastAPI best practices
- API Gateway JWT authorizer is already configured for protected routes
- DynamoDB tables and indexes are already provisioned
- Property and area info JSON data files exist and are valid
- Payment processing remains mocked (as in current tools)
- OAuth2 authentication flow via AgentCore Identity is available for protected endpoints
- Existing shared services (`shared/services/`) and models (`shared/models/`) can be reused or refactored as needed for REST API best practices
- DynamoDB table schemas can be modified if needed for optimal REST API access patterns

## Out of Scope

- Modifying the agent package (`backend/agent`) in any way
- Creating new business logic not present in existing tools
- Real payment provider integration
- WebSocket or streaming endpoints
- Admin-only management endpoints
- Rate limiting (handled by API Gateway)
- Request logging/tracing (handled by middleware)
- Load testing and concurrency validation (SC-007, SC-008 are aspirational targets)
- AgentCore Gateway MCP integration (planned future feature)

## Future Considerations

- **AgentCore Gateway Integration**: The OpenAPI schema auto-generated by FastAPI (via `infrastructure/modules/gateway-v2`) will serve as an MCP target for AgentCore Gateway in a future feature. This drives the requirement for exceptional API documentation quality.

## Clarifications

### Session 2025-12-31
- Q: Should agent tools code be copied or rewritten? → A: Rewritten following FastAPI best practices (POC reference only)
- Q: API documentation requirements? → A: Agent-friendly descriptions with OpenAPI request examples for Swagger; future MCP target compatibility
- Q: Shared services refactoring scope? → A: IN SCOPE - shared services can be refactored for booking flow/REST API best practices
- Q: DynamoDB schema refactoring scope? → A: IN SCOPE - table schemas can be modified if needed for REST API patterns
- Q: Existing auth endpoints disposition? → A: REMOVE - `/auth/refresh` and `/auth/session/{session_id}` are unused (frontend uses Amplify for token refresh and calls AgentCore SDK directly for session binding)
- Q: OpenAPI contract management approach? → A: CODE-FIRST - OpenAPI spec is auto-generated from FastAPI app via `generate_openapi.py` script called by Terraform during apply; no manual `contracts/api.yaml` file needed
