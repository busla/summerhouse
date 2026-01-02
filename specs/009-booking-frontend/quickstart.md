# Quickstart Guide: Complete Booking Frontend

**Feature**: 009-booking-frontend
**Date**: 2026-01-01

## Prerequisites

### Required Tools

| Tool | Version | Installation |
|------|---------|--------------|
| Node.js | 20+ | `brew install node` or [nodejs.org](https://nodejs.org) |
| Python | 3.13+ | `brew install python@3.13` or [python.org](https://python.org) |
| Terraform | 1.5+ | `brew install terraform` |
| Task | 3.x | `brew install go-task` or [taskfile.dev](https://taskfile.dev) |
| AWS CLI | 2.x | `brew install awscli` |
| Yarn | 4.x (Berry) | `corepack enable && corepack prepare yarn@stable --activate` |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

### AWS Account Setup

The existing AWS setup from `001-agent-booking-platform` is sufficient. This feature adds:

1. **DynamoDB Table**: `booking-{env}-pois` for Points of Interest
2. **API Endpoint**: `GET /pois` for retrieving POI data

No additional AWS permissions required beyond existing setup.

---

## Project Setup

### 1. Checkout Feature Branch

```bash
cd booking
git fetch origin
git checkout 009-booking-frontend
```

### 2. Install New Frontend Dependencies

```bash
cd frontend

# Install all dependencies including new packages
yarn install

# New packages added:
# - react-day-picker: Date range selection (FR-007)
# - react-leaflet + leaflet: Interactive maps (FR-024)
# - date-fns: Date manipulation for calendar
# - @types/leaflet: TypeScript definitions for Leaflet
```

Verify installation:

```bash
# Check React Day Picker
yarn tsc --noEmit

# Verify packages in package.json
grep -E "react-day-picker|react-leaflet|leaflet|date-fns" package.json
```

### 3. Generate API Client (First Time Setup)

The frontend uses a generated TypeScript client from the backend OpenAPI spec:

```bash
cd frontend

# Generate type-safe API client from FastAPI OpenAPI schema
yarn generate:api

# This creates src/lib/api-client/ with:
# - client.gen.ts: HTTP client functions
# - types.gen.ts: TypeScript interfaces matching backend models
# - services.gen.ts: Service-specific API calls
```

**Important**: Re-run `yarn generate:api` whenever backend API changes to stay in sync.

### 4. Backend Setup (POI Endpoint)

```bash
cd backend

# Install workspace dependencies (if not already done)
uv sync --dev

# Verify POI service
uv run python -c "from shared.services.poi import POIService; print('POI service OK')"
```

### 5. Infrastructure (POI Table)

> **IMPORTANT**: All Terraform commands MUST be run via `Taskfile.yaml`. Never run terraform directly.

```bash
# From repo root
task tf:plan:dev    # Review POI table creation
task tf:apply:dev   # Apply (creates booking-dev-pois table)

# Seed POI data
task seed:pois:dev
```

---

## Running Locally

### Start Backend

```bash
cd backend

# Run FastAPI with hot reload
uv run --package api uvicorn api.main:app --reload --port 3001

# POI endpoint available at:
# GET http://localhost:3001/api/pois
# GET http://localhost:3001/api/pois?category=beach
# GET http://localhost:3001/api/pois/{poi_id}
```

### Start Frontend

```bash
cd frontend

# Start Next.js dev server
yarn dev

# Opens http://localhost:3000
```

### Local Development Stack

| Service | URL | Description |
|---------|-----|-------------|
| Homepage | http://localhost:3000 | New property homepage with booking widget |
| Agent | http://localhost:3000/agent | AI chat interface (preserved) |
| Gallery | http://localhost:3000/gallery | Photo gallery with lightbox |
| Location | http://localhost:3000/location | Interactive map with POI markers |
| Book | http://localhost:3000/book | Direct booking form flow |
| Backend API | http://localhost:3001/api | FastAPI endpoints |
| POI Endpoint | http://localhost:3001/api/pois | Points of Interest data |

---

## New Components

### Booking Widget Components

```typescript
// BookingWidget.tsx - Date picker + price preview
import { BookingWidget } from '@/components/booking/BookingWidget'

<BookingWidget
  onDatesChange={(range) => console.log(range)}
  onBook={(dates) => router.push('/book')}
/>

// DateRangePicker.tsx - React Day Picker wrapper
import { DateRangePicker } from '@/components/booking/DateRangePicker'

<DateRangePicker
  selected={range}
  onSelect={setRange}
  disabled={bookedDates}  // Dates from availability API
  numberOfMonths={2}
/>

// PriceBreakdown.tsx - Price calculation display
import { PriceBreakdown } from '@/components/booking/PriceBreakdown'

<PriceBreakdown
  checkIn="2026-07-01"
  checkOut="2026-07-08"
  nightlyRate={12000}  // EUR cents
  cleaningFee={7500}
/>
```

### Map Components

```typescript
// LocationMap.tsx - Leaflet map wrapper (dynamic import for SSR)
import dynamic from 'next/dynamic'

const LocationMap = dynamic(
  () => import('@/components/map/LocationMapClient'),
  { ssr: false, loading: () => <div>Loading map...</div> }
)

// Usage in page
<LocationMap
  center={[38.0731, -0.8167]}  // Quesada coordinates
  pois={poiData}               // From API
/>

// POIMarker.tsx - Point of interest marker with popup
import { POIMarker } from '@/components/map/POIMarker'

<POIMarker
  poi={{
    poi_id: 'beach-guardamar',
    name: 'Guardamar Beach',
    category: 'beach',
    latitude: 38.0873,
    longitude: -0.6556,
    distance_text: '20 min drive'
  }}
/>
```

### Using Generated API Client

```typescript
// Configure client (once in layout or provider)
import { client } from '@/lib/api-client'

client.setConfig({
  baseUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001/api',
})

// Call API with full type safety
import { listPOIs, checkAvailability, createReservation } from '@/lib/api-client'

// Get POIs for map
const { data: pois } = await listPOIs({ query: { category: 'beach' } })

// Check availability (existing endpoint)
const { data: availability } = await checkAvailability({
  query: { check_in: '2026-07-01', check_out: '2026-07-08' }
})

// Create reservation (existing endpoint)
const { data: reservation } = await createReservation({
  body: {
    check_in: '2026-07-01',
    check_out: '2026-07-08',
    guest: {
      name: 'John Doe',
      email: 'john@example.com',
      phone: '+34612345678',
      numGuests: 2
    }
  }
})
```

---

## Running Tests

### Frontend Tests

```bash
cd frontend

# Unit tests (Vitest)
yarn test

# Unit tests with coverage
yarn test:coverage

# Watch mode for development
yarn test:watch

# Run specific test file
yarn test src/components/booking/DateRangePicker.test.tsx

# E2E tests (Playwright) - requires running backend
yarn test:e2e

# E2E booking flow only
yarn test:e2e --grep "booking"
```

### Backend Tests

```bash
cd backend

# Run all tests
uv run pytest

# Run POI-specific tests
uv run pytest tests/unit/services/test_poi.py
uv run pytest tests/unit/routes/test_poi.py

# Coverage report
uv run pytest --cov=shared --cov=api --cov-report=html
```

### Test Categories for This Feature

| Category | Location | Purpose |
|----------|----------|---------|
| Unit (Frontend) | `frontend/tests/unit/components/booking/` | Test date picker, price breakdown, booking form |
| Unit (Frontend) | `frontend/tests/unit/components/map/` | Test map rendering, POI markers |
| Unit (Backend) | `backend/tests/unit/services/test_poi.py` | Test POI service |
| Unit (Backend) | `backend/tests/unit/routes/test_poi.py` | Test POI API endpoint |
| E2E | `frontend/tests/e2e/booking-flow.spec.ts` | Full booking journey |
| E2E | `frontend/tests/e2e/homepage.spec.ts` | Homepage rendering, navigation |
| E2E | `frontend/tests/e2e/location-map.spec.ts` | Map interactions, POI popups |

---

## Common Development Tasks

### Regenerate API Client After Backend Changes

```bash
cd frontend
yarn generate:api
yarn tsc --noEmit  # Verify types still compile
```

### Add New POI Categories

1. Update `POICategory` enum in `backend/shared/src/shared/models/poi.py`
2. Update `POICategory` schema in `specs/009-booking-frontend/contracts/poi-api.yaml`
3. Regenerate frontend client: `yarn generate:api`
4. Add category icon mapping in `frontend/src/components/map/POIMarker.tsx`

### Test Map Without Backend

Use mock data in development:

```typescript
// In LocationMap component or page
const mockPOIs: POI[] = [
  {
    poi_id: 'beach-guardamar',
    category: 'beach',
    name: 'Guardamar Beach',
    description: 'Long sandy beach with Blue Flag status',
    latitude: 38.0873,
    longitude: -0.6556,
    distance_km: 15,
    distance_text: '20 min drive',
    is_active: true,
    display_order: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }
]
```

### Debug Leaflet SSR Issues

Leaflet requires browser APIs. Always use dynamic import:

```typescript
// CORRECT: Dynamic import with ssr: false
const LocationMap = dynamic(
  () => import('./LocationMapClient'),
  { ssr: false }
)

// WRONG: Direct import will fail during SSR
import { MapContainer } from 'react-leaflet'  // Error!
```

### View Booking Form Validation Errors

The booking form uses Zod schemas from `contracts/booking-form.schema.ts`:

```typescript
import { safeValidateBookingRequest, formatValidationErrors } from '@/specs/009-booking-frontend/contracts/booking-form.schema'

const result = safeValidateBookingRequest(formData)
if (!result.success) {
  const errors = formatValidationErrors(result.error)
  console.log(errors)
  // { 'guest.email': 'Please enter a valid email address', ... }
}
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `window is not defined` | Leaflet imported during SSR | Use `dynamic()` with `ssr: false` |
| API client types outdated | Backend schema changed | Run `yarn generate:api` |
| Map not displaying | Missing Leaflet CSS | Import `leaflet/dist/leaflet.css` in layout |
| Date picker styling broken | Missing Day Picker CSS | Import `react-day-picker/style.css` |
| POI endpoint 404 | Table not created | Run `task tf:apply:dev` |
| POI empty response | No seed data | Run `task seed:pois:dev` |
| Booking form validation fails | Schema mismatch | Check Zod schema matches API contract |

### Debug Mode

```bash
# Frontend verbose logging
cd frontend
DEBUG=* yarn dev

# Backend verbose logging
cd backend
LOG_LEVEL=DEBUG uv run --package api uvicorn api.main:app --reload

# API client debugging
# Add to api-client config:
client.setConfig({
  baseUrl: '...',
  onRequest: (req) => console.log('Request:', req),
  onResponse: (res) => console.log('Response:', res),
})
```

### Health Checks

```bash
# Backend health
curl http://localhost:3001/api/health

# POI endpoint
curl http://localhost:3001/api/pois

# POI by category
curl "http://localhost:3001/api/pois?category=beach"

# Frontend build check
cd frontend && yarn build

# Lighthouse performance audit
npx lighthouse http://localhost:3000 --view
```

---

## Deployment

### Deploy Infrastructure (POI Table)

> **IMPORTANT**: All Terraform commands MUST be run via `Taskfile.yaml`.

```bash
# From repo root
task tf:plan:prod
task tf:apply:prod

# Seed production POI data
task seed:pois:prod
```

### Deploy Frontend

Frontend deployment is **fully managed by Terraform**:

```bash
# From repo root - frontend build and S3 sync happen automatically
task tf:apply:prod

# The static-website module handles:
# 1. Detecting source changes (hash-based)
# 2. Building frontend (yarn build)
# 3. Syncing to S3
# 4. CloudFront cache uses content-hash filenames (no invalidation needed)
```

---

## Resources

### Feature Documentation

- [Feature Specification](./spec.md) - Requirements and user stories
- [Implementation Plan](./plan.md) - Architecture decisions
- [Research Notes](./research.md) - Library evaluation
- [Data Model](./data-model.md) - POI DynamoDB schema
- [POI API Contract](./contracts/poi-api.yaml) - OpenAPI spec
- [Booking Form Schema](./contracts/booking-form.schema.ts) - Zod validation

### External Documentation

- [React Day Picker](https://daypicker.dev/) - Date picker documentation
- [React Leaflet](https://react-leaflet.js.org/) - Map component library
- [Leaflet](https://leafletjs.com/) - Map library
- [@hey-api/openapi-ts](https://heyapi.dev/) - OpenAPI client generator
- [Zod](https://zod.dev/) - TypeScript schema validation

### Existing Feature Docs

- [001-agent-booking-platform](../001-agent-booking-platform/quickstart.md) - Base platform setup
