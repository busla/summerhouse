# Tasks: Tools REST API Endpoints

**Input**: Design documents from `/specs/007-tools-api-endpoints/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), data-model.md, quickstart.md, research.md

**Tests**: Tests are REQUIRED per Constitution Principle I (Test-First Development - NON-NEGOTIABLE).

**Organization**: Tasks grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and API structure

- [ ] T001 Create routes package structure at `backend/api/src/api/routes/__init__.py`
- [ ] T002 [P] Create API models directory at `backend/api/src/api/models/__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T003 Create dependencies module with service factory functions at `backend/api/src/api/dependencies.py`
- [ ] T004 [P] Create exception handlers with ErrorCode-to-HTTP mapping at `backend/api/src/api/exceptions.py`
- [ ] T005 Register exception handlers in FastAPI app at `backend/api/src/api/main.py`
- [ ] T006 Create shared request/response models at `backend/api/src/api/models/common.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Check Property Availability (Priority: P1) 🎯 MVP

**Goal**: Enable guests to check date availability and view calendar before booking

**Independent Test**: Call `GET /api/availability` with dates, receive availability status with pricing estimate

### Implementation for User Story 1

- [ ] T007 [P] [US1] Create `CalendarDay` and `CalendarResponse` models at `backend/api/src/api/models/availability.py`
- [ ] T007a [US1] Write unit tests for availability endpoints at `backend/tests/unit/api/test_availability_routes.py`
- [ ] T008 [US1] Implement `GET /api/availability` endpoint at `backend/api/src/api/routes/availability.py`
- [ ] T008b [US1] Add `suggested_alternatives` field to AvailabilityResponse and implement alternative date suggestion logic (FR-003) at `backend/shared/src/shared/models/availability.py` and `backend/shared/src/shared/services/availability.py`
- [ ] T009 [US1] Implement `GET /api/availability/calendar/{month}` endpoint at `backend/api/src/api/routes/availability.py`
- [ ] T010 [US1] Register availability router in `backend/api/src/api/routes/__init__.py`

**Checkpoint**: Availability endpoints functional - guests can check dates and view calendar

---

## Phase 4: User Story 2 - View Pricing and Rates (Priority: P1) 🎯 MVP

**Goal**: Display transparent pricing with seasonal rates, totals, and minimum stay requirements

**Independent Test**: Call `GET /api/pricing/calculate` with dates, receive detailed pricing breakdown

### Implementation for User Story 2

- [ ] T011 [P] [US2] Create pricing response models (`BasePricingResponse`, `SeasonalRatesResponse`, `MinimumStayCheckResponse`, `MinimumStayInfoResponse`) at `backend/api/src/api/models/pricing.py`
- [ ] T011a [US2] Write unit tests for pricing endpoints at `backend/tests/unit/api/test_pricing_routes.py`
- [ ] T012 [US2] Implement `GET /api/pricing` endpoint at `backend/api/src/api/routes/pricing.py`
- [ ] T013 [US2] Implement `GET /api/pricing/calculate` endpoint at `backend/api/src/api/routes/pricing.py`
- [ ] T014 [US2] Implement `GET /api/pricing/rates` endpoint at `backend/api/src/api/routes/pricing.py`
- [ ] T015 [US2] Implement `GET /api/pricing/minimum-stay` endpoint at `backend/api/src/api/routes/pricing.py`
- [ ] T016 [US2] Implement `GET /api/pricing/minimum-stay/{date}` endpoint at `backend/api/src/api/routes/pricing.py`
- [ ] T017 [US2] Register pricing router in `backend/api/src/api/routes/__init__.py`

**Checkpoint**: Pricing endpoints functional - guests can see rates and calculate totals

---

## Phase 5: User Story 3 - Manage Reservations (Priority: P1) 🎯 MVP

**Goal**: Enable authenticated guests to create, modify, view, and cancel reservations

**Independent Test**: Authenticate, create reservation via `POST /api/reservations`, verify via `GET /api/reservations/{id}`

### Implementation for User Story 3

- [ ] T018 [P] [US3] Create reservation request/response models (`ReservationCreateRequest`, `ReservationModifyRequest`, `ReservationListResponse`, `CancellationResponse`) at `backend/api/src/api/models/reservations.py`
- [ ] T018a [US3] Write unit tests for reservation endpoints at `backend/tests/unit/api/test_reservations_routes.py`
- [ ] T019 [US3] Implement `POST /api/reservations` endpoint (JWT protected) at `backend/api/src/api/routes/reservations.py`
- [ ] T020 [US3] Implement `GET /api/reservations/{id}` endpoint (public) at `backend/api/src/api/routes/reservations.py`
- [ ] T021 [US3] Implement `GET /api/reservations` endpoint (JWT protected, user's reservations) at `backend/api/src/api/routes/reservations.py`
- [ ] T022 [US3] Implement `PATCH /api/reservations/{id}` endpoint (JWT protected) at `backend/api/src/api/routes/reservations.py`
- [ ] T023 [US3] Implement `DELETE /api/reservations/{id}` endpoint (JWT protected) at `backend/api/src/api/routes/reservations.py`
- [ ] T024 [US3] Register reservations router in `backend/api/src/api/routes/__init__.py`

**Checkpoint**: Reservation management complete - full booking lifecycle available

---

## Phase 6: User Story 4 - Process Payments (Priority: P2)

**Goal**: Enable guests to complete payment for pending reservations

**Independent Test**: Create reservation, call `POST /api/payments`, verify status changes to CONFIRMED

### Implementation for User Story 4

- [ ] T025 [P] [US4] Create payment request models (`PaymentRequest`, `PaymentRetryRequest`) at `backend/api/src/api/models/payments.py`
- [ ] T025a [US4] Write unit tests for payment endpoints at `backend/tests/unit/api/test_payments_routes.py`
- [ ] T026 [US4] Implement `POST /api/payments` endpoint (JWT protected) at `backend/api/src/api/routes/payments.py`
- [ ] T027 [US4] Implement `GET /api/payments/{reservation_id}` endpoint (public) at `backend/api/src/api/routes/payments.py`
- [ ] T028 [US4] Implement `POST /api/payments/{reservation_id}/retry` endpoint (JWT protected) at `backend/api/src/api/routes/payments.py`
- [ ] T029 [US4] Register payments router in `backend/api/src/api/routes/__init__.py`

**Checkpoint**: Payment flow functional - reservations can be paid and confirmed

---

## Phase 7: User Story 5 - Guest Verification (Priority: P2)

**Goal**: Enable new guests to verify email and create accounts before booking

**Independent Test**: Call `POST /api/guests/verify` with email, then `POST /api/guests/verify/confirm` with code

### Implementation for User Story 5

- [ ] T030 [P] [US5] Create guest verification response model (`VerificationInitiatedResponse`) at `backend/api/src/api/models/guests.py`
- [ ] T030a [US5] Write unit tests for guest endpoints at `backend/tests/unit/api/test_guests_routes.py`
- [ ] T031 [US5] Implement `POST /api/guests/verify` endpoint (public) at `backend/api/src/api/routes/guests.py`
- [ ] T032 [US5] Implement `POST /api/guests/verify/confirm` endpoint (public) at `backend/api/src/api/routes/guests.py`
- [ ] T033 [US5] Implement `GET /api/guests/{email}` endpoint (JWT protected) at `backend/api/src/api/routes/guests.py`
- [ ] T034 [US5] Implement `PATCH /api/guests/{guest_id}` endpoint (JWT protected) at `backend/api/src/api/routes/guests.py`
- [ ] T035 [US5] Register guests router in `backend/api/src/api/routes/__init__.py`

**Checkpoint**: Guest verification flow complete - users can verify and manage profiles

---

## Phase 8: User Story 6 - Property Information (Priority: P2)

**Goal**: Provide property details, amenities, and photos to prospective guests

**Independent Test**: Call `GET /api/property` and `GET /api/property/photos`, verify complete property info returned

### Implementation for User Story 6

- [ ] T036 [P] [US6] Write unit tests for property endpoints at `backend/tests/unit/api/test_property_routes.py`
- [ ] T036a [US6] Implement `GET /api/property` endpoint (public) at `backend/api/src/api/routes/property.py`
- [ ] T037 [US6] Implement `GET /api/property/photos` endpoint (public, optional category filter) at `backend/api/src/api/routes/property.py`
- [ ] T038 [US6] Register property router in `backend/api/src/api/routes/__init__.py`

**Checkpoint**: Property information accessible - guests can learn about the apartment

---

## Phase 9: User Story 7 - Local Area Information (Priority: P3)

**Goal**: Provide local area information and personalized recommendations

**Independent Test**: Call `GET /api/area` and `GET /api/area/recommendations`, verify local info returned

### Implementation for User Story 7

- [ ] T039 [P] [US7] Write unit tests for area endpoints at `backend/tests/unit/api/test_area_routes.py`
- [ ] T039a [US7] Implement `GET /api/area` endpoint (public, optional category filter) at `backend/api/src/api/routes/area.py`
- [ ] T040 [US7] Implement `GET /api/area/recommendations` endpoint (public, interest filter) at `backend/api/src/api/routes/area.py`
- [ ] T041 [US7] Register area router in `backend/api/src/api/routes/__init__.py`

**Checkpoint**: Area information complete - guests can explore local attractions

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Final cleanup and validation across all endpoints

- [ ] T042 Update contract test to verify all 21 endpoints in OpenAPI spec and add edge case tests (cross-season pricing, expired verification, duplicate payment, timezone handling) at `backend/tests/contract/test_openapi_schema.py`
- [ ] T043 Remove unused auth endpoints (`/auth/refresh`, `/auth/session/{session_id}`) from `backend/api/src/api/routes/`
- [ ] T044 [P] Verify OpenAPI generation script works with all endpoints via `uv run python -m api.scripts.generate_openapi`
- [ ] T044a Review all endpoint docstrings for FR-029 to FR-032 compliance (agent-friendly descriptions, OpenAPI examples, explicit params/returns, verb-noun format)
- [ ] T045 Run quickstart.md validation - test local development workflow

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phases 3-9)**: All depend on Foundational phase completion
  - User stories can proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Phase 10)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 - Availability (P1)**: Can start after Foundational - No dependencies on other stories
- **US2 - Pricing (P1)**: Can start after Foundational - No dependencies on other stories
- **US3 - Reservations (P1)**: Can start after Foundational - Uses availability/pricing services internally
- **US4 - Payments (P2)**: Can start after Foundational - Integrates with reservations (same DB)
- **US5 - Guests (P2)**: Can start after Foundational - Independent verification flow
- **US6 - Property (P2)**: Can start after Foundational - Reads static JSON data
- **US7 - Area Info (P3)**: Can start after Foundational - Reads static JSON data

### Within Each User Story

- Models before endpoints (if new models needed)
- Implement endpoints sequentially within route file
- Register router after all endpoints implemented
- Story complete before moving to next priority

### Parallel Opportunities

After Foundational phase completes:

```bash
# All model tasks can run in parallel:
T007 [US1] availability models
T011 [US2] pricing models
T018 [US3] reservation models
T025 [US4] payment models
T030 [US5] guest models

# Different stories can be worked on simultaneously:
Developer A: US1 (Availability) + US2 (Pricing)
Developer B: US3 (Reservations)
Developer C: US4-US7 (P2/P3 stories)
```

---

## Implementation Strategy

### MVP First (P1 Stories Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: US1 - Availability
4. Complete Phase 4: US2 - Pricing
5. Complete Phase 5: US3 - Reservations
6. **STOP and VALIDATE**: Test booking flow end-to-end
7. Deploy/demo MVP with 12 endpoints

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (Availability) → Test independently → 2 endpoints live
3. Add US2 (Pricing) → Test independently → 7 endpoints live
4. Add US3 (Reservations) → Test independently → 12 endpoints live (MVP!)
5. Add US4 (Payments) → 15 endpoints live
6. Add US5 (Guests) → 19 endpoints live
7. Add US6 (Property) → 21 endpoints live
8. Add US7 (Area Info) → 23 endpoints total? No, 21 - all complete

### Authentication Summary

| Story | Endpoints | Public | JWT Protected |
|-------|-----------|--------|---------------|
| US1 | 2 | 2 | 0 |
| US2 | 5 | 5 | 0 |
| US3 | 5 | 1 | 4 |
| US4 | 3 | 1 | 2 |
| US5 | 4 | 2 | 2 |
| US6 | 2 | 2 | 0 |
| US7 | 2 | 2 | 0 |
| **Total** | **21** | **15** | **8*** |

*Note: 8 JWT-protected endpoints as corrected in plan.md.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Services already exist in `shared/services/` - reuse via `dependencies.py`
- Models already exist in `shared/models/` - only create API-specific models
- OpenAPI spec is CODE-FIRST - auto-generated from FastAPI app
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
