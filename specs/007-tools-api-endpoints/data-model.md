# Data Model: Tools REST API Endpoints

**Phase**: 1 | **Date**: 2025-12-31 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Overview

This document defines request/response models for all 21 REST API endpoints. Models are organized by category and follow these conventions:

- **Reuse existing models** from `shared/models/` where appropriate
- **Create API-specific wrappers** for HTTP-specific concerns (status codes, error responses)
- **Use Pydantic v2 strict mode** for all models
- **Include examples** for OpenAPI documentation quality (FR-029)
- **Amounts in EUR cents** (not euros) to avoid floating-point issues

---

## Enumerations (Existing)

All enums are defined in `shared/models/enums.py`:

| Enum | Values | Used In |
|------|--------|---------|
| `ReservationStatus` | `pending`, `confirmed`, `cancelled`, `completed` | Reservations |
| `PaymentStatus` | `pending`, `paid`, `refunded`, `partial_refund`, `cancelled` | Reservations |
| `AvailabilityStatus` | `available`, `booked`, `blocked` | Availability |
| `PaymentMethod` | `card`, `paypal`, `bank_transfer` | Payments |
| `TransactionStatus` | `pending`, `completed`, `failed`, `refunded` | Payments |
| `PhotoCategory` | `exterior`, `living_room`, `bedroom`, etc. | Property |
| `AreaCategory` | `golf`, `beach`, `restaurant`, `attraction`, `activity` | Area Info |

---

## Category 1: Availability (P1)

### GET `/api/availability`

Check if dates are available for booking.

**Query Parameters**:

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `start_date` | date | Yes | Check-in date (YYYY-MM-DD) | `2025-07-15` |
| `end_date` | date | Yes | Check-out date (YYYY-MM-DD) | `2025-07-22` |

**Response**: `AvailabilityResponse` (existing model in `shared/models/availability.py`)

```python
class AvailabilityResponse(BaseModel):
    """Response for availability check."""
    model_config = ConfigDict(strict=True)

    start_date: date
    end_date: date
    is_available: bool
    unavailable_dates: list[date] = Field(default_factory=list)
    total_nights: int
    nightly_rate: int = Field(..., description="Rate per night in EUR cents")
    cleaning_fee: int = Field(..., description="Cleaning fee in EUR cents")
    total_amount: int = Field(..., description="Total price in EUR cents")
```

**Example Response**:
```json
{
  "start_date": "2025-07-15",
  "end_date": "2025-07-22",
  "is_available": true,
  "unavailable_dates": [],
  "total_nights": 7,
  "nightly_rate": 15000,
  "cleaning_fee": 7500,
  "total_amount": 112500
}
```

**Status Codes**: `200` OK

---

### GET `/api/availability/calendar/{month}`

Get calendar view for a month.

**Path Parameters**:

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `month` | str | Yes | Month in YYYY-MM format | `2025-07` |

**Response** (new model):

```python
class CalendarDay(BaseModel):
    """Single day in calendar view."""
    model_config = ConfigDict(strict=True)

    date: date
    status: AvailabilityStatus
    is_check_in_allowed: bool = True
    is_check_out_allowed: bool = True

class CalendarResponse(BaseModel):
    """Monthly calendar view."""
    model_config = ConfigDict(strict=True)

    month: str = Field(..., pattern=r"^\d{4}-\d{2}$", examples=["2025-07"])
    days: list[CalendarDay]
    available_count: int
    booked_count: int
    blocked_count: int
```

**Example Response**:
```json
{
  "month": "2025-07",
  "days": [
    {"date": "2025-07-01", "status": "available", "is_check_in_allowed": true, "is_check_out_allowed": true},
    {"date": "2025-07-02", "status": "booked", "is_check_in_allowed": false, "is_check_out_allowed": false}
  ],
  "available_count": 20,
  "booked_count": 8,
  "blocked_count": 3
}
```

**Status Codes**: `200` OK, `400` Invalid month format

---

## Category 2: Pricing (P1)

### GET `/api/pricing`

Get current pricing (base rates).

**Query Parameters**: None

**Response** (new model):

```python
class BasePricingResponse(BaseModel):
    """Current base pricing information."""
    model_config = ConfigDict(strict=True)

    nightly_rate: int = Field(..., description="Current nightly rate in EUR cents")
    cleaning_fee: int = Field(..., description="Cleaning fee in EUR cents")
    minimum_nights: int = Field(..., description="Current minimum stay")
    season_name: str = Field(..., description="Current season name")
    currency: str = "EUR"
```

**Example Response**:
```json
{
  "nightly_rate": 15000,
  "cleaning_fee": 7500,
  "minimum_nights": 7,
  "season_name": "High Season (July-August)",
  "currency": "EUR"
}
```

**Status Codes**: `200` OK

---

### GET `/api/pricing/calculate`

Calculate total price for a stay.

**Query Parameters**:

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `start_date` | date | Yes | Check-in date | `2025-07-15` |
| `end_date` | date | Yes | Check-out date | `2025-07-22` |

**Response**: `PriceCalculation` (existing model in `shared/models/pricing.py`)

```python
class PriceCalculation(BaseModel):
    """Result of price calculation for a stay."""
    model_config = ConfigDict(strict=True)

    check_in: date
    check_out: date
    nights: int
    nightly_rate: int = Field(..., description="Effective nightly rate in EUR cents")
    subtotal: int = Field(..., description="nights * nightly_rate in EUR cents")
    cleaning_fee: int = Field(..., description="Cleaning fee in EUR cents")
    total_amount: int = Field(..., description="Total price in EUR cents")
    minimum_nights: int
    season_name: str
```

**Example Response**:
```json
{
  "check_in": "2025-07-15",
  "check_out": "2025-07-22",
  "nights": 7,
  "nightly_rate": 15000,
  "subtotal": 105000,
  "cleaning_fee": 7500,
  "total_amount": 112500,
  "minimum_nights": 7,
  "season_name": "High Season (July-August)"
}
```

**Status Codes**: `200` OK, `400` Invalid dates

---

### GET `/api/pricing/rates`

Get all seasonal rates.

**Query Parameters**: None

**Response** (new model):

```python
class SeasonalRatesResponse(BaseModel):
    """All seasonal pricing rates."""
    model_config = ConfigDict(strict=True)

    seasons: list[Pricing]
    currency: str = "EUR"

# Where Pricing is existing model:
class Pricing(BaseModel):
    season_id: str
    season_name: str
    start_date: date
    end_date: date
    nightly_rate: int
    minimum_nights: int
    cleaning_fee: int
    is_active: bool = True
```

**Example Response**:
```json
{
  "seasons": [
    {
      "season_id": "low-2025",
      "season_name": "Low Season",
      "start_date": "2025-01-01",
      "end_date": "2025-03-31",
      "nightly_rate": 8000,
      "minimum_nights": 3,
      "cleaning_fee": 5000,
      "is_active": true
    }
  ],
  "currency": "EUR"
}
```

**Status Codes**: `200` OK

---

### GET `/api/pricing/minimum-stay`

Check minimum stay requirement.

**Query Parameters**:

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `start_date` | date | Yes | Check-in date | `2025-07-15` |
| `end_date` | date | Yes | Check-out date | `2025-07-22` |

**Response** (new model):

```python
class MinimumStayCheckResponse(BaseModel):
    """Result of minimum stay validation."""
    model_config = ConfigDict(strict=True)

    is_valid: bool
    requested_nights: int
    minimum_nights: int
    season_name: str
    message: str = ""
```

**Example Response**:
```json
{
  "is_valid": true,
  "requested_nights": 7,
  "minimum_nights": 7,
  "season_name": "High Season (July-August)",
  "message": ""
}
```

**Status Codes**: `200` OK, `400` Invalid dates

---

### GET `/api/pricing/minimum-stay/{date}`

Get minimum stay info for a specific date.

**Path Parameters**:

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `date` | date | Yes | Date to check | `2025-07-15` |

**Response** (new model):

```python
class MinimumStayInfoResponse(BaseModel):
    """Minimum stay information for a date."""
    model_config = ConfigDict(strict=True)

    date: date
    minimum_nights: int
    season_name: str
    nightly_rate: int
```

**Example Response**:
```json
{
  "date": "2025-07-15",
  "minimum_nights": 7,
  "season_name": "High Season (July-August)",
  "nightly_rate": 15000
}
```

**Status Codes**: `200` OK, `404` No pricing for date

---

## Category 3: Reservations (P1)

### POST `/api/reservations` (JWT Required)

Create a new reservation.

**Request Body**:

```python
class ReservationCreateRequest(BaseModel):
    """Request to create a reservation."""
    model_config = ConfigDict(strict=True)

    check_in: date = Field(..., examples=["2025-07-15"])
    check_out: date = Field(..., examples=["2025-07-22"])
    num_adults: int = Field(..., ge=1, le=4, examples=[2])
    num_children: int = Field(default=0, ge=0, le=4, examples=[0])
    special_requests: str | None = Field(default=None, max_length=500)
```

**Example Request**:
```json
{
  "check_in": "2025-07-15",
  "check_out": "2025-07-22",
  "num_adults": 2,
  "num_children": 1,
  "special_requests": "Late arrival around 10pm"
}
```

**Response**: `Reservation` (existing model)

**Status Codes**:
- `201` Created
- `400` Bad request (validation error)
- `401` Unauthorized (no JWT)
- `409` Conflict (dates unavailable)

---

### GET `/api/reservations/{id}`

Get reservation by ID.

**Path Parameters**:

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `id` | str | Yes | Reservation ID | `RES-2025-001234` |

**Response**: `Reservation` (existing model)

```python
class Reservation(BaseModel):
    """A vacation rental reservation."""
    model_config = ConfigDict(strict=True)

    reservation_id: str
    guest_id: str
    check_in: date
    check_out: date
    num_adults: int
    num_children: int = 0
    status: ReservationStatus
    payment_status: PaymentStatus
    total_amount: int
    cleaning_fee: int
    nightly_rate: int
    nights: int
    special_requests: str | None = None
    created_at: datetime
    updated_at: datetime
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None
    refund_amount: int | None = None
```

**Status Codes**: `200` OK, `404` Not found

---

### GET `/api/reservations` (JWT Required)

Get current user's reservations.

**Query Parameters**:

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `status` | str | No | Filter by status | `confirmed` |
| `limit` | int | No | Max results (default 20) | `10` |

**Response**:

```python
class ReservationListResponse(BaseModel):
    """List of reservations."""
    model_config = ConfigDict(strict=True)

    reservations: list[ReservationSummary]
    total_count: int

class ReservationSummary(BaseModel):
    """Summary view of a reservation."""
    model_config = ConfigDict(strict=True)

    reservation_id: str
    check_in: date
    check_out: date
    status: ReservationStatus
    total_amount: int
```

**Status Codes**: `200` OK, `401` Unauthorized

---

### PATCH `/api/reservations/{id}` (JWT Required)

Modify a reservation.

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | str | Yes | Reservation ID |

**Request Body**:

```python
class ReservationModifyRequest(BaseModel):
    """Request to modify a reservation."""
    model_config = ConfigDict(strict=True)

    check_in: date | None = None
    check_out: date | None = None
    num_adults: int | None = Field(default=None, ge=1, le=4)
    num_children: int | None = Field(default=None, ge=0, le=4)
    special_requests: str | None = None
```

**Response**: `Reservation` (updated)

**Status Codes**:
- `200` OK
- `400` Invalid modification
- `401` Unauthorized
- `403` Forbidden (not your reservation)
- `404` Not found
- `409` Conflict (new dates unavailable)

---

### DELETE `/api/reservations/{id}` (JWT Required)

Cancel a reservation.

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | str | Yes | Reservation ID |

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `reason` | str | No | Cancellation reason |

**Response**:

```python
class CancellationResponse(BaseModel):
    """Reservation cancellation result."""
    model_config = ConfigDict(strict=True)

    reservation_id: str
    status: ReservationStatus  # Will be "cancelled"
    refund_amount: int | None = None
    refund_policy: str
```

**Status Codes**:
- `200` OK (cancelled)
- `401` Unauthorized
- `403` Forbidden
- `404` Not found
- `409` Conflict (already cancelled)

---

## Category 4: Payments (P2)

### POST `/api/payments` (JWT Required)

Process a payment.

**Request Body**:

```python
class PaymentRequest(BaseModel):
    """Request to process a payment."""
    model_config = ConfigDict(strict=True)

    reservation_id: str
    payment_method: PaymentMethod
    # Amount comes from reservation - not user input
```

**Response**: `PaymentResult` (existing model)

```python
class PaymentResult(BaseModel):
    """Result of a payment operation."""
    model_config = ConfigDict(strict=True)

    payment_id: str
    status: TransactionStatus
    provider_transaction_id: str | None = None
    error_message: str | None = None
```

**Status Codes**:
- `201` Created (payment initiated)
- `400` Bad request
- `401` Unauthorized
- `402` Payment failed
- `404` Reservation not found

---

### GET `/api/payments/{reservation_id}`

Get payment status for a reservation.

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `reservation_id` | str | Yes | Reservation ID |

**Response**: `Payment` (existing model)

```python
class Payment(BaseModel):
    """A payment transaction for a reservation."""
    model_config = ConfigDict(strict=True)

    payment_id: str
    reservation_id: str
    amount: int
    currency: str = "EUR"
    status: TransactionStatus
    payment_method: PaymentMethod
    provider: PaymentProvider
    provider_transaction_id: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
```

**Status Codes**: `200` OK, `404` Not found

---

### POST `/api/payments/{reservation_id}/retry` (JWT Required)

Retry a failed payment.

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `reservation_id` | str | Yes | Reservation ID |

**Request Body**:

```python
class PaymentRetryRequest(BaseModel):
    """Request to retry a failed payment."""
    model_config = ConfigDict(strict=True)

    payment_method: PaymentMethod | None = None  # Use same if not provided
```

**Response**: `PaymentResult`

**Status Codes**:
- `200` OK (retry successful)
- `400` Bad request (no failed payment to retry)
- `401` Unauthorized
- `402` Payment failed again
- `404` Reservation not found

---

## Category 5: Guests (P2)

### POST `/api/guests/verify`

Initiate email verification.

**Request Body**: `VerificationRequest` (existing model)

```python
class VerificationRequest(BaseModel):
    """Request to send a verification code."""
    model_config = ConfigDict(strict=True)

    email: EmailStr
```

**Response**:

```python
class VerificationInitiatedResponse(BaseModel):
    """Verification code sent response."""
    model_config = ConfigDict(strict=True)

    message: str = "Verification code sent"
    expires_in_seconds: int = 600  # 10 minutes
```

**Status Codes**:
- `200` OK (code sent)
- `400` Invalid email
- `429` Too many requests

---

### POST `/api/guests/verify/confirm`

Verify email code.

**Request Body**: `VerificationAttempt` (existing model)

```python
class VerificationAttempt(BaseModel):
    """Attempt to verify a code."""
    model_config = ConfigDict(strict=True)

    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
```

**Response**: `VerificationResult` (existing model)

```python
class VerificationResult(BaseModel):
    """Result of verification attempt."""
    model_config = ConfigDict(strict=True)

    success: bool
    guest_id: str | None = None
    error: str | None = None
    is_new_guest: bool = False
```

**Status Codes**:
- `200` OK (verified)
- `400` Invalid code format
- `401` Wrong code / expired

---

### GET `/api/guests/{email}` (JWT Required)

Get guest info by email.

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email` | str | Yes | Guest email (URL encoded) |

**Response**: `Guest` (existing model)

```python
class Guest(BaseModel):
    """A registered guest."""
    model_config = ConfigDict(strict=True)

    guest_id: str
    email: EmailStr
    cognito_sub: str | None = None
    name: str | None = None
    phone: str | None = None
    preferred_language: str = "en"
    email_verified: bool = False
    first_verified_at: datetime | None = None
    total_bookings: int = 0
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
```

**Status Codes**:
- `200` OK
- `401` Unauthorized
- `403` Forbidden (can only access own profile)
- `404` Not found

---

### PATCH `/api/guests/{guest_id}` (JWT Required)

Update guest details.

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `guest_id` | str | Yes | Guest ID |

**Request Body**: `GuestUpdate` (existing model)

```python
class GuestUpdate(BaseModel):
    """Fields that can be updated for a guest."""
    model_config = ConfigDict(strict=True)

    name: str | None = None
    phone: str | None = None
    preferred_language: str | None = Field(default=None, pattern="^(en|es)$")
```

**Response**: `Guest` (updated)

**Status Codes**:
- `200` OK
- `400` Invalid data
- `401` Unauthorized
- `403` Forbidden (can only update own profile)
- `404` Not found

---

## Category 6: Property (P2)

### GET `/api/property`

Get property details.

**Response**: `Property` (existing model)

```python
class Property(BaseModel):
    """Complete property details."""
    model_config = ConfigDict(strict=True)

    property_id: str
    name: str
    description: str
    address: Address
    coordinates: Coordinates
    bedrooms: int
    bathrooms: int
    max_guests: int
    amenities: list[str]
    photos: list[Photo]
    check_in_time: str = "15:00"
    check_out_time: str = "10:00"
    house_rules: list[str]
    highlights: list[str]
```

**Status Codes**: `200` OK

---

### GET `/api/property/photos`

Get property photos.

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | str | No | Filter by category |

**Response**: `PhotosResponse` (existing model)

```python
class PhotosResponse(BaseModel):
    """Response model for photo requests."""
    model_config = ConfigDict(strict=True)

    photos: list[Photo]
    category: PhotoCategory | None = None
    total_count: int
```

**Status Codes**: `200` OK, `400` Invalid category

---

## Category 7: Area Info (P3)

### GET `/api/area`

Get area information.

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | str | No | Filter by category |

**Response**: `AreaInfoResponse` (existing model)

```python
class AreaInfoResponse(BaseModel):
    """Response model for area information queries."""
    model_config = ConfigDict(strict=True)

    places: list[AreaInfo]
    category: AreaCategory | None = None
    total_count: int
```

**Status Codes**: `200` OK, `400` Invalid category

---

### GET `/api/area/recommendations`

Get personalized recommendations.

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `interests` | str | No | Comma-separated interests |
| `max_distance_km` | float | No | Max distance filter |
| `family_friendly` | bool | No | Family-friendly only |
| `limit` | int | No | Max results (default 5) |

**Response**: `RecommendationResponse` (existing model)

```python
class RecommendationResponse(BaseModel):
    """Response model for recommendations."""
    model_config = ConfigDict(strict=True)

    recommendations: list[AreaInfo]
    total_count: int
    filters_applied: dict[str, Any]
```

**Status Codes**: `200` OK

---

## Error Response Model

All error responses use the existing `ToolError` model:

```python
class ToolError(BaseModel):
    """Standard error response format."""
    model_config = ConfigDict(strict=True)

    success: bool = False
    error_code: ErrorCode  # e.g., "ERR_001", "ERR_006"
    message: str
    recovery: str  # Suggestion for how to recover
    details: dict[str, str] | None = None
```

### Error Code to HTTP Status Mapping

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `ERR_001` DATES_UNAVAILABLE | 409 Conflict | Dates are booked/blocked |
| `ERR_002` MINIMUM_NIGHTS_NOT_MET | 400 Bad Request | Stay too short |
| `ERR_003` MAX_GUESTS_EXCEEDED | 400 Bad Request | More than 4 guests |
| `ERR_004` VERIFICATION_REQUIRED | 401 Unauthorized | Must verify email first |
| `ERR_005` VERIFICATION_FAILED | 401 Unauthorized | Invalid/expired code |
| `ERR_006` RESERVATION_NOT_FOUND | 404 Not Found | Invalid reservation ID |
| `ERR_007` UNAUTHORIZED | 403 Forbidden | Can't access this resource |
| `ERR_008` PAYMENT_FAILED | 402 Payment Required | Payment processing error |
| `ERR_AUTH_*` | 401/403 | Authentication errors |

---

## New Models Summary

Models that need to be created in `api/src/api/models/`:

| Model | Location | Purpose |
|-------|----------|---------|
| `CalendarDay`, `CalendarResponse` | `api/models/availability.py` | Calendar endpoint |
| `BasePricingResponse` | `api/models/pricing.py` | Current pricing |
| `SeasonalRatesResponse` | `api/models/pricing.py` | All rates |
| `MinimumStayCheckResponse` | `api/models/pricing.py` | Validation result |
| `MinimumStayInfoResponse` | `api/models/pricing.py` | Date-specific info |
| `ReservationCreateRequest` | `api/models/reservations.py` | Create request |
| `ReservationModifyRequest` | `api/models/reservations.py` | Modify request |
| `ReservationListResponse` | `api/models/reservations.py` | List response |
| `CancellationResponse` | `api/models/reservations.py` | Cancel result |
| `PaymentRequest` | `api/models/payments.py` | Process payment |
| `PaymentRetryRequest` | `api/models/payments.py` | Retry payment |
| `VerificationInitiatedResponse` | `api/models/guests.py` | Code sent |

---

## Model Reuse Summary

Existing models from `shared/models/` to reuse directly:

| Model | File | Endpoints |
|-------|------|-----------|
| `AvailabilityResponse` | `availability.py` | GET /availability |
| `Pricing`, `PriceCalculation` | `pricing.py` | Pricing endpoints |
| `Reservation`, `ReservationSummary` | `reservation.py` | Reservation endpoints |
| `Payment`, `PaymentResult` | `payment.py` | Payment endpoints |
| `Guest`, `GuestUpdate` | `guest.py` | Guest endpoints |
| `VerificationRequest`, `VerificationAttempt`, `VerificationResult` | `verification.py` | Verification |
| `Property`, `PhotosResponse` | `property.py` | Property endpoints |
| `AreaInfoResponse`, `RecommendationResponse` | `area_info.py` | Area endpoints |
| `ToolError` | `errors.py` | All error responses |
