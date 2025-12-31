# Research: Tools REST API Endpoints

**Phase**: 0 | **Date**: 2025-12-31 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Executive Summary

This research documents the existing patterns, architecture decisions, and implementation strategies for exposing 21 Strands agent tools as FastAPI REST endpoints. The key finding is that the codebase already has clean separation between **models**, **services**, and **tools** - meaning REST endpoints can directly use existing services without modifying POC tool code.

---

## 1. Architecture Overview

### Current Layer Structure

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Layer                              │
│  (shared/tools/*.py - @tool decorated functions)            │
│  POC REFERENCE ONLY - NOT MODIFIED                          │
├─────────────────────────────────────────────────────────────┤
│                   Service Layer                              │
│  (shared/services/*.py - Business logic)                    │
│  REUSED DIRECTLY by REST endpoints                          │
├─────────────────────────────────────────────────────────────┤
│                    Model Layer                               │
│  (shared/models/*.py - Pydantic v2 strict)                  │
│  REUSED DIRECTLY by REST endpoints                          │
├─────────────────────────────────────────────────────────────┤
│                  Database Layer                              │
│  (DynamoDB via DynamoDBService singleton)                   │
└─────────────────────────────────────────────────────────────┘
```

### Key Insight: Service Reuse Strategy

The POC tools (`shared/tools/*.py`) are thin wrappers around services. For REST endpoints:

| Don't Use | Use Instead |
|-----------|-------------|
| `check_availability()` tool | `AvailabilityService.check_availability()` |
| `get_pricing()` tool | `PricingService.get_season_for_date()` |
| `create_reservation()` tool | `BookingService.create_reservation()` |

This avoids duplicating business logic and keeps the agent tools as reference-only.

---

## 2. Existing Code Patterns

### 2.1 FastAPI Router Pattern

**Source**: `backend/api/src/api/routes/health.py`

```python
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])

class HealthResponse(BaseModel):
    status: str
    version: str

@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="healthy", version="0.1.0")
```

**Key observations**:
- Routers use `APIRouter()` with tags for OpenAPI grouping
- Response models are Pydantic classes
- Endpoints are `async def` for Lambda compatibility
- No prefix on router - added when including in main app

### 2.2 App Initialization Pattern

**Source**: `backend/api/src/api/routes/__init__.py`

```python
from fastapi import FastAPI
from api.routes.health import router as health_router

app = FastAPI(
    title="Quesada Apartment Booking API",
    description="Agent-First Vacation Rental Booking Platform",
    version="0.1.0",
)

app.include_router(health_router, prefix="/api")
```

**Note**: All routes get `/api` prefix when included.

### 2.3 JWT Authentication Pattern

**Source**: `backend/api/src/api/security.py`

```python
from fastapi import Depends, Request
from pydantic import BaseModel

class AuthScope(str, Enum):
    BOOKING_READ = "booking:read"
    BOOKING_WRITE = "booking:write"
    GUEST_READ = "guest:read"
    GUEST_WRITE = "guest:write"

class SecurityRequirement(BaseModel):
    scopes: list[AuthScope] | None = None

def require_auth(scopes: list[AuthScope] | None = None):
    """Create a security requirement dependency.

    This dependency does NOT perform JWT validation (API Gateway does).
    It serves as a marker for the OpenAPI generation script.
    """
    def _require_auth(request: Request) -> SecurityRequirement:
        return SecurityRequirement(scopes=scopes)
    return _require_auth
```

**Usage in endpoints**:

```python
@router.post("/reservations")
async def create_reservation(
    body: ReservationCreateRequest,
    auth: SecurityRequirement = Depends(require_auth([AuthScope.BOOKING_WRITE])),
) -> ReservationResponse:
    # API Gateway has already validated JWT
    # 'auth' is marker-only for OpenAPI spec generation
    ...
```

**Important**: API Gateway handles JWT validation. The `require_auth()` dependency is purely for OpenAPI spec generation - it marks which endpoints need authentication.

### 2.4 DynamoDB Singleton Pattern

**Source**: `backend/shared/src/shared/services/dynamodb.py`

```python
_dynamodb_service_instance: "DynamoDBService | None" = None

def get_dynamodb_service(environment: str | None = None) -> "DynamoDBService":
    """Get or create the singleton DynamoDB service instance.

    This avoids creating new boto3 clients on every request,
    which adds ~100-200ms overhead per instantiation.
    """
    global _dynamodb_service_instance
    if _dynamodb_service_instance is None:
        _dynamodb_service_instance = DynamoDBService(environment)
    return _dynamodb_service_instance
```

**REST endpoints must use this singleton** for performance.

### 2.5 Service Instantiation Pattern

**Source**: `backend/shared/src/shared/services/availability.py`

Services have dependencies injected via constructor:

```python
class AvailabilityService:
    def __init__(self, db: "DynamoDBService", pricing: "PricingService") -> None:
        self.db = db
        self.pricing = pricing
```

**For REST endpoints**, use a FastAPI dependency:

```python
from functools import lru_cache

@lru_cache
def get_availability_service() -> AvailabilityService:
    db = get_dynamodb_service()
    pricing = PricingService(db)
    return AvailabilityService(db, pricing)
```

### 2.6 Error Response Pattern

**Source**: `backend/shared/src/shared/models/errors.py`

```python
class ToolError(BaseModel):
    model_config = ConfigDict(strict=True)
    success: bool = False
    error_code: ErrorCode
    message: str
    recovery: str
    details: Optional[dict[str, str]] = None

    @classmethod
    def from_code(cls, code: ErrorCode, details: Optional[dict[str, str]] = None) -> "ToolError":
        return cls(
            error_code=code,
            message=ERROR_MESSAGES[code],
            recovery=ERROR_RECOVERY[code],
            details=details
        )
```

**For REST endpoints**, convert to HTTP responses using exception handlers.

---

## 3. REST Endpoint Design Decisions

### 3.1 Error Handling Strategy

**Decision**: Use FastAPI exception handlers to convert errors to HTTP responses.

```python
# api/exceptions.py
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from shared.models.errors import ErrorCode, ToolError

class BookingError(Exception):
    """Base exception for booking errors."""
    def __init__(self, error: ToolError):
        self.error = error

@app.exception_handler(BookingError)
async def booking_error_handler(request: Request, exc: BookingError) -> JSONResponse:
    # Map error codes to HTTP status codes
    status_map = {
        ErrorCode.DATES_UNAVAILABLE: 409,      # Conflict
        ErrorCode.MINIMUM_NIGHTS_NOT_MET: 400,  # Bad Request
        ErrorCode.MAX_GUESTS_EXCEEDED: 400,
        ErrorCode.VERIFICATION_REQUIRED: 401,   # Unauthorized
        ErrorCode.VERIFICATION_FAILED: 401,
        ErrorCode.RESERVATION_NOT_FOUND: 404,   # Not Found
        ErrorCode.UNAUTHORIZED: 403,            # Forbidden
        ErrorCode.PAYMENT_FAILED: 402,          # Payment Required
    }
    return JSONResponse(
        status_code=status_map.get(exc.error.error_code, 400),
        content=exc.error.model_dump(),
    )
```

### 3.2 Request/Response Model Strategy

**Decision**: Create API-specific request/response models that wrap existing shared models.

**Rationale**:
- Shared models are designed for internal/service use
- REST APIs need different field names (camelCase for JSON)
- OpenAPI descriptions should be API-consumer focused

**Example**:

```python
# Shared model (snake_case, internal)
class Reservation(BaseModel):
    reservation_id: str
    guest_id: str
    check_in: date
    ...

# API response model (potentially different structure)
class ReservationResponse(BaseModel):
    """REST API response for a reservation."""
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="reservation_id")
    guest_id: str
    check_in: date
    check_out: date
    status: ReservationStatus
    total_amount: int = Field(..., description="Total in EUR cents")

    @classmethod
    def from_model(cls, r: Reservation) -> "ReservationResponse":
        return cls(**r.model_dump())
```

### 3.3 Service Layer Access Pattern

**Decision**: Use FastAPI dependencies for service access.

```python
# api/dependencies.py
from functools import lru_cache
from shared.services.dynamodb import get_dynamodb_service
from shared.services.availability import AvailabilityService
from shared.services.pricing import PricingService

@lru_cache
def get_pricing_service() -> PricingService:
    return PricingService(get_dynamodb_service())

@lru_cache
def get_availability_service() -> AvailabilityService:
    return AvailabilityService(
        db=get_dynamodb_service(),
        pricing=get_pricing_service(),
    )
```

**Usage**:

```python
@router.get("/availability")
async def check_availability(
    start_date: date = Query(...),
    end_date: date = Query(...),
    service: AvailabilityService = Depends(get_availability_service),
) -> AvailabilityResponse:
    return service.check_availability(start_date, end_date)
```

---

## 4. OpenAPI Documentation Quality (FR-029 to FR-032)

The spec requires high-quality OpenAPI documentation for future MCP tool generation:

### 4.1 Description Requirements

Every endpoint must have:

```python
@router.get(
    "/availability",
    summary="Check date availability",
    description="""
    Check if specific dates are available for booking.

    Returns availability status, pricing breakdown, and any unavailable
    dates within the requested range. Use this before creating a reservation
    to verify dates are open.

    **Notes:**
    - Dates are in YYYY-MM-DD format
    - check_out is exclusive (last night is check_out - 1)
    - Amounts are in EUR cents
    """,
    response_description="Availability status with pricing breakdown",
)
```

### 4.2 Example Values

All request/response models must include examples:

```python
class AvailabilityCheckRequest(BaseModel):
    """Request to check availability for a date range."""

    start_date: date = Field(
        ...,
        description="Check-in date (YYYY-MM-DD)",
        examples=["2025-07-15"],
    )
    end_date: date = Field(
        ...,
        description="Check-out date (YYYY-MM-DD)",
        examples=["2025-07-22"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "start_date": "2025-07-15",
                    "end_date": "2025-07-22",
                }
            ]
        }
    )
```

### 4.3 Error Response Documentation

```python
@router.get(
    "/reservations/{id}",
    responses={
        200: {"description": "Reservation found"},
        404: {
            "description": "Reservation not found",
            "model": ToolError,
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "error_code": "ERR_006",
                        "message": "Reservation not found",
                        "recovery": "Ask guest to verify reservation ID",
                        "details": {"reservation_id": "RES-2025-INVALID"}
                    }
                }
            }
        }
    }
)
```

---

## 5. Authentication Flow

### 5.1 JWT Token Flow

```
┌─────────────┐      ┌──────────────┐      ┌───────────┐      ┌────────────┐
│   Client    │──────│ API Gateway  │──────│  Lambda   │──────│  DynamoDB  │
│  (Frontend) │      │ (JWT Valid.) │      │ (FastAPI) │      │            │
└─────────────┘      └──────────────┘      └───────────┘      └────────────┘
      │                     │                    │                   │
      │ Authorization:      │                    │                   │
      │ Bearer <JWT>        │                    │                   │
      │────────────────────>│                    │                   │
      │                     │                    │                   │
      │                     │ Validate JWT       │                   │
      │                     │ (Cognito issuer)   │                   │
      │                     │                    │                   │
      │                     │ x-user-sub: <sub>  │                   │
      │                     │────────────────────>                   │
      │                     │                    │                   │
      │                     │                    │ Query by guest_id │
      │                     │                    │───────────────────>
```

### 5.2 Getting User Identity

For JWT-protected endpoints, the user's Cognito `sub` is passed via header:

```python
@router.get("/reservations")
async def get_my_reservations(
    request: Request,
    auth: SecurityRequirement = Depends(require_auth([AuthScope.BOOKING_READ])),
    db: DynamoDBService = Depends(get_dynamodb_service),
) -> list[ReservationSummary]:
    # API Gateway adds x-user-sub header after JWT validation
    user_sub = request.headers.get("x-user-sub")
    if not user_sub:
        raise HTTPException(status_code=401, detail="Missing user identity")

    # Look up guest by Cognito sub
    guest = db.get_guest_by_cognito_sub(user_sub)
    if not guest:
        return []  # User exists in Cognito but not in our DB yet

    # Get reservations for this guest
    reservations = db.get_reservations_by_guest_id(guest["guest_id"])
    return [ReservationSummary.model_validate(r) for r in reservations]
```

---

## 6. Existing Services Inventory

| Service | Location | Methods to Reuse |
|---------|----------|------------------|
| `AvailabilityService` | `services/availability.py` | `check_availability()`, `get_range()`, `get_date()` |
| `PricingService` | `services/pricing.py` | `calculate_price()`, `get_all_seasons()`, `get_season_for_date()`, `validate_minimum_stay()` |
| `BookingService` | `services/booking.py` | `create_reservation()`, `modify_reservation()`, `cancel_reservation()`, `get_reservation()` |
| `PaymentService` | `services/payment_service.py` | `process_payment()`, `get_payment_status()`, `retry_payment()` |
| `DynamoDBService` | `services/dynamodb.py` | `get_guest_by_email()`, `get_guest_by_cognito_sub()`, `get_reservations_by_guest_id()` |

### Services That Need Creation

| Service | Reason | Methods Needed |
|---------|--------|----------------|
| `PropertyService` | No existing service | `get_details()`, `get_photos()` |
| `AreaInfoService` | No existing service | `get_info()`, `get_recommendations()` |
| `VerificationService` | Logic in tools only | `initiate()`, `verify_code()` |

**Decision**: Create these as thin services in `shared/services/` that the REST endpoints can use.

---

## 7. Existing Models Inventory

| Model | Location | Status |
|-------|----------|--------|
| `Reservation`, `ReservationCreate`, `ReservationSummary` | `models/reservation.py` | ✅ Ready |
| `Availability`, `AvailabilityRange`, `AvailabilityResponse` | `models/availability.py` | ✅ Ready |
| `Pricing`, `PriceCalculation` | `models/pricing.py` | ✅ Ready |
| `Payment`, `PaymentCreate`, `PaymentStatus` | `models/payment.py` | ✅ Ready |
| `Guest`, `GuestCreate` | `models/guest.py` | ✅ Ready |
| `Property` | `models/property.py` | ✅ Ready |
| `AreaInfo`, `Recommendation` | `models/area_info.py` | ✅ Ready |
| `ToolError`, `ErrorCode` | `models/errors.py` | ✅ Ready |
| `VerificationCode` | `models/verification.py` | ✅ Ready |

---

## 8. Performance Considerations

### 8.1 Cold Start Optimization

- Use `@lru_cache` for service instantiation
- Initialize services outside request handlers where possible
- Keep imports minimal in route files

### 8.2 Connection Reuse

- **Always** use `get_dynamodb_service()` singleton
- Never instantiate `DynamoDBService()` directly in endpoints

### 8.3 Response Time Targets

| Endpoint Type | Target | Strategy |
|---------------|--------|----------|
| Read (availability, pricing) | <500ms | Single DynamoDB query, cached services |
| Write (reservations) | <1000ms | Transactional writes, minimal validation |
| List (my reservations) | <500ms | GSI query, pagination if needed |

---

## 9. Testing Strategy

### 9.1 Unit Tests

Use `moto` for DynamoDB mocking (already in test setup):

```python
import pytest
from moto import mock_aws
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    with mock_aws():
        # Reset singleton for fresh mock connection
        reset_dynamodb_service()
        # Create tables in mock DynamoDB
        _create_test_tables()
        # Import app after mock setup
        from api.main import app
        yield TestClient(app)

def test_check_availability(client):
    response = client.get("/api/availability?start_date=2025-07-15&end_date=2025-07-22")
    assert response.status_code == 200
    data = response.json()
    assert "is_available" in data
```

### 9.2 Contract Tests

Verify OpenAPI schema matches implementation:

```python
def test_openapi_schema_complete():
    """Ensure all 21 endpoints are documented in OpenAPI schema."""
    from api.main import app
    schema = app.openapi()

    required_paths = [
        "/api/availability",
        "/api/availability/calendar/{month}",
        "/api/pricing",
        "/api/pricing/calculate",
        # ... all 21 endpoints
    ]

    for path in required_paths:
        assert path in schema["paths"], f"Missing: {path}"
```

---

## 10. File Structure Summary

```text
backend/api/src/api/
├── main.py                    # FastAPI app + Mangum handler
├── security.py                # JWT auth markers (existing)
├── dependencies.py            # NEW: Service dependency injection
├── exceptions.py              # NEW: Exception handlers
└── routes/
    ├── __init__.py            # Router registration
    ├── health.py              # Existing
    ├── availability.py        # NEW: 2 endpoints
    ├── pricing.py             # NEW: 5 endpoints
    ├── reservations.py        # NEW: 5 endpoints
    ├── payments.py            # NEW: 3 endpoints
    ├── guests.py              # NEW: 4 endpoints
    ├── property.py            # NEW: 2 endpoints
    └── area.py                # NEW: 2 endpoints

backend/shared/src/shared/
├── models/                    # UNCHANGED - reuse existing
├── services/
│   ├── dynamodb.py            # UNCHANGED
│   ├── availability.py        # UNCHANGED
│   ├── pricing.py             # UNCHANGED
│   ├── booking.py             # UNCHANGED (if exists)
│   ├── payment_service.py     # UNCHANGED
│   ├── property.py            # NEW: Property data service
│   ├── area_info.py           # NEW: Area info service
│   └── verification.py        # NEW: Verification service
└── tools/                     # POC REFERENCE ONLY - NOT MODIFIED
```

---

## 11. Open Questions (Resolved)

| Question | Resolution |
|----------|------------|
| Should we modify existing tools? | **No** - tools are POC reference; endpoints use services directly |
| How to handle auth in Lambda? | API Gateway validates JWT, passes `x-user-sub` header |
| camelCase vs snake_case in API? | **snake_case** - consistent with Pydantic field names |
| Where to add new services? | `shared/services/` - same pattern as existing |

---

## 12. References

- [FastAPI Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Pydantic v2 Strict Mode](https://docs.pydantic.dev/latest/concepts/strict_mode/)
- [OpenAPI 3.0 Spec](https://swagger.io/specification/)
- [AWS API Gateway JWT Authorizer](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html)
- Existing codebase: `backend/shared/src/shared/services/`, `backend/api/src/api/routes/`
