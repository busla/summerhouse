# Quickstart: Tools REST API Endpoints

**Phase**: 1 | **Date**: 2025-12-31 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Overview

This guide covers development, testing, and deployment of the 21 REST endpoints that expose Strands agent tool functionality. The endpoints use existing `shared/services/` business logic directly—POC tools (`shared/tools/`) are reference only.

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
- AWS credentials (for local DynamoDB testing with moto)

---

## Project Structure

```text
backend/
├── api/src/api/
│   ├── main.py              # FastAPI app + Mangum handler
│   ├── security.py          # JWT auth markers (existing)
│   ├── dependencies.py      # NEW: Service injection
│   ├── exceptions.py        # NEW: Error handlers
│   └── routes/
│       ├── __init__.py      # Router registration
│       ├── health.py        # Existing
│       ├── availability.py  # NEW: 2 endpoints
│       ├── pricing.py       # NEW: 5 endpoints
│       ├── reservations.py  # NEW: 5 endpoints
│       ├── payments.py      # NEW: 3 endpoints
│       ├── guests.py        # NEW: 4 endpoints
│       ├── property.py      # NEW: 2 endpoints
│       └── area.py          # NEW: 2 endpoints
│
├── shared/src/shared/
│   ├── models/              # Existing Pydantic models (reuse)
│   ├── services/            # Existing business logic (reuse)
│   └── tools/               # POC reference ONLY (don't modify)
│
└── tests/
    ├── conftest.py          # Fixtures, moto setup
    ├── unit/api/
    │   ├── test_availability_routes.py   # NEW
    │   ├── test_pricing_routes.py        # NEW
    │   └── ...                           # NEW
    └── contract/
        └── test_openapi_schema.py        # Update for 21 endpoints
```

---

## Development Workflow

### 1. Create Route Module (Test-First)

Start with failing tests:

```python
# tests/unit/api/test_availability_routes.py
"""Unit tests for availability endpoints."""

import pytest
from fastapi.testclient import TestClient
from moto import mock_aws


class TestCheckAvailability:
    """Tests for GET /api/availability."""

    @mock_aws
    def test_returns_availability_for_date_range(
        self,
        create_tables,  # From conftest.py
        sample_availability,
    ) -> None:
        """Returns availability status for requested dates."""
        from api.main import app

        client = TestClient(app)
        response = client.get(
            "/api/availability",
            params={
                "check_in": "2025-07-15",
                "check_out": "2025-07-22",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "is_available" in data
        assert "total_nights" in data
        assert "unavailable_dates" in data

    @mock_aws
    def test_returns_400_for_invalid_date_range(
        self,
        create_tables,
    ) -> None:
        """Returns 400 when check_out <= check_in."""
        from api.main import app

        client = TestClient(app)
        response = client.get(
            "/api/availability",
            params={
                "check_in": "2025-07-22",
                "check_out": "2025-07-15",  # Before check_in
            },
        )

        assert response.status_code == 400
```

### 2. Create Dependencies Module

```python
# api/src/api/dependencies.py
"""FastAPI dependencies for service injection."""

from functools import lru_cache

from shared.services.availability import AvailabilityService
from shared.services.booking import BookingService
from shared.services.dynamodb import get_dynamodb_service
from shared.services.payment_service import PaymentService
from shared.services.pricing import PricingService


@lru_cache
def get_pricing_service() -> PricingService:
    """Get singleton PricingService instance."""
    return PricingService(get_dynamodb_service())


@lru_cache
def get_availability_service() -> AvailabilityService:
    """Get singleton AvailabilityService instance."""
    return AvailabilityService(
        db=get_dynamodb_service(),
        pricing=get_pricing_service(),
    )


@lru_cache
def get_booking_service() -> BookingService:
    """Get singleton BookingService instance."""
    return BookingService(
        db=get_dynamodb_service(),
        availability=get_availability_service(),
        pricing=get_pricing_service(),
    )


@lru_cache
def get_payment_service() -> PaymentService:
    """Get singleton PaymentService instance."""
    return PaymentService(db=get_dynamodb_service())


def reset_dependencies() -> None:
    """Reset all cached dependencies (for testing)."""
    get_pricing_service.cache_clear()
    get_availability_service.cache_clear()
    get_booking_service.cache_clear()
    get_payment_service.cache_clear()
```

### 3. Create Exception Handlers

```python
# api/src/api/exceptions.py
"""Exception handlers for converting errors to HTTP responses."""

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from shared.models.errors import ErrorCode, ToolError


class BookingError(Exception):
    """Base exception for booking-related errors."""

    def __init__(self, error: ToolError) -> None:
        self.error = error


# Map error codes to HTTP status codes
ERROR_STATUS_MAP: dict[ErrorCode, int] = {
    ErrorCode.DATES_UNAVAILABLE: 409,       # Conflict
    ErrorCode.MINIMUM_NIGHTS_NOT_MET: 400,  # Bad Request
    ErrorCode.MAX_GUESTS_EXCEEDED: 400,     # Bad Request
    ErrorCode.VERIFICATION_REQUIRED: 401,   # Unauthorized
    ErrorCode.VERIFICATION_FAILED: 401,     # Unauthorized
    ErrorCode.RESERVATION_NOT_FOUND: 404,   # Not Found
    ErrorCode.UNAUTHORIZED: 403,            # Forbidden
    ErrorCode.PAYMENT_FAILED: 402,          # Payment Required
}


async def booking_error_handler(
    request: Request,
    exc: BookingError,
) -> JSONResponse:
    """Convert BookingError to JSON response with appropriate status."""
    status_code = ERROR_STATUS_MAP.get(exc.error.error_code, 400)
    return JSONResponse(
        status_code=status_code,
        content=exc.error.model_dump(),
    )
```

### 4. Create Route Module

```python
# api/src/api/routes/availability.py
"""Availability endpoints for checking date availability."""

from datetime import date

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_availability_service
from shared.models.availability import AvailabilityResponse
from shared.services.availability import AvailabilityService

router = APIRouter(tags=["availability"])


@router.get(
    "/availability",
    summary="Check date availability",
    description="""
    Check if specific dates are available for booking.

    Returns availability status, unavailable dates within range,
    and pricing breakdown. Use before creating a reservation.

    **Notes:**
    - Dates are in YYYY-MM-DD format
    - check_out is exclusive (last night is check_out - 1)
    - Amounts are in EUR cents
    """,
    response_description="Availability status with pricing breakdown",
    response_model=AvailabilityResponse,
)
async def check_availability(
    check_in: date = Query(
        ...,
        description="Check-in date (YYYY-MM-DD)",
        examples=["2025-07-15"],
    ),
    check_out: date = Query(
        ...,
        description="Check-out date (YYYY-MM-DD)",
        examples=["2025-07-22"],
    ),
    service: AvailabilityService = Depends(get_availability_service),
) -> AvailabilityResponse:
    """Check availability for date range."""
    return service.check_availability(check_in, check_out)
```

### 5. Register Router

```python
# api/src/api/routes/__init__.py
from fastapi import FastAPI

from api.routes.availability import router as availability_router
from api.routes.health import router as health_router
# ... other routers

app = FastAPI(
    title="Quesada Apartment Booking API",
    description="Agent-First Vacation Rental Booking Platform",
    version="1.0.0",
)

# Register all routers with /api prefix
app.include_router(health_router, prefix="/api")
app.include_router(availability_router, prefix="/api")
# ... other routers
```

### 6. Run Tests

```bash
# Run specific test file
task backend:test -- tests/unit/api/test_availability_routes.py -v

# Run all API tests
task backend:test -- tests/unit/api/ -v

# Run with coverage
task backend:test -- --cov=api --cov-report=term-missing
```

---

## Testing Patterns

### Moto DynamoDB Mocking

```python
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws


class TestMyEndpoint:
    @mock_aws
    def test_example(self, create_tables):
        """Test with mocked DynamoDB."""
        # create_tables fixture creates all 6 tables
        # reset_dynamodb_singleton (autouse) ensures fresh connection

        from api.main import app
        client = TestClient(app)

        response = client.get("/api/endpoint")
        assert response.status_code == 200
```

### JWT-Protected Endpoints

```python
class TestProtectedEndpoint:
    @mock_aws
    def test_requires_jwt_token(self, create_tables):
        """Returns 401 without JWT token."""
        from api.main import app
        client = TestClient(app)

        response = client.post("/api/reservations", json={...})
        # Note: In tests, API Gateway JWT validation is not present
        # Test the endpoint logic, not auth (auth tested separately)
```

### Error Response Testing

```python
def test_returns_tool_error_format(self, create_tables):
    """Error responses use ToolError format."""
    from api.main import app
    client = TestClient(app)

    response = client.get(
        "/api/reservations/INVALID-ID"
    )

    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["error_code"] == "ERR_006"
    assert "message" in data
    assert "recovery" in data
```

---

## Contract Testing

Update `tests/contract/test_openapi_schema.py` to verify all 21 endpoints:

```python
class TestToolsEndpointsExist:
    """Verify all 21 tools endpoints are present."""

    REQUIRED_ENDPOINTS = [
        # Availability (2)
        ("get", "/api/availability"),
        ("get", "/api/availability/calendar/{month}"),
        # Pricing (5)
        ("get", "/api/pricing"),
        ("get", "/api/pricing/calculate"),
        ("get", "/api/pricing/rates"),
        ("get", "/api/pricing/minimum-stay"),
        ("get", "/api/pricing/minimum-stay/{date}"),
        # Reservations (5)
        ("post", "/api/reservations"),
        ("get", "/api/reservations/{id}"),
        ("get", "/api/reservations"),
        ("patch", "/api/reservations/{id}"),
        ("delete", "/api/reservations/{id}"),
        # Payments (3)
        ("post", "/api/payments"),
        ("get", "/api/payments/{reservation_id}"),
        ("post", "/api/payments/{reservation_id}/retry"),
        # Guests (4)
        ("post", "/api/guests/verify"),
        ("post", "/api/guests/verify/confirm"),
        ("get", "/api/guests/{email}"),
        ("patch", "/api/guests/{guest_id}"),
        # Property (2)
        ("get", "/api/property"),
        ("get", "/api/property/photos"),
        # Area (2)
        ("get", "/api/area"),
        ("get", "/api/area/recommendations"),
    ]

    def test_all_endpoints_present(self, generated_openapi: dict) -> None:
        """All 21 tools endpoints must be in OpenAPI spec."""
        paths = generated_openapi["paths"]

        for method, path in self.REQUIRED_ENDPOINTS:
            assert path in paths, f"Missing path: {path}"
            assert method in paths[path], f"Missing {method.upper()} {path}"
```

---

## Local Development

### Running the API

```bash
# Start FastAPI dev server (port 3001)
task backend:dev

# Test endpoints
curl http://localhost:3001/api/health
curl "http://localhost:3001/api/availability?check_in=2025-07-15&check_out=2025-07-22"
```

### Using Swagger UI

Navigate to `http://localhost:3001/docs` for interactive API documentation.

### Seed Data

```bash
# Seed dev DynamoDB tables
task seed:dev
```

---

## Authentication Notes

### JWT Validation Flow

```
┌─────────────┐     ┌───────────────┐     ┌───────────┐
│   Client    │────▶│  API Gateway  │────▶│  Lambda   │
│             │     │  JWT Validate │     │  FastAPI  │
└─────────────┘     └───────────────┘     └───────────┘
     │                    │                     │
     │ Authorization:     │                     │
     │ Bearer <jwt>       │                     │
     │                    │                     │
     │                    │ x-user-sub header   │
     │                    │────────────────────▶│
```

- **API Gateway** validates JWT tokens (Cognito authorizer)
- **FastAPI** receives `x-user-sub` header with Cognito `sub` claim
- **`require_auth()`** is a marker-only dependency for OpenAPI spec generation

### Protected Endpoint Example

```python
from fastapi import Depends, Request

from api.security import AuthScope, require_auth, SecurityRequirement


@router.get("/reservations")
async def get_my_reservations(
    request: Request,
    auth: SecurityRequirement = Depends(require_auth([AuthScope.OPENID])),
) -> list[ReservationSummary]:
    """Get current user's reservations."""
    # API Gateway validated JWT, passed sub via header
    user_sub = request.headers.get("x-user-sub")
    if not user_sub:
        raise HTTPException(401, "Missing user identity")

    # Look up guest by Cognito sub
    guest = db.get_guest_by_cognito_sub(user_sub)
    # ... rest of implementation
```

---

## Deployment

### Infrastructure (Terraform)

The API Gateway is provisioned via OpenAPI spec. After implementing endpoints:

1. Regenerate OpenAPI spec:
   ```bash
   cd backend && uv run python -m api.scripts.generate_openapi
   ```

2. Apply infrastructure:
   ```bash
   task tf:plan:dev
   task tf:apply:dev
   ```

### CI/CD

Tests run automatically on PR:
- Unit tests with `moto` mocking
- Contract tests verify OpenAPI schema
- Type checking with `mypy`
- Linting with `ruff`

---

## Checklist

### Per-Endpoint Checklist

- [ ] Write failing test first (`test_{endpoint}_routes.py`)
- [ ] Create/update route module with endpoint
- [ ] Add response model (reuse from `shared/models/`)
- [ ] Add request validation (Query/Path/Body params)
- [ ] Add OpenAPI documentation (summary, description, examples)
- [ ] Handle errors with `BookingError` + `ToolError`
- [ ] Add to router registration in `__init__.py`
- [ ] Verify test passes
- [ ] Update contract test if needed

### Category Completion Checklist

- [ ] **P1: Availability** (2 endpoints) - FR-001, FR-002
- [ ] **P1: Pricing** (5 endpoints) - FR-003 to FR-007
- [ ] **P1: Reservations** (5 endpoints) - FR-008 to FR-014
- [ ] **P2: Payments** (3 endpoints) - FR-015 to FR-017
- [ ] **P2: Guests** (4 endpoints) - FR-018 to FR-021
- [ ] **P2: Property** (2 endpoints) - FR-022, FR-023
- [ ] **P3: Area Info** (2 endpoints) - FR-024, FR-025

---

## References

- [Data Model](./data-model.md) - Request/response schemas
- [Research](./research.md) - Architecture decisions
- [Spec](./spec.md) - Functional requirements
- [Plan](./plan.md) - Implementation plan

**Note**: OpenAPI spec is CODE-FIRST - auto-generated from FastAPI app via `generate_openapi.py`. View at `http://localhost:3001/openapi.json` during development or via Terraform output after deployment.

---

## Troubleshooting

### Common Issues

**"DynamoDB table not found"**
- Ensure `create_tables` fixture is used
- Check `reset_dynamodb_singleton` is running (autouse fixture)

**"Import error for shared module"**
- Run `task backend:install` to install workspace packages
- Verify UV workspace is configured correctly

**"Tests pass locally but fail in CI"**
- Check AWS credential mocking (conftest.py sets fake credentials)
- Verify moto version compatibility

**"OpenAPI schema validation failed"**
- Run `uv run python -m api.scripts.generate_openapi` to regenerate
- Check response models are consistent with FastAPI endpoint definitions
