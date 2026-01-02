# Implementation Plan: Complete Booking Frontend

**Branch**: `009-booking-frontend` | **Date**: 2026-01-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/009-booking-frontend/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Transform the existing agent-first booking platform into a complete traditional booking frontend while preserving the AI agent at `/agent`. The primary entry point becomes a property homepage with hero imagery, booking widget, and gallery. Users can complete bookings through form-based flows (React Day Picker for dates, generated TypeScript client from FastAPI OpenAPI for API calls) or continue using the conversational agent. The location page will be enhanced with Leaflet/OpenStreetMap interactive maps showing POIs from DynamoDB.

## Technical Context

**Language/Version**: TypeScript 5.7+ (strict mode), Next.js 14+ (App Router, static export)
**Primary Dependencies**: React Day Picker, Leaflet + React-Leaflet, Generated OpenAPI TypeScript Client, Vercel AI SDK v6, ai-elements, Lucide React, Tailwind CSS, shadcn/ui (for non-agent pages), yet-another-react-lightbox
**Storage**: DynamoDB (POIs table via backend API), existing backend services (availability, pricing, reservations)
**Testing**: Vitest (unit), Playwright (E2E), Testing Library
**Target Platform**: S3 + CloudFront static export (browser-only, no API routes)
**Project Type**: Web application (frontend-focused feature, backend POI endpoint addition)
**Performance Goals**: Lighthouse 80+ performance, <3s homepage load on 3G, <5s gallery load with lazy loading
**Constraints**: Single property (4 guests max), mobile-first responsive, WCAG AA accessibility, graceful JS degradation
**Scale/Scope**: 5-6 new/modified pages, 8-10 new components, 1 new API endpoint (POIs)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Test-First Development | ✅ PASS | Will write tests before components for booking widget, gallery, map |
| II. Simplicity & YAGNI | ✅ PASS | Single property, form-based booking - no premature abstractions |
| III. Type Safety | ✅ PASS | Generated OpenAPI client ensures type-safe API calls, strict TS |
| IV. Observability | ✅ PASS | Structured logging for booking flow, correlation IDs exist |
| V. Incremental Delivery | ✅ PASS | Prioritized user stories (P1-P5), each independently deployable |
| VI. Technology Stack | ✅ PASS | Uses AI SDK v6, ai-elements, Strands (backend unchanged) |
| VI.a. UI Component Research | ✅ PASS | Must document ai-elements catalog research below |

### ai-elements Catalog Research

**Existing ai-elements components (from `frontend/src/components/ai-elements/`):**
- `Conversation`, `ConversationContent`, `ConversationEmptyState`, `ConversationScrollButton`
- `Message`, `MessageContent`, `MessageResponse`, `MessageActions`, `MessageAction`, `MessageLoading`
- `Input`, `PromptInputTextarea`, `PromptInputSubmit`, `PromptInputWrapper`

**Existing agent components (from `frontend/src/components/agent/`):**
- `AvailabilityCalendar` - Custom calendar showing availability status
- `BookingSummaryCard` - Reservation summary display
- `VerificationCodeInput` - OTP verification UI
- `PhotoGallery` - Full lightbox implementation with keyboard nav
- `RichContentRenderer` - Detects and routes structured content

**Component Decisions:**

| New Component Needed | ai-elements Applicability | Decision |
|---------------------|---------------------------|----------|
| Date range picker (booking widget) | None - ai-elements is for chat UI | Use React Day Picker (per spec FR-007) |
| Price breakdown card | None - domain-specific | Custom component |
| Booking form | None - standard forms | Custom with Tailwind |
| Hero section | None - page layout | Custom component |
| Interactive map | None - geospatial | Leaflet + React-Leaflet |
| Gallery (homepage) | PhotoGallery exists | Extend existing PhotoGallery |
| Property highlights | None - content display | Custom component |

**Justification**: ai-elements is a chat/conversation UI library, not a general UI component library. The booking frontend requires traditional web UI patterns (forms, date pickers, maps, cards) that are outside ai-elements' scope. The PhotoGallery component already exists in the agent components and will be reused.

## Project Structure

### Documentation (this feature)

```text
specs/009-booking-frontend/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── poi-api.yaml     # POI endpoint OpenAPI contract
│   └── booking-form.schema.ts  # Booking form validation schema
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── app/
│   │   ├── page.tsx              # Homepage (new - hero, booking widget, highlights)
│   │   ├── agent/
│   │   │   └── page.tsx          # Agent chat (moved from root)
│   │   ├── gallery/
│   │   │   └── page.tsx          # Full gallery page (new)
│   │   ├── location/
│   │   │   └── page.tsx          # Enhanced with Leaflet map (modified)
│   │   └── book/
│   │       └── page.tsx          # Booking flow (new)
│   ├── components/
│   │   ├── booking/              # New booking components
│   │   │   ├── BookingWidget.tsx    # Date picker + price preview
│   │   │   ├── BookingForm.tsx      # Guest details form
│   │   │   ├── PriceBreakdown.tsx   # Price calculation display
│   │   │   └── DateRangePicker.tsx  # React Day Picker wrapper
│   │   ├── home/                 # New homepage components
│   │   │   ├── Hero.tsx             # Hero section
│   │   │   ├── PropertyHighlights.tsx
│   │   │   └── QuickLinks.tsx
│   │   ├── map/                  # New map components
│   │   │   ├── LocationMap.tsx      # Leaflet map wrapper
│   │   │   └── POIMarker.tsx        # Point of interest marker
│   │   ├── agent/                # Existing (unchanged)
│   │   ├── ai-elements/          # Existing (unchanged)
│   │   └── layout/               # Existing (nav updated)
│   ├── lib/
│   │   └── api-client/           # Generated OpenAPI client (new)
│   └── types/
│       └── poi.ts                # POI types (new)
└── tests/
    ├── unit/
    │   └── components/
    │       └── booking/
    └── e2e/
        └── booking-flow.spec.ts

backend/
├── api/
│   └── src/api/
│       └── routes/
│           └── poi.py            # New POI endpoint
└── shared/
    └── src/shared/
        └── services/
            └── poi.py            # POI service (DynamoDB)

infrastructure/
└── modules/
    └── dynamodb/
        └── poi-table.tf          # POI DynamoDB table (new)
```

**Structure Decision**: Frontend-focused feature with minimal backend additions (POI endpoint + table). The existing backend workspace structure (api, shared, agent) is preserved. New frontend components are organized by domain (booking, home, map) following existing patterns.

## Complexity Tracking

> **No constitution violations to justify** - all requirements fit within existing stack and patterns.

| Consideration | Decision | Rationale |
|---------------|----------|-----------|
| React Day Picker vs existing AvailabilityCalendar | Use React Day Picker | Spec explicitly requires it (FR-007); existing calendar is display-only, not a date picker |
| Leaflet vs Google Maps | Leaflet + OSM | Spec requires free solution (FR-024); no API key needed |
| OpenAPI client generation | openapi-typescript-codegen or similar | Ensures type safety per spec (FR-014, FR-014a) |
