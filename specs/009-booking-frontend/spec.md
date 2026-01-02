# Feature Specification: Complete Booking Frontend

**Feature Branch**: `009-booking-frontend`
**Created**: 2026-01-01
**Status**: Draft
**Input**: User description: "The frontend was originally designed as an agent-first booking platform but recent development requires me to design a complete booking frontend. The agent shall not be removed, just be available at the /agent route"

## Clarifications

### Session 2026-01-01

- Q: How should the frontend call backend APIs (FR-014)? → A: Generated TypeScript client from FastAPI OpenAPI spec (type-safe, auto-updated)
- Q: Which date picker library for booking widget (FR-007, FR-031)? → A: React Day Picker (lightweight, accessible, Tailwind-friendly)
- Q: Which map provider for location page (FR-024-027)? → A: Leaflet + OpenStreetMap (free, lightweight, sufficient for POI markers)
- Q: Where does map POI data come from (FR-025-026)? → A: DynamoDB table via API (dynamic, requires backend endpoint)
- Q: How is email verified after form booking submission? → A: Reuse existing Cognito email verification (consistent with agent flow)
- Q: Should we use shadcn/ui or build custom components (FR-012, FR-007)? → A: Adopt shadcn/ui with Tailwind CSS for non-agent pages (Homepage, Gallery, Book, Location, placeholders). Use pre-built accessible form components (Input, Button, Select, Label), dialog primitives. Requires migrating 13 existing components to Tailwind classes. `lucide-react` and `zod` already installed - compatible with shadcn patterns. **EXCEPTION: Agent components (`/agent` route) SHALL NOT use shadcn - must use ai-elements and AI SDK v6 exclusively.**
- Q: Which library for photo lightbox/gallery (FR-016, FR-017, FR-018)? → A: Use `yet-another-react-lightbox` (~15KB). Full-featured: keyboard nav, swipe, pinch-to-zoom, thumbnails. TypeScript support, customizable styling to match shadcn aesthetic.
- Q: Where do property photos come from (FR-015, FR-019)? → A: S3 bucket via API endpoint. Backend exposes `/api/photos` returning photo URLs and captions from DynamoDB metadata. Photos stored in S3, served via CloudFront. Requires: DynamoDB `photos` table, S3 bucket, API endpoint, photo upload mechanism (AWS console initially).
- Q: Which pages are MVP scope (FR-006)? → A: Booking-critical pages only: Homepage (`/`), Gallery (`/gallery`), Book (`/book`), Location (`/location`), Agent (`/agent`). Other pages (Pricing, About, Area Guide, FAQ, Contact) get placeholder "Coming Soon" pages for MVP. Navigation shows all links but non-MVP pages display placeholder.
- Q: How is booking form state preserved on page refresh? → A: Session storage (persists form data across refresh within browser session, clears on tab close)
- Q: What metadata should be stored per photo in DynamoDB (FR-015, FR-019)? → A: Minimal schema: photo_id (PK), url, caption, display_order, room_type (5 fields)
- Q: Is modifying the existing agent code in scope (FR-020-023)? → A: **NO. Modifying agent code is OUT OF SCOPE.** The agent already uses ai-elements and AI SDK v6. FR-020-023 are about routing/moving the existing page to `/agent`, NOT rewriting agent components. Agent code remains unchanged; only the route/URL changes.

## Out of Scope

- **Modifying agent code**: The existing agent implementation (ai-elements, AI SDK v6, chat components) SHALL NOT be modified. Only the route changes from `/` to `/agent`.
- **Rewriting agent components**: Agent components already use ai-elements/AI SDK v6 - this is preserved, not reimplemented.
- **Non-MVP pages content**: Pricing, About, Area Guide, FAQ, Contact pages get placeholder content only.
- **Photo upload UI**: Photo management is done via AWS Console for MVP.
- **Payment processing**: Remains mocked per existing implementation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Property Discovery Homepage (Priority: P1)

A potential guest visits the website and immediately sees an attractive, professional vacation rental homepage showcasing the Quesada apartment. They see hero imagery, key property highlights (bedrooms, pool, location), a prominent availability checker, and quick access to pricing information - all without needing to engage in conversation with an AI agent.

**Why this priority**: This is the new primary entry point. The homepage must make an immediate positive impression, showcase the property effectively, and provide clear pathways to check availability and make bookings. It replaces the chat-first experience while maintaining professional vacation rental website standards.

**Independent Test**: Can be fully tested by navigating to the homepage and verifying all property highlights, hero imagery, and navigation elements display correctly without any agent interaction.

**Acceptance Scenarios**:

1. **Given** a visitor lands on the website, **When** the page loads, **Then** they see an attractive hero section with property photos and a clear value proposition.

2. **Given** a visitor views the homepage, **When** they scroll, **Then** they see key property highlights (bedrooms, guests capacity, amenities icons).

3. **Given** a visitor wants to check availability, **When** they look for a booking widget, **Then** they find a prominent date picker/availability checker above the fold or easily accessible.

4. **Given** a visitor wants to learn more, **When** they look at the homepage, **Then** they see quick links to pricing, location, and property details.

5. **Given** a visitor prefers AI assistance, **When** they look for chat options, **Then** they see a clear path to the AI agent (link or chat widget trigger).

---

### User Story 2 - Direct Booking Flow (Priority: P2)

A guest has decided to book and wants to complete the entire reservation through a traditional web form interface. They select dates using a calendar, see a price breakdown, enter their details, and submit a booking request - all through familiar form-based interactions rather than conversation.

**Why this priority**: Core booking capability must exist as an alternative to the agent. Users who prefer traditional web forms or have specific accessibility needs must be able to complete bookings without AI interaction.

**Independent Test**: Can be tested by selecting dates, viewing pricing, entering guest details, and submitting a booking request through forms only.

**Acceptance Scenarios**:

1. **Given** a user wants to book specific dates, **When** they use the booking widget, **Then** they can select check-in and check-out dates from a visual calendar.

2. **Given** dates are selected, **When** the user reviews the selection, **Then** they see an immediate price breakdown (nightly rate × nights + cleaning fee = total).

3. **Given** dates are unavailable, **When** the user selects them, **Then** those dates appear disabled/blocked on the calendar with clear visual indication.

4. **Given** the user confirms dates and pricing, **When** they proceed to booking, **Then** they see a guest details form (name, email, phone, number of guests).

5. **Given** all required fields are completed, **When** the user submits the booking, **Then** they are prompted to verify their email using Cognito verification code (same flow as agent bookings).

---

### User Story 3 - Visual Property Gallery (Priority: P3)

A guest wants to see detailed photos of the apartment before booking. They navigate to a gallery page where they can browse high-quality images of all rooms, amenities, and outdoor spaces. They can view images in full-screen mode and see descriptions of each area.

**Why this priority**: Visual content is critical for vacation rental bookings. Users need to see exactly what they're getting, and a well-presented gallery significantly influences booking decisions.

**Independent Test**: Can be tested by navigating to the gallery, viewing thumbnails, opening full-screen mode, and navigating between images.

**Acceptance Scenarios**:

1. **Given** a user navigates to the property page, **When** the page loads, **Then** they see a featured image gallery with multiple property photos.

2. **Given** a user wants to see more photos, **When** they click on the gallery, **Then** a lightbox/full-screen viewer opens showing all photos.

3. **Given** the lightbox is open, **When** the user navigates, **Then** they can move through images using arrows/swipe/keyboard.

4. **Given** photos are being viewed, **When** the user hovers over or views an image, **Then** they see a caption describing the room/area shown.

5. **Given** the user is on mobile, **When** they view the gallery, **Then** touch gestures (swipe, pinch-to-zoom) work naturally.

---

### User Story 4 - AI Agent Chat Route (Priority: P4)

A visitor prefers conversational interaction or needs help that goes beyond the standard booking flow. They navigate to the dedicated agent page at `/agent` and interact with the AI assistant exactly as before - asking about availability, getting personalized recommendations, learning about the local area, and potentially completing bookings through conversation.

**Why this priority**: The agent capability should not be removed - it provides value for users who prefer conversation, need personalized recommendations, or have questions that aren't covered by static pages. Moving it to a dedicated route preserves this functionality.

**Independent Test**: Can be tested by navigating to `/agent` and having the same conversational experience that was previously available on the homepage.

**Acceptance Scenarios**:

1. **Given** a visitor navigates to `/agent`, **When** the page loads, **Then** the AI chat interface appears exactly as it did on the previous homepage.

2. **Given** the agent page is loaded, **When** the user sends a message, **Then** the AI responds with the same capabilities (availability, pricing, property info, area recommendations).

3. **Given** the user is on any other page, **When** they want to chat with the agent, **Then** they can access the agent page via navigation link.

4. **Given** the user started a conversation on `/agent`, **When** they navigate away and return, **Then** their conversation history is preserved (session-based).

5. **Given** the agent suggests viewing specific information, **When** appropriate, **Then** links to relevant static pages (pricing, gallery, location) are provided.

---

### User Story 5 - Interactive Location & Map (Priority: P5)

A visitor wants to understand exactly where the property is located and what's nearby. They navigate to the location page and see an interactive map showing the apartment's position, nearby beaches, golf courses, restaurants, and other points of interest.

**Why this priority**: Location is a key factor in vacation rental decisions. Guests want to understand proximity to attractions, beaches, and amenities before booking.

**Independent Test**: Can be tested by navigating to location page, viewing the map, and interacting with markers for nearby attractions.

**Acceptance Scenarios**:

1. **Given** a user navigates to the Location page, **When** the page loads, **Then** they see an interactive map centered on the property location.

2. **Given** the map is displayed, **When** the user views it, **Then** they see markers for nearby attractions (beaches, golf, restaurants).

3. **Given** markers are on the map, **When** the user clicks a marker, **Then** they see details about that location (name, distance, brief description).

4. **Given** the user wants to explore, **When** they zoom/pan the map, **Then** the map responds smoothly and shows the broader Quesada/Costa Blanca area.

5. **Given** the user is on mobile, **When** they view the map, **Then** touch gestures work correctly for navigation.

---

### Edge Cases

- What happens when JavaScript fails to load? (Core content/images still visible; booking redirects to contact page)
- What happens when the availability API is slow or fails? (Loading states, graceful fallback message, suggestion to contact directly)
- How does the site handle very slow connections? (Progressive image loading, optimistic UI, skeleton screens)
- What happens when dates span seasonal boundaries? (Price breakdown shows different rates per period)
- How are past dates handled in the calendar? (Disabled, visually distinct, cannot be selected)
- What happens if a user tries to book dates that become unavailable while filling the form? (Validation on submit, clear error message)
- How does the gallery handle missing images? (Graceful fallback, placeholder, skip in gallery view)
- What happens if the user refreshes during booking? (Form state preserved or graceful restart)

## Requirements *(mandatory)*

### Functional Requirements

**Homepage & Navigation**

- **FR-001**: Homepage MUST display hero imagery showcasing the property
- **FR-002**: Homepage MUST display key property highlights (bedrooms, max guests, key amenities)
- **FR-003**: Homepage MUST include a prominent availability/booking call-to-action
- **FR-004**: Navigation MUST update to reflect new page structure with Homepage as landing page
- **FR-005**: Navigation MUST include clear link to AI Agent at `/agent` route
- **FR-006**: Navigation MUST maintain existing links: Pricing, Location, About, Area Guide, FAQ, Contact

**Booking Widget & Flow**

- **FR-007**: System MUST provide a visual date picker using React Day Picker for selecting check-in and check-out dates
- **FR-008**: Date picker MUST clearly show unavailable dates as blocked/disabled
- **FR-009**: System MUST display instant price calculation upon date selection
- **FR-010**: Price breakdown MUST show: nightly rate (per season), number of nights, cleaning fee, total
- **FR-011**: System MUST enforce minimum night requirements per season
- **FR-012**: System MUST collect guest information: name, email, phone, number of guests
- **FR-013**: System MUST validate guest count against property maximum (4 guests)
- **FR-013a**: Booking form MUST trigger Cognito email verification using existing `initiate_verification` / `verify_code` endpoints (consistent with agent flow)
- **FR-014**: Booking form MUST integrate with existing backend booking endpoints via generated TypeScript client from FastAPI OpenAPI schema
- **FR-014a**: All frontend HTTP clients MUST be auto-generated from the FastAPI OpenAPI spec to ensure type safety and contract alignment

**Property Gallery**

- **FR-015**: System MUST display property photos in an organized gallery format
- **FR-016**: Gallery MUST support full-screen/lightbox viewing mode
- **FR-017**: Lightbox MUST support keyboard navigation (arrow keys, escape to close)
- **FR-018**: Lightbox MUST support touch gestures on mobile (swipe navigation)
- **FR-019**: Images MUST include descriptive captions/alt text

**Agent Route** *(routing only - agent code modification is OUT OF SCOPE)*

- **FR-020**: Current chat interface MUST be accessible at `/agent` route (route change only; existing agent code unchanged)
- **FR-021**: Agent at `/agent` MUST retain all existing functionality (no modifications to agent implementation)
- **FR-021a**: Agent components MUST continue using ai-elements and Vercel AI SDK v6 (preserved from existing implementation; SHALL NOT adopt shadcn/ui)
- **FR-022**: Agent conversation state MUST be maintained within session (existing behavior preserved)
- **FR-023**: Agent page MUST be accessible from main navigation

**Location & Map**

- **FR-024**: Location page MUST display an interactive map using Leaflet with OpenStreetMap showing property position
- **FR-025**: Map MUST show markers for nearby points of interest fetched from backend API
- **FR-025a**: Backend MUST expose a POI endpoint returning points of interest from DynamoDB (via generated OpenAPI client)
- **FR-026**: Map markers MUST display popup/tooltip with location details (name, category, distance, description)
- **FR-027**: Map MUST support standard interactions (zoom, pan, click)

**Performance & Accessibility**

- **FR-028**: Homepage MUST achieve Lighthouse performance score above 80
- **FR-029**: All images MUST have appropriate alt text for screen readers
- **FR-030**: Forms MUST be fully keyboard navigable
- **FR-031**: Date picker MUST be accessible to screen readers
- **FR-032**: Color contrast MUST meet WCAG AA standards

### Key Entities

- **Booking Widget State**: User's selected dates, calculated pricing, guest count. Transient state during booking flow.

- **Gallery Image (Photo)**: Property photo stored in DynamoDB `photos` table with: `photo_id` (PK), `url` (S3/CloudFront URL), `caption`, `display_order` (integer for sorting), `room_type` (e.g., "bedroom", "pool", "kitchen").

- **Map Marker (POI)**: Point of interest stored in DynamoDB with name, category (beach, golf, restaurant, etc.), coordinates (lat/lng), distance from property, and description. Fetched via backend API.

- **Page**: Website page with route, title, metadata, and content. New homepage and agent routes join existing pages.

## Assumptions

- The existing backend API endpoints for availability checking and booking remain unchanged
- Property photos are already available or will be provided as static assets
- Leaflet with OpenStreetMap will be used for the location page (free, no API key required)
- **The existing agent code (ai-elements, AI SDK v6, chat components) remains completely unchanged** - only the route changes from `/` to `/agent`
- The existing chat functionality and all its dependencies (AgentCore, Cognito, etc.) remain unchanged
- Current static pages (Pricing, Location, About, Area Guide, FAQ, Contact) remain largely unchanged in content
- Mobile-first responsive design using Tailwind CSS (to be set up as part of shadcn/ui adoption)
- The property remains a single apartment with max 4 guests

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 70% of visitors can find availability information within 30 seconds of landing
- **SC-002**: 80% of booking form completions result in successful submission (form usability)
- **SC-003**: Homepage loads in under 3 seconds on 3G connection
- **SC-004**: Gallery images all load within 5 seconds of page load (with lazy loading)
- **SC-005**: AI agent usage remains accessible - 100% of previous agent functionality available at `/agent`
- **SC-006**: 90% of users can navigate from homepage to agent page in under 2 clicks
- **SC-007**: Lighthouse accessibility score above 90 for all pages
- **SC-008**: All booking-critical paths work without JavaScript (graceful degradation to contact form)
- **SC-009**: Mobile users (50%+ of traffic) report equivalent experience quality to desktop
- **SC-010**: Zero regression in existing functionality - all current pages and features continue working
