# Research: Complete Booking Frontend

**Feature**: 009-booking-frontend | **Date**: 2026-01-01 | **Phase**: 0

## Executive Summary

This research validates the technical approach for transforming the agent-first booking platform into a complete traditional frontend. Three key libraries were evaluated: **React Day Picker** for date selection, **React Leaflet** for interactive maps, and **@hey-api/openapi-ts** for type-safe API client generation. All libraries are well-suited for the requirements and integrate cleanly with the existing Next.js + Tailwind stack.

## Library Research

### 1. React Day Picker (Date Selection)

**Package**: `react-day-picker` | **Version**: 9.x | **License**: MIT

**Why Selected** (per spec clarification):
- Lightweight (~10KB gzipped)
- Fully accessible (WCAG 2.1 AA compliant)
- Native Tailwind CSS integration
- No date library dependency required (but works with date-fns)

#### Date Range Selection Pattern

For the booking widget (FR-007), use `mode="range"` with controlled state:

```tsx
import { useState } from "react";
import { addDays, format } from "date-fns";
import { type DateRange, DayPicker } from "react-day-picker";
import "react-day-picker/style.css";

function BookingDatePicker() {
  const defaultSelected: DateRange = {
    from: new Date(),
    to: addDays(new Date(), 4),
  };
  const [range, setRange] = useState<DateRange | undefined>(defaultSelected);

  let footer = "Please pick the first day.";
  if (range?.from) {
    if (!range.to) {
      footer = format(range.from, "PPP");
    } else if (range.to) {
      footer = `${format(range.from, "PPP")}–${format(range.to, "PPP")}`;
    }
  }

  return (
    <DayPicker
      mode="range"
      selected={range}
      footer={footer}
      onSelect={setRange}
      numberOfMonths={2}
    />
  );
}
```

#### Booked/Unavailable Dates Pattern

For FR-008 (show unavailable dates as blocked), use custom `modifiers`:

```tsx
import { type DayMouseEventHandler, DayPicker } from "react-day-picker";
import "react-day-picker/style.css";

const css = `
.booked {
  position: relative;
  background-color: #ffebee;
}
.booked::before {
  content: "";
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  height: 2px;
  background: currentColor;
  z-index: 1;
  transform: rotate(-45deg);
}`;

function AvailabilityDatePicker({ bookedDates }: { bookedDates: Date[] }) {
  const handleDayClick: DayMouseEventHandler = (day, { booked }) => {
    if (booked) {
      alert(`${day.toLocaleDateString()} is already booked`);
    }
  };

  return (
    <>
      <style>{css}</style>
      <DayPicker
        mode="range"
        modifiers={{ booked: bookedDates }}
        modifiersClassNames={{ booked: "booked" }}
        onDayClick={handleDayClick}
      />
    </>
  );
}
```

#### Disabling Past Dates

Combine with `disabled` prop for past dates and specific blocked ranges:

```tsx
const disabledDays = [
  { before: new Date() }, // All past dates
  { dayOfWeek: [0, 6] },  // Optional: weekends (if applicable)
  // Specific booked ranges from API
  { from: new Date(2026, 0, 15), to: new Date(2026, 0, 20) },
];

<DayPicker
  mode="range"
  disabled={disabledDays}
/>
```

**Integration Notes**:
- Use Tailwind CSS for styling instead of default CSS
- Wrap in `DateRangePicker.tsx` component for reuse
- Connect to availability API for dynamic blocked dates

---

### 2. React Leaflet (Interactive Maps)

**Packages**: `react-leaflet`, `leaflet` | **Version**: 4.x | **License**: BSD-2-Clause

**Why Selected** (per spec clarification):
- Free, no API key required (OpenStreetMap tiles)
- Lightweight compared to Google Maps SDK
- Good React integration with hooks
- Sufficient for POI markers and basic interactions

#### Basic Map with Marker Pattern

For FR-024 (display interactive map with property position):

```tsx
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

function PropertyMap() {
  // Quesada, Alicante coordinates
  const propertyPosition: [number, number] = [38.0731, -0.8167]

  return (
    <MapContainer
      center={propertyPosition}
      zoom={14}
      scrollWheelZoom={false}
      style={{ height: '400px', width: '100%' }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Marker position={propertyPosition}>
        <Popup>
          <strong>Quesada Apartment</strong><br />
          Your vacation rental
        </Popup>
      </Marker>
    </MapContainer>
  )
}
```

#### POI Markers with Popups Pattern

For FR-025/FR-026 (show nearby POIs with details):

```tsx
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'

interface POI {
  id: string
  name: string
  category: 'beach' | 'golf' | 'restaurant' | 'attraction'
  coordinates: [number, number]
  distance: string
  description: string
}

function LocationMapWithPOIs({ pois }: { pois: POI[] }) {
  const propertyPosition: [number, number] = [38.0731, -0.8167]

  return (
    <MapContainer center={propertyPosition} zoom={13}>
      <TileLayer
        attribution='&copy; OpenStreetMap contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {/* Property marker */}
      <Marker position={propertyPosition}>
        <Popup>Quesada Apartment</Popup>
      </Marker>

      {/* POI markers */}
      {pois.map((poi) => (
        <Marker
          key={poi.id}
          position={poi.coordinates}
          eventHandlers={{
            click: () => console.log(`POI clicked: ${poi.name}`),
          }}
        >
          <Popup>
            <strong>{poi.name}</strong>
            <br />
            <em>{poi.category}</em> • {poi.distance}
            <br />
            {poi.description}
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  )
}
```

#### Event Handling Pattern

For interactive map features (FR-027):

```tsx
import { useMapEvents } from 'react-leaflet'

function MapEventHandler() {
  const map = useMapEvents({
    click(e) {
      console.log('Map clicked at:', e.latlng)
    },
    zoomend() {
      console.log('Zoom level:', map.getZoom())
    },
  })
  return null
}

// Usage inside MapContainer
<MapContainer>
  <MapEventHandler />
  {/* ... other components */}
</MapContainer>
```

**Integration Notes**:
- Import Leaflet CSS in layout or component
- Use dynamic import (`next/dynamic`) with `ssr: false` for Next.js
- Consider custom marker icons for different POI categories
- POI data fetched from backend API (new endpoint needed)

---

### 3. @hey-api/openapi-ts (API Client Generation)

**Package**: `@hey-api/openapi-ts` | **Version**: Latest | **License**: MIT

**Why Selected** (per spec FR-014/FR-014a):
- Auto-generates type-safe TypeScript client from FastAPI OpenAPI spec
- Ensures frontend-backend contract alignment
- Supports Fetch API (browser-native, no axios dependency)
- Integrates with build pipeline

#### Configuration Pattern

Create `openapi-ts.config.ts` in frontend root:

```typescript
import { defineConfig } from '@hey-api/openapi-ts';

export default defineConfig({
  input: '../backend/api/openapi.json', // FastAPI generated spec
  output: 'src/lib/api-client',
  plugins: ['@hey-api/client-fetch'],
});
```

#### Package.json Script

```json
{
  "scripts": {
    "generate:api": "openapi-ts"
  }
}
```

#### Client Configuration Pattern

Configure the generated client with base URL:

```typescript
// src/lib/api-client/config.ts
import { client } from './client.gen';

client.setConfig({
  baseUrl: process.env.NEXT_PUBLIC_API_URL || 'https://api.example.com',
});

export { client };
```

#### Usage Pattern

The generated SDK provides type-safe functions:

```typescript
import { getAvailability, createReservation } from '@/lib/api-client';

// Type-safe API calls
async function checkDates(checkIn: string, checkOut: string) {
  const response = await getAvailability({
    query: { check_in: checkIn, check_out: checkOut },
  });

  if (response.data) {
    return response.data; // Fully typed response
  }
  throw new Error(response.error?.message);
}
```

#### Per-Request Configuration

Override configuration for specific calls:

```typescript
const response = await getAvailability({
  baseUrl: 'https://staging-api.example.com', // Override for testing
  query: { check_in: '2026-01-15', check_out: '2026-01-20' },
});
```

**Integration Notes**:
- Run `yarn generate:api` after backend API changes
- Add to CI/CD to detect contract drift
- Generated types eliminate manual interface maintenance
- Works with existing CloudFront + API Gateway setup

---

## Existing Component Reuse Analysis

### PhotoGallery (Can Reuse)

The existing `frontend/src/components/agent/PhotoGallery.tsx` provides:
- Full lightbox implementation with overlay
- Keyboard navigation (arrow keys, escape)
- Touch gesture support (swipe)
- Thumbnail grid view
- Image captions

**Satisfies**: FR-015 through FR-019 (gallery requirements)

**Recommendation**: Extract to shared location (`components/shared/`) or import directly from `components/agent/`.

### AvailabilityCalendar (Cannot Reuse for Booking)

The existing `frontend/src/components/agent/AvailabilityCalendar.tsx` is:
- Display-only (shows availability status)
- Not a date picker (no selection capability)
- Designed for agent tool responses

**Does NOT satisfy**: FR-007 (visual date picker for selection)

**Recommendation**: Use React Day Picker for the booking widget; keep AvailabilityCalendar for agent display.

### ai-elements (Chat UI Only)

Components in `frontend/src/components/ai-elements/`:
- `Conversation`, `ConversationContent`, `ConversationEmptyState`
- `Message`, `MessageContent`, `MessageResponse`, `MessageLoading`
- `Input`, `PromptInputTextarea`, `PromptInputSubmit`

**Scope**: Chat/conversation UI patterns only

**Does NOT satisfy**: Booking forms, date pickers, maps, property cards

**Recommendation**: ai-elements remains for `/agent` page; new components for booking frontend.

---

## Architecture Decisions

### 1. Next.js Dynamic Imports for Leaflet

Leaflet requires browser APIs (`window`). Use dynamic import:

```tsx
// components/map/LocationMap.tsx
import dynamic from 'next/dynamic'

const LocationMap = dynamic(
  () => import('./LocationMapClient'),
  { ssr: false, loading: () => <div>Loading map...</div> }
)

export default LocationMap
```

### 2. API Client in Static Export

Since the frontend is a static export (S3 + CloudFront):
- API client calls happen client-side only
- Base URL configured via `NEXT_PUBLIC_API_URL` env var
- No API routes in frontend (all backend calls to API Gateway)

### 3. Form State Management

For the booking form (FR-012), use React Hook Form with Zod:
- Type-safe form validation
- Integrates with generated API types
- Consistent with existing patterns

---

## Dependencies to Add

```json
{
  "dependencies": {
    "react-day-picker": "^9.0.0",
    "date-fns": "^3.0.0",
    "react-leaflet": "^4.2.0",
    "leaflet": "^1.9.0"
  },
  "devDependencies": {
    "@hey-api/openapi-ts": "^0.60.0",
    "@types/leaflet": "^1.9.0"
  }
}
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Leaflet SSR issues | Medium | Low | Dynamic import with `ssr: false` |
| OpenAPI spec drift | Low | Medium | CI check comparing generated vs committed |
| Date picker accessibility | Low | Medium | React Day Picker is WCAG compliant by default |
| Map tile loading (OSM) | Low | Low | OSM is highly available; add loading state |
| POI API latency | Medium | Low | Client-side caching, skeleton loading |

---

## Next Steps

1. **Phase 1**: Create data model for POI entity
2. **Phase 1**: Define API contract for POI endpoint
3. **Phase 1**: Generate quickstart guide for development setup
4. **Implementation**: Start with homepage (P1), then booking flow (P2)
