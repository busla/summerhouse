# Implementation Plan: Tools REST API Endpoints

**Branch**: `007-tools-api-endpoints` | **Date**: 2025-12-31 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-tools-api-endpoints/spec.md`

## Summary

Expose 21 Strands agent tools as FastAPI REST endpoints, enabling direct API access for the frontend booking flow without requiring agent conversation context. The implementation will rewrite POC tool logic following FastAPI best practices, reuse existing Pydantic models and shared services, and integrate with API Gateway JWT authorization.

## Technical Context

**Language/Version**: Python 3.13+ (UV workspace)
**Primary Dependencies**: FastAPI 0.115+, Pydantic v2 (strict mode), boto3 (DynamoDB)
**Storage**: DynamoDB (6 existing tables: reservations, guests, availability, pricing, payments, verification-codes)
**Testing**: pytest with moto (AWS mocking)
**Target Platform**: AWS Lambda via Mangum adapter, API Gateway HTTP API
**Project Type**: Web application (backend API)
**Performance Goals**: <500ms for reads (availability, pricing), <1000ms for writes (reservations)
**Constraints**: 100 concurrent requests, API Gateway rate limits, DynamoDB provisioned capacity
**Scale/Scope**: Single property, ~1000 reservations/year, 7 categories of endpoints (21 total)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First Development | ✅ PASS | Tests will be written first for each endpoint; pytest + moto setup exists |
| II. Simplicity & YAGNI | ✅ PASS | Direct implementation from spec; no speculative features; reusing existing services |
| III. Type Safety | ✅ PASS | Pydantic v2 strict mode; existing models in `shared/models/` |
| IV. Observability | ✅ PASS | Structured logging via Python logging; correlation IDs via API Gateway |
| V. Incremental Delivery | ✅ PASS | Endpoints grouped by priority (P1→P2→P3); each independently deployable |
| VI. Technology Stack | ✅ PASS | FastAPI backend; no frontend changes; no agent modifications |
| VI.b UI Component Dev | N/A | Backend-only feature |

**Gate Status**: ✅ PASSED - All applicable principles satisfied

## Project Structure

### Documentation (this feature)

```text
specs/007-tools-api-endpoints/
├── plan.md              # This file
├── research.md          # Phase 0: FastAPI patterns, auth, error handling
├── data-model.md        # Phase 1: Request/response models per endpoint
├── quickstart.md        # Phase 1: Development and testing guide
└── tasks.md             # Phase 2: Implementation tasks (via /speckit.tasks)
```

**Note**: OpenAPI spec is CODE-FIRST - auto-generated from FastAPI app via `generate_openapi.py` script called by Terraform during apply. No manual `contracts/api.yaml` file.

### Source Code (repository root)

```text
backend/
├── api/                          # FastAPI package (MODIFIED)
│   ├── pyproject.toml
│   └── src/api/
│       ├── main.py               # App entry + /api prefix routing
│       ├── security.py           # JWT auth markers (existing)
│       └── routes/
│           ├── __init__.py
│           ├── health.py         # Existing health endpoints
│           ├── availability.py   # NEW: check_availability, get_calendar
│           ├── pricing.py        # NEW: get_pricing, calculate_total, etc.
│           ├── reservations.py   # NEW: create/modify/cancel/get reservations
│           ├── payments.py       # NEW: process/status/retry payments
│           ├── guests.py         # NEW: verification, profile management
│           ├── property.py       # NEW: property details, photos
│           └── area.py           # NEW: area info, recommendations
│
├── shared/                       # Shared package (MINIMAL CHANGES)
│   └── src/shared/
│       ├── models/               # Existing Pydantic models (reused)
│       │   ├── availability.py
│       │   ├── pricing.py
│       │   ├── reservation.py
│       │   ├── payment.py
│       │   ├── guest.py
│       │   ├── property.py
│       │   ├── area_info.py
│       │   └── errors.py         # ToolError format (reused)
│       ├── services/
│       │   └── dynamodb.py       # Singleton DynamoDB service (reused)
│       └── tools/                # POC reference only (NOT MODIFIED)
│
└── tests/
    ├── unit/
    │   └── api/
    │       ├── test_availability_routes.py   # NEW
    │       ├── test_pricing_routes.py        # NEW
    │       ├── test_reservations_routes.py   # NEW
    │       ├── test_payments_routes.py       # NEW
    │       ├── test_guests_routes.py         # NEW
    │       ├── test_property_routes.py       # NEW
    │       └── test_area_routes.py           # NEW
    └── contract/
        └── test_openapi_schema.py            # Updated for new endpoints
```

**Structure Decision**: Backend UV workspace structure preserved. New routes added under `api/src/api/routes/`. Shared models and services reused; tools package unchanged (POC reference only).

## Endpoint Mapping

### Category 1: Availability (P1)

| Tool Function | HTTP Method | Endpoint | Auth |
|--------------|-------------|----------|------|
| `check_availability` | GET | `/api/availability` | Public |
| `get_calendar` | GET | `/api/availability/calendar/{month}` | Public |

### Category 2: Pricing (P1)

| Tool Function | HTTP Method | Endpoint | Auth |
|--------------|-------------|----------|------|
| `get_pricing` | GET | `/api/pricing` | Public |
| `calculate_total` | GET | `/api/pricing/calculate` | Public |
| `get_seasonal_rates` | GET | `/api/pricing/rates` | Public |
| `check_minimum_stay` | GET | `/api/pricing/minimum-stay` | Public |
| `get_minimum_stay_info` | GET | `/api/pricing/minimum-stay/{date}` | Public |

### Category 3: Reservations (P1)

| Tool Function | HTTP Method | Endpoint | Auth |
|--------------|-------------|----------|------|
| `create_reservation` | POST | `/api/reservations` | JWT |
| `get_reservation` | GET | `/api/reservations/{id}` | Public |
| `get_my_reservations` | GET | `/api/reservations` | JWT |
| `modify_reservation` | PATCH | `/api/reservations/{id}` | JWT |
| `cancel_reservation` | DELETE | `/api/reservations/{id}` | JWT |

### Category 4: Payments (P2)

| Tool Function | HTTP Method | Endpoint | Auth |
|--------------|-------------|----------|------|
| `process_payment` | POST | `/api/payments` | JWT |
| `get_payment_status` | GET | `/api/payments/{reservation_id}` | Public |
| `retry_payment` | POST | `/api/payments/{reservation_id}/retry` | JWT |

### Category 5: Guests (P2)

| Tool Function | HTTP Method | Endpoint | Auth |
|--------------|-------------|----------|------|
| `initiate_verification` | POST | `/api/guests/verify` | Public |
| `verify_code` | POST | `/api/guests/verify/confirm` | Public |
| `get_guest_info` | GET | `/api/guests/{email}` | JWT |
| `update_guest_details` | PATCH | `/api/guests/{guest_id}` | JWT |

### Category 6: Property (P2)

| Tool Function | HTTP Method | Endpoint | Auth |
|--------------|-------------|----------|------|
| `get_property_details` | GET | `/api/property` | Public |
| `get_photos` | GET | `/api/property/photos` | Public |

### Category 7: Area Info (P3)

| Tool Function | HTTP Method | Endpoint | Auth |
|--------------|-------------|----------|------|
| `get_area_info` | GET | `/api/area` | Public |
| `get_recommendations` | GET | `/api/area/recommendations` | Public |

**Total**: 21 endpoints (13 public, 8 JWT-protected)

## Complexity Tracking

> No constitution violations to justify.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | - | - |
