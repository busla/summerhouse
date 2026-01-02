# Tasks: Complete Booking Frontend

**Feature**: 009-booking-frontend
**Generated**: 2026-01-01
**Source**: spec.md, plan.md, data-model.md, contracts/

## Overview

This task breakdown implements a complete booking frontend for the vacation rental platform. Tasks are organized by user story priority (P1-P5), enabling independent implementation and testing of each vertical slice.

### User Story Summary

| ID | Priority | Name | Description |
|----|----------|------|-------------|
| US1 | P1 | Property Discovery Homepage | Hero section, property highlights, booking widget |
| US2 | P2 | Direct Booking Flow | Date picker, price breakdown, guest form |
| US3 | P3 | Visual Property Gallery | Photo gallery with lightbox |
| US4 | P4 | AI Agent Chat Route | Preserve existing agent at /agent |
| US5 | P5 | Interactive Location & Map | Leaflet map with POI markers |

### Task Format

```
- [ ] T### [P?] [US?] Description
      └─ file: path/to/file.tsx
```

- **T###**: Sequential task ID
- **[P?]**: Priority (P0=blocker, P1-P5=user story priority)
- **[US?]**: User story reference (US1-US5, or "Foundation" for shared work)

---

## Phase 1: Project Setup

> Dependencies and configuration required before feature work.

### 1.0 shadcn/ui Setup (REQUIRED: spec.md clarification line 17)

> **Context**: shadcn/ui provides accessible, customizable components for non-agent pages. Agent components (/agent route) SHALL NOT use shadcn - they use ai-elements exclusively.

- [x] T000a [P0] [Foundation] Verify Tailwind CSS configuration exists and is functional
      └─ file: `frontend/tailwind.config.ts`
      └─ Verify: postcss.config.mjs configured, globals.css imports Tailwind directives
      └─ Action: Check existing config; create if missing

- [x] T000b [P0] [Foundation] Install shadcn/ui dependencies
      └─ cmd: `cd frontend && yarn add clsx tailwind-merge class-variance-authority`
      └─ Note: `lucide-react` and `zod` already installed - no action needed

- [x] T000c [P0] [Foundation] Initialize shadcn/ui configuration
      └─ cmd: `cd frontend && npx shadcn@latest init`
      └─ Choices: New York style, CSS variables, baseColor slate
      └─ Creates: `components.json`, updates `tailwind.config.ts`, `globals.css`

- [x] T000d [P0] [Foundation] Install core shadcn/ui components for booking forms
      └─ cmd: `cd frontend && npx shadcn@latest add button input card select label dialog`
      └─ Creates: `frontend/src/components/ui/{button,input,card,select,label,dialog}.tsx`

- [x] T000e [P0] [Foundation] Install shadcn/ui Form component for validated forms
      └─ cmd: `cd frontend && npx shadcn@latest add form`
      └─ Creates: `frontend/src/components/ui/form.tsx`
      └─ Depends on: react-hook-form, @hookform/resolvers (auto-installed)

- [x] T000f [P0] [Foundation] Install yet-another-react-lightbox for gallery
      └─ cmd: `cd frontend && yarn add yet-another-react-lightbox`
      └─ Used by: T036 (Lightbox component)

### 1.1 Feature Dependencies

- [x] T001 [P0] [Foundation] Install React Day Picker package for date range selection
      └─ cmd: `cd frontend && yarn add react-day-picker date-fns`

- [x] T002 [P0] [Foundation] Install Leaflet and React-Leaflet packages for interactive maps
      └─ cmd: `cd frontend && yarn add leaflet react-leaflet @types/leaflet`

- [x] T003 [P0] [Foundation] Add Leaflet CSS import to root layout for map styling
      └─ file: `frontend/src/app/layout.tsx`
      └─ Add: `import 'leaflet/dist/leaflet.css'`

- [x] T004 [P0] [Foundation] Add React Day Picker CSS import to root layout
      └─ file: `frontend/src/app/layout.tsx`
      └─ Add: `import 'react-day-picker/style.css'`

- [x] T005 [P0] [Foundation] Create component directory structure for new features
      └─ dirs: `frontend/src/components/{booking,home,map}/`
      └─ Status: All directories exist (booking/, home/, map/)

---

## Phase 2: Foundational Components

> Shared utilities and API client generation.

- [x] T006 [P0] [Foundation] Generate TypeScript API client from backend OpenAPI spec
      └─ cmd: `cd frontend && yarn generate:api`
      └─ Creates: `frontend/src/lib/api-client/`

- [x] T007 [P0] [Foundation] Configure API client with base URL from environment
      └─ file: `frontend/src/lib/api-client/config.ts`
      └─ Use: `NEXT_PUBLIC_API_URL` env var with fallback to localhost:3001

- [x] T008 [P0] [Foundation] Create currency formatting utility for EUR prices in cents
      └─ file: `frontend/src/lib/format.ts`
      └─ Export: `formatPrice(cents: number): string` → "€120.00"

- [x] T009 [P0] [Foundation] Create date formatting utilities using date-fns
      └─ file: `frontend/src/lib/date-utils.ts`
      └─ Export: `formatDateRange`, `calculateNights`, `formatDate`

- [x] T010 [P0] [Foundation] Copy Zod booking form schema to frontend lib
      └─ from: `specs/009-booking-frontend/contracts/booking-form.schema.ts`
      └─ to: `frontend/src/lib/schemas/booking-form.schema.ts`

---

## Phase 3: US1 - Property Discovery Homepage (P1)

> Hero section, property highlights, and booking widget shell.

### 3.1 Homepage Layout

- [x] T011 [P1] [US1] Create homepage route with metadata and static generation
      └─ file: `frontend/src/app/page.tsx`
      └─ Requirements: FR-001, FR-002
      └─ Include: Hero, PropertyHighlights, QuickLinks sections

- [x] T012 [P1] [US1] Create Hero component with background image and tagline
      └─ file: `frontend/src/components/home/Hero.tsx`
      └─ Requirements: FR-001
      └─ Props: `title`, `subtitle`, `backgroundImage`, `ctaText`, `ctaHref`
      └─ Styling: Tailwind CSS classes, shadcn/ui Button for CTA

- [x] T013 [P1] [US1] Create PropertyHighlights component showing key amenities
      └─ file: `frontend/src/components/home/PropertyHighlights.tsx`
      └─ Requirements: FR-002
      └─ Display: bedrooms (2), bathrooms (1), pool (shared), A/C, WiFi, parking
      └─ Styling: Tailwind CSS classes, shadcn/ui Card for highlight items

- [x] T014 [P1] [US1] Create QuickLinks component for navigation sections
      └─ file: `frontend/src/components/home/QuickLinks.tsx`
      └─ Requirements: FR-003
      └─ Links: Gallery, Location, Book Now, Chat with Agent
      └─ Styling: Tailwind CSS classes, shadcn/ui Card for link items

### 3.2 Booking Widget (Shell)

- [x] T015 [P1] [US1] Create BookingWidget container component with date state
      └─ file: `frontend/src/components/booking/BookingWidget.tsx`
      └─ Requirements: FR-004, FR-005
      └─ Props: `onDatesChange`, `onBook`
      └─ State: `selectedRange`, `isLoading`, `error`
      └─ Styling: Tailwind CSS classes, shadcn/ui Card + Button

- [x] T016 [P1] [US1] Create BookingWidgetSkeleton for loading state
      └─ file: `frontend/src/components/booking/BookingWidgetSkeleton.tsx`
      └─ Styling: Tailwind animate-pulse classes, shadcn/ui Skeleton component

### 3.3 Navigation

- [x] T017 [P1] [US1] Update Header component with navigation links
      └─ file: `frontend/src/components/layout/Header.tsx`
      └─ Requirements: FR-006
      └─ Links: Home, Gallery, Location, Book, Agent

- [x] T018 [P1] [US1] Create Footer component with contact info and links
      └─ file: `frontend/src/components/layout/Footer.tsx`
      └─ Include: Property address, email, quick links, copyright
      └─ Styling: Tailwind CSS classes

### 3.4 Component Migration (JSX styles → Tailwind/shadcn)

> **Context**: If components T012-T018 were created with `<style jsx>` tags, they MUST be migrated to Tailwind CSS classes. This ensures consistency with shadcn/ui patterns and spec requirements.

- [x] T018a [P1] [US1] Migrate Hero.tsx from JSX styles to Tailwind CSS
      └─ file: `frontend/src/components/home/Hero.tsx`
      └─ Action: Replace `<style jsx>` block with Tailwind utility classes
      └─ Use: shadcn/ui Button for CTA buttons
      └─ Verify: Visual appearance matches original, responsive behavior preserved

- [x] T018b [P1] [US1] Migrate PropertyHighlights.tsx from JSX styles to Tailwind CSS
      └─ file: `frontend/src/components/home/PropertyHighlights.tsx`
      └─ Action: Replace `<style jsx>` block with Tailwind utility classes
      └─ Use: shadcn/ui Card if appropriate for highlight items
      └─ Verify: Grid layout, hover states, icon styling preserved

- [x] T018c [P1] [US1] Migrate QuickLinks.tsx from JSX styles to Tailwind CSS
      └─ file: `frontend/src/components/home/QuickLinks.tsx`
      └─ Action: Replace `<style jsx>` block with Tailwind utility classes
      └─ Use: shadcn/ui Card for link cards
      └─ Verify: Grid layout, hover transforms, accent styling preserved

- [x] T018d [P1] [US1] Migrate BookingWidget.tsx from JSX styles to Tailwind CSS
      └─ file: `frontend/src/components/booking/BookingWidget.tsx`
      └─ Action: Replace `<style jsx>` block with Tailwind utility classes
      └─ Use: shadcn/ui Card + Button
      └─ Verify: Compact mode variant, error display preserved

---

## Phase 4: US2 - Direct Booking Flow (P2)

> Complete booking form with date picker, pricing, and guest details.

### 4.1 Date Range Picker

- [x] T019 [P2] [US2] Create DateRangePicker component wrapping React Day Picker
      └─ file: `frontend/src/components/booking/DateRangePicker.tsx`
      └─ Requirements: FR-007, FR-008
      └─ Props: `selected`, `onSelect`, `disabled` (blocked dates), `numberOfMonths`
      └─ Features: 2-month view on desktop, 1-month on mobile

- [x] T020 [P2] [US2] Add useAvailability hook to fetch blocked dates from API
      └─ file: `frontend/src/hooks/useAvailability.ts`
      └─ Requirements: FR-008
      └─ Returns: `{ blockedDates: Date[], isLoading, error }`
      └─ Uses: `checkAvailability` from generated API client

- [x] T021 [P2] [US2] Style DateRangePicker with Tailwind CSS custom theme
      └─ file: `frontend/src/components/booking/DateRangePicker.tsx`
      └─ Match: Project color scheme, hover states, selected range highlighting

### 4.2 Price Calculation

- [x] T022 [P2] [US2] Create PriceBreakdown component showing cost details
      └─ file: `frontend/src/components/booking/PriceBreakdown.tsx`
      └─ Requirements: FR-009, FR-010
      └─ Props: `checkIn`, `checkOut`, `nightlyRate`, `cleaningFee`
      └─ Display: nights × rate, cleaning fee, total, minimum nights warning

- [x] T023 [P2] [US2] Add usePricing hook to calculate totals from API
      └─ file: `frontend/src/hooks/usePricing.ts`
      └─ Requirements: FR-009
      └─ Returns: `{ pricing, isLoading, error }`
      └─ Uses: `calculateTotal` from generated API client

- [x] T024 [P2] [US2] Integrate PriceBreakdown into BookingWidget
      └─ file: `frontend/src/components/booking/BookingWidget.tsx`
      └─ Requirements: FR-010
      └─ Show price breakdown when dates selected, loading state during fetch

### 4.3 Guest Details Form

- [x] T025 [P2] [US2] Create GuestDetailsForm component with validation
      └─ file: `frontend/src/components/booking/GuestDetailsForm.tsx`
      └─ Requirements: FR-012, FR-013
      └─ Fields: name, email, phone, numGuests (1-4 dropdown), specialRequests
      └─ Uses: Zod schema from `lib/schemas/booking-form.schema.ts`

- [x] T026 [P2] [US2] Create GuestCountSelector component (1-4 guests)
      └─ file: `frontend/src/components/booking/GuestCountSelector.tsx`
      └─ Requirements: FR-013
      └─ Props: `value`, `onChange`, `max` (4)
      └─ UI: Dropdown or stepper with +/- buttons

- [x] T027 [P2] [US2] Add form field error display using shadcn Form primitives
      └─ file: `frontend/src/components/booking/GuestFormField.tsx`
      └─ Uses: shadcn/ui Form, FormField, FormItem, FormLabel, FormControl, FormMessage
      └─ Integration: react-hook-form with Zod schema from T010
      └─ Props: Standard react-hook-form field props via FormField render
      └─ Note: shadcn Form already provides accessible error display (aria-invalid)

### 4.4 Booking Page

- [x] T028 [P2] [US2] Create /book page route with booking flow
      └─ file: `frontend/src/app/book/page.tsx`
      └─ Requirements: FR-011
      └─ Steps: Date selection → Price review → Guest details → Confirmation

- [x] T029 [P2] [US2] Create BookingForm container orchestrating full flow
      └─ file: `frontend/src/components/booking/BookingForm.tsx`
      └─ Requirements: FR-014
      └─ Combines: DateRangePicker, PriceBreakdown, GuestDetailsForm
      └─ Handles: Form submission to createReservation API

- [x] T030 [P2] [US2] Add useCreateReservation mutation hook
      └─ file: `frontend/src/hooks/useCreateReservation.ts`
      └─ Requirements: FR-014
      └─ Returns: `{ mutate, isLoading, error, data }`
      └─ Uses: `createReservation` from generated API client

- [x] T031 [P2] [US2] Create BookingConfirmation component for success state
      └─ file: `frontend/src/components/booking/BookingConfirmation.tsx`
      └─ Requirements: FR-014a
      └─ Props: `reservation` (from API response)
      └─ Display: Confirmation number, dates, guest name, next steps

- [x] T031a [P2] [US2] Add minimum nights validation to booking form schema
      └─ file: `frontend/src/lib/schemas/booking-form.schema.ts`
      └─ Requirements: FR-011
      └─ Add: `minimumNightsSchema` with seasonal rules refinement
      └─ Validation: Check nights >= season minimum (from usePricing hook)
      └─ Display: Error message in PriceBreakdown when minimum not met

---

## Phase 5: US3 - Visual Property Gallery (P3)

> Photo gallery with lightbox and keyboard navigation.
>
> **Simplified Approach**: Photos are served from the existing S3 bucket (same as frontend) via CloudFront. Frontend uses hardcoded paths `/photos/01.jpg`, `/photos/02.jpg`, etc. No photos API required.

- [x] T032 [P3] [US3] Add mock property photos to frontend public directory
      └─ dir: `frontend/public/photos/`
      └─ Files: `01.jpg` through `06.jpg` (6 photos: living, bedroom, kitchen, bathroom, pool, exterior)
      └─ Status: Complete - photos exist at /photos/01.jpg through /photos/06.jpg

- [x] T033 [P3] [US3] Create hardcoded gallery image data with captions
      └─ file: `frontend/src/app/gallery/page.tsx` (inline data)
      └─ Status: Complete - data defined inline in page component instead of separate file
      └─ Structure: `{ src, alt, title, description }` array

- [x] T034 [P3] [US3] Create /gallery page route
      └─ file: `frontend/src/app/gallery/page.tsx`
      └─ Requirements: FR-015
      └─ Status: Complete - responsive grid layout with thumbnail cards

- [x] T035 [P3] [US3] Extend existing PhotoGallery component with lightbox
      └─ file: `frontend/src/app/gallery/page.tsx`
      └─ Requirements: FR-016, FR-017
      └─ Status: Complete - uses `yet-another-react-lightbox` with Thumbnails plugin

- [x] T036 [P3] [US3] Create Lightbox component with navigation
      └─ file: `frontend/src/app/gallery/page.tsx`
      └─ Requirements: FR-017, FR-018
      └─ Status: Complete - `yet-another-react-lightbox` provides prev/next, close, backdrop click

- [x] T037 [P3] [US3] Add keyboard navigation to Lightbox (Esc, arrows)
      └─ file: `frontend/src/app/gallery/page.tsx`
      └─ Requirements: FR-018
      └─ Status: Complete - built into `yet-another-react-lightbox` library

- [x] T038 [P3] [US3] Add touch swipe gestures for mobile lightbox
      └─ file: `frontend/src/app/gallery/page.tsx`
      └─ Requirements: FR-019
      └─ Status: Complete - built into `yet-another-react-lightbox` library

---

## Phase 6: US4 - AI Agent Chat Route (P4)

> Preserve existing agent functionality at /agent route.
>
> **⚠️ SCOPE CONSTRAINT**: This phase involves ROUTING ONLY. The existing agent code (ai-elements, AI SDK v6, chat components) SHALL NOT be modified. Agent components MUST continue using ai-elements - they SHALL NOT adopt shadcn/ui.

- [x] T039 [P4] [US4] Create /agent page route by copying existing homepage agent
      └─ file: `frontend/src/app/agent/page.tsx`
      └─ Requirements: FR-020
      └─ Action: Copy (not modify) existing agent page to new route
      └─ Note: NO modifications to agent component code - route change only

- [x] T040 [P4] [US4] Update agent page metadata for SEO
      └─ file: `frontend/src/app/agent/page.tsx`
      └─ Requirements: FR-020
      └─ Title: "Chat with Our AI Concierge | [Property Name]"
      └─ Description: Describe agent capabilities
      └─ Note: Metadata only - DO NOT modify agent component imports/logic

- [x] T041 [P4] [US4] Verify ChatInterface component works at new route
      └─ Requirements: FR-021, FR-022
      └─ Action: Manual verification only - NO code changes
      └─ Verify: All existing functionality preserved (auth, messaging, tools)
      └─ Test: Send message, verify response, check conversation persistence

- [x] T042 [P4] [US4] Add "Chat with Agent" link in navigation
      └─ file: `frontend/src/components/layout/Header.tsx`
      └─ Requirements: FR-023
      └─ Link to: `/agent` route in main navigation

---

## Phase 7: US5 - Interactive Location & Map (P5)

> Leaflet map with property marker and POI markers.
>
> **⏸️ DEFERRED**: Location page implemented with Google Maps iframe. Full Leaflet + POI implementation deferred for future enhancement.

### 7.1 Backend: POI Endpoint

- [~] T043 [P5] [US5] [DEFERRED] Create POI Pydantic model
      └─ file: `backend/shared/src/shared/models/poi.py`
      └─ Based on: `specs/009-booking-frontend/data-model.md`
      └─ Classes: `POICategory` enum, `POI` model, `POIResponse` model

- [~] T044 [P5] [US5] [DEFERRED] Create POI DynamoDB service
      └─ file: `backend/shared/src/shared/services/poi.py`
      └─ Methods: `list_pois(category?)`, `get_poi(poi_id)`
      └─ Uses: Singleton DynamoDB pattern from `get_dynamodb_service()`

- [~] T045 [P5] [US5] [DEFERRED] Create POI API route
      └─ file: `backend/api/src/api/routes/poi.py`
      └─ Endpoints: `GET /pois`, `GET /pois/{poi_id}`
      └─ Based on: `specs/009-booking-frontend/contracts/poi-api.yaml`

- [~] T046 [P5] [US5] [DEFERRED] Register POI router in FastAPI app
      └─ file: `backend/api/src/api/main.py`
      └─ Add: `app.include_router(poi_router, prefix="/api")`

- [~] T047 [P5] [US5] [DEFERRED] Add POI DynamoDB table to Terraform
      └─ file: `infrastructure/modules/dynamodb/poi-table.tf`
      └─ Based on: `specs/009-booking-frontend/data-model.md` Terraform section
      └─ Table: `booking-{env}-pois` with category-order-index GSI

- [~] T048 [P5] [US5] [DEFERRED] Create POI seed data JSON file
      └─ file: `backend/shared/data/pois.json`
      └─ Based on: Sample data from `data-model.md`
      └─ Include: 6+ POIs across beach, golf, restaurant, attraction categories

- [~] T049 [P5] [US5] [DEFERRED] Create POI seed script
      └─ file: `backend/shared/src/shared/scripts/seed_pois.py`
      └─ Usage: `uv run python -m shared.scripts.seed_pois --env dev`
      └─ Reads: `pois.json`, writes to DynamoDB table

- [~] T050 [P5] [US5] [DEFERRED] Add seed:pois task to Taskfile
      └─ file: `Taskfile.yaml`
      └─ Commands: `seed:pois:dev`, `seed:pois:prod`

### 7.2 Frontend: Map Components

- [x] T051 [P5] [US5] Create /location page route
      └─ file: `frontend/src/app/location/page.tsx`
      └─ Requirements: FR-024
      └─ Status: Complete - uses Google Maps iframe (simpler than Leaflet approach)

- [~] T052 [P5] [US5] [DEFERRED] Create LocationMapClient component (client-side only)
      └─ file: `frontend/src/components/map/LocationMapClient.tsx`
      └─ Requirements: FR-024, FR-025
      └─ Uses: MapContainer, TileLayer from react-leaflet
      └─ Props: `center`, `zoom`, `pois`

- [~] T053 [P5] [US5] [DEFERRED] Create LocationMap wrapper with dynamic import (SSR-safe)
      └─ file: `frontend/src/components/map/LocationMap.tsx`
      └─ Requirements: FR-024
      └─ Uses: `dynamic(() => import('./LocationMapClient'), { ssr: false })`

- [~] T054 [P5] [US5] [DEFERRED] Create POIMarker component with category icons
      └─ file: `frontend/src/components/map/POIMarker.tsx`
      └─ Requirements: FR-025, FR-026
      └─ Props: `poi` (from API)
      └─ Features: Category-specific icon, click to show popup

- [~] T055 [P5] [US5] [DEFERRED] Create PropertyMarker component for apartment location
      └─ file: `frontend/src/components/map/PropertyMarker.tsx`
      └─ Requirements: FR-024
      └─ Location: Quesada coordinates (38.0731, -0.8167)
      └─ Style: Distinct icon, "You are here" popup

- [~] T056 [P5] [US5] [DEFERRED] Create POIPopup component for marker details
      └─ file: `frontend/src/components/map/POIPopup.tsx`
      └─ Requirements: FR-026
      └─ Props: `poi`
      └─ Display: name, description, distance_text, external link

- [~] T057 [P5] [US5] [DEFERRED] Add usePOIs hook to fetch POI data
      └─ file: `frontend/src/hooks/usePOIs.ts`
      └─ Requirements: FR-025
      └─ Returns: `{ pois, isLoading, error }`
      └─ Uses: `listPOIs` from generated API client

- [~] T058 [P5] [US5] [DEFERRED] Create POI category filter component
      └─ file: `frontend/src/components/map/POICategoryFilter.tsx`
      └─ Requirements: FR-027 (optional enhancement)
      └─ Props: `categories`, `selected`, `onChange`
      └─ UI: Checkbox or button group to filter visible markers

- [~] T059 [P5] [US5] [DEFERRED] Create map icon assets for each POI category
      └─ dir: `frontend/public/icons/map/`
      └─ Files: `beach.svg`, `golf.svg`, `restaurant.svg`, `attraction.svg`, `shopping.svg`, `transport.svg`, `property.svg`

---

## Phase 8: Polish & Accessibility ⏸️ DEFERRED

> Performance, accessibility, and final touches.
>
> **Status**: Deferred to focus on next feature. Core functionality complete.

### 8.1 Accessibility

- [~] T060 [P3] [Foundation] [DEFERRED] Add skip-to-content link for keyboard navigation
      └─ file: `frontend/src/components/layout/SkipLink.tsx`
      └─ Requirements: FR-031
      └─ Position: Hidden until focused, links to #main-content

- [~] T061 [P3] [Foundation] [DEFERRED] Ensure all interactive elements have focus states
      └─ file: `frontend/src/app/globals.css`
      └─ Requirements: FR-031
      └─ Add: Focus-visible ring styles for buttons, links, inputs

- [~] T062 [P3] [Foundation] [DEFERRED] Add aria-labels to icon-only buttons
      └─ files: Various components with icon buttons
      └─ Requirements: FR-032
      └─ Check: Lightbox nav, chat FAB, map controls

### 8.2 Performance

- [~] T063 [P2] [Foundation] [DEFERRED] Add Next.js Image optimization to gallery
      └─ file: `frontend/src/components/gallery/PhotoGallery.tsx`
      └─ Requirements: FR-028
      └─ Use: next/image with priority for above-fold images

- [~] T064 [P2] [Foundation] [DEFERRED] Implement lazy loading for below-fold content
      └─ file: `frontend/src/app/page.tsx`
      └─ Requirements: FR-029
      └─ Use: Intersection Observer or Next.js dynamic imports

- [~] T065 [P2] [Foundation] [DEFERRED] Verify Core Web Vitals targets
      └─ Requirements: FR-028, FR-029, FR-030
      └─ Targets: LCP < 2.5s, FID < 100ms, CLS < 0.1
      └─ cmd: `npx lighthouse http://localhost:3000 --view`

### 8.3 Testing Edge Cases

- [~] T066 [P2] [US2] [DEFERRED] Add E2E test for concurrent booking conflict scenario
      └─ file: `frontend/tests/e2e/booking-concurrent.spec.ts`
      └─ Scenario: Two users attempt to book same dates simultaneously
      └─ Test: First booking succeeds, second receives clear conflict error
      └─ Verify: Error message explains dates became unavailable, suggests alternatives
      └─ Edge case from spec: "What happens if a user tries to book dates that become unavailable while filling the form?"

### 8.4 Documentation

- [~] T067 [P3] [Foundation] [DEFERRED] Update quickstart.md with actual implementation notes
      └─ file: `specs/009-booking-frontend/quickstart.md`
      └─ Add: Any learnings, gotchas, or deviations from plan

---

## Dependency Graph

```
Phase 1 (Setup)
    │
    ▼
Phase 2 (Foundation)
    │
    ├──────────────────────────────────────────┐
    ▼                                          ▼
Phase 3 (US1 Homepage)                   Phase 7.1 (Backend POI)
    │                                          │
    ▼                                          ▼
Phase 4 (US2 Booking)                    Phase 7.2 (Frontend Map)
    │                                          │
    ▼                                          │
Phase 5 (US3 Gallery)                          │
    │                                          │
    ▼                                          │
Phase 6 (US4 Agent)                            │
    │                                          │
    └──────────────────┬───────────────────────┘
                       ▼
                Phase 8 (Polish)
```

**Key Dependencies:**
- T006 (API client) blocks all API-dependent tasks (T020, T023, T030, T057)
- T043-T050 (POI backend) blocks T051-T059 (Map frontend)
- T015 (BookingWidget shell) blocks T019-T024 (Date picker + pricing)
- T032-T033 (Photos + gallery data) blocks T034-T038 (Gallery page + lightbox)
- Gallery (Phase 5) has NO backend dependency - uses hardcoded static photos

---

## Verification Checklist

After completing all tasks, verify:

- [x] Homepage loads with hero, highlights, and booking widget
- [x] Date picker shows blocked dates from API
- [x] Price breakdown updates when dates change
- [x] Booking form validates and submits to API
- [x] Gallery opens lightbox with keyboard/touch navigation (uses yet-another-react-lightbox)
- [x] Agent chat works at /agent route
- [~] Location page shows map (uses Google Maps iframe - different from spec's Leaflet approach)
- [ ] POI markers with Leaflet (Phase 7 backend/frontend not implemented - location uses iframe instead)
- [ ] All pages pass Lighthouse accessibility audit (Phase 8 not verified)
- [ ] Core Web Vitals meet targets (Phase 8 not verified)

---

## Statistics

| Metric | Count |
|--------|-------|
| Total Tasks | 68 |
| P0 (Foundation) | 10 |
| P1 (US1 Homepage) | 8 |
| P2 (US2 Booking) | 14 |
| P3 (US3 Gallery) | 7 |
| P4 (US4 Agent) | 4 |
| P5 (US5 Map) | 17 |
| Polish Tasks | 8 |
| Phases | 8 |

---

*Generated by speckit.tasks from design artifacts*
