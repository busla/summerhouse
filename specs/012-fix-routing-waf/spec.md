# Feature Specification: Fix Next.js Routing and WAF 403 Errors

**Feature Branch**: `012-fix-routing-waf`
**Created**: 2026-01-03
**Status**: Draft
**Input**: User description: "the nextjs router is not working properly. The navbar is not mapped to correct routes, i.e. /booking instead of /booking/. When I enter the correct routes in the url bar, i.e. /booking/ I get a 403 (could be related to my WAF settings)."

## Problem Statement

Users are experiencing two related navigation issues on the booking website:

1. **Navbar Route Mismatch**: Navigation links point to paths without trailing slashes (e.g., `/gallery`) while the site is configured to use trailing slashes (`/gallery/`). This causes inconsistent behavior and prevents proper route matching.

2. **403 Errors on Valid Routes**: When users manually enter URLs with correct trailing slashes (e.g., `/booking/`), they receive 403 Forbidden errors. This suggests either WAF misconfiguration or S3/CloudFront routing issues preventing access to valid static files.

## Root Cause Analysis

Based on codebase investigation:

- **Navigation.tsx**: Default links use non-trailing-slash paths (`/gallery`, `/book`, `/agent`)
- **next.config.js**: Has `trailingSlash: true` - exports pages as `/gallery/index.html`
- **WAF Configuration**: Deny-by-default policy blocks non-whitelisted IPs
- **CloudFront Error Handling**: Returns 403 for both WAF blocks AND missing S3 objects

### Understanding the Two Routing Layers

**Layer 1 - Next.js Client-Side Routing (works correctly):**
When clicking a `<Link>` component, Next.js handles navigation entirely in JavaScript. No HTTP request is made to the server, so the trailing slash format doesn't matter.

**Layer 2 - CloudFront + S3 Static Hosting (where 403 errors occur):**
When refreshing the page or typing a URL directly, the browser makes an HTTP request to CloudFront → S3. The static export creates files like `/gallery/index.html`, but:
- S3 doesn't automatically resolve `/gallery` → `/gallery/index.html`
- S3 doesn't automatically resolve `/gallery/` → `/gallery/index.html`
- S3 with OAC returns 403 (not 404) for any non-existent path

**The 403 error sequence:**
1. User refreshes browser on `/gallery/` (or types URL directly)
2. CloudFront asks S3 for `/gallery/`
3. S3 looks for a file literally named `/gallery/` (doesn't exist)
4. S3 returns 403 (access denied - security behavior with OAC)
5. User sees 403 instead of the gallery page

**Why CloudFront URL rewriting is needed:**
The CloudFront Function intercepts requests at the edge and rewrites `/gallery` and `/gallery/` to `/gallery/index.html` before S3 is queried. This is the standard solution for static site hosting with S3.

## User Scenarios & Testing

### User Story 1 - Navigate Site via Navbar (Priority: P1)

Users can navigate between all pages using the navigation bar without encountering errors.

**Why this priority**: Core functionality - users must be able to browse the site to make bookings.

**Independent Test**: Click each navigation link and verify the correct page loads with proper URL.

**Acceptance Scenarios**:

1. **Given** a user is on the homepage, **When** they click "Gallery" in the navbar, **Then** they are taken to the gallery page and the URL shows the correct path
2. **Given** a user is on any page, **When** they click any navigation link, **Then** the page loads within 2 seconds without errors
3. **Given** a user is on a page accessed via navbar, **When** they refresh the browser, **Then** the same page reloads successfully
4. **Given** a user is on the booking page with form data entered, **When** they refresh the browser, **Then** the form data (guest count, dates, contact info) is preserved

---

### User Story 2 - Direct URL Access (Priority: P1)

Users can access any page by typing or pasting the URL directly into their browser's address bar.

**Why this priority**: Essential for sharing links, bookmarks, and returning visitors.

**Independent Test**: Type each route URL directly into browser and verify page loads.

**Acceptance Scenarios**:

1. **Given** a user types `example.com/gallery/` in the address bar, **When** they press Enter, **Then** the gallery page loads successfully
2. **Given** a user types `example.com/gallery` (no trailing slash), **When** they press Enter, **Then** they are redirected to the correct URL and the page loads
3. **Given** a user bookmarks a page, **When** they click the bookmark later, **Then** the page loads without 403 or 404 errors

---

### User Story 3 - Active Navigation State (Priority: P2)

The navigation bar visually indicates which page the user is currently viewing.

**Why this priority**: Improves user orientation and experience but not critical for functionality.

**Independent Test**: Navigate to each page and verify the corresponding nav link is highlighted.

**Acceptance Scenarios**:

1. **Given** a user is on the gallery page (accessed via `/gallery/`), **When** they view the navbar, **Then** the "Gallery" link appears highlighted/active
2. **Given** a user navigates from gallery to booking, **When** the page loads, **Then** the active state moves from "Gallery" to "Book"

---

### Edge Cases

- What happens when a user accesses a URL that doesn't exist (e.g., `/nonexistent/`)? → Shows error page (403.html with 404-style messaging; see FR-004 clarification in Assumptions)
- How does the system handle double slashes (e.g., `/gallery//`)? → Treated as invalid path; CloudFront Function does not normalize multiple slashes. Displays error page (acceptable behavior, not worth additional complexity).
- What happens when accessing routes from non-whitelisted IPs? → Should show appropriate 403 error page (this is expected WAF behavior)
- What clears booking form data? → Successful booking submission or user explicitly starting a new booking

## Requirements

### Functional Requirements

- **FR-001**: All navbar links MUST use URLs that match the configured trailing slash setting
- **FR-002**: Users MUST be able to access all public pages without receiving 403 errors (when on whitelisted IPs)
- **FR-003**: The active navigation state MUST correctly reflect the current page regardless of URL format accessed
- **FR-004**: Non-existent routes MUST return 404 errors, not 403 errors
- **FR-005**: The content delivery system MUST properly resolve directory requests to their index files
- **FR-006**: All pages MUST be accessible both with and without trailing slashes (via URL rewrite at edge)
- **FR-007**: The booking page (`/book/`) MUST preserve form data (guest count, dates, contact info) when the user refreshes the page

### Key Entities

- **Navigation Link**: Label, target URL, active state indicator
- **Route**: URL path, corresponding static file location, trailing slash handling
- **Error Page**: Error code (403/404), custom error page content

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of navigation links successfully load their target pages without errors
- **SC-002**: All 12 public routes are accessible via direct URL entry (`/`, `/gallery/`, `/location/`, `/book/`, `/agent/`, `/about/`, `/pricing/`, `/faq/`, `/contact/`, `/area-guide/`, `/login/`, `/callback/`)
- **SC-003**: Page load time remains under 3 seconds after routing changes
- **SC-004**: Both trailing slash and non-trailing slash URL variants successfully reach the same content
- **SC-005**: Non-existent URLs display the 404 error page, not 403

## Clarifications

### Session 2026-01-03

- Q: Which pages require form data persistence on refresh? → A: Only the booking page (`/book/`) - preserve guest count, dates, contact info
- Q: Why do we need a CloudFront function? Can't we just fix the trailing slashes in the navbar? → A: The navbar fix only solves client-side navigation. The CloudFront function is needed because: (1) S3 doesn't automatically resolve directory paths to index.html files, (2) browser refresh and direct URL access bypass Next.js client routing, and (3) S3 with OAC returns 403 for any path that doesn't exactly match a stored file. This is the standard solution for static site hosting.

## Assumptions

- The WAF IP whitelist is correctly configured and the 403 errors are not caused by IP blocking (user reports they can access `index.html` from the same IP)
- The issue is isolated to routing/URL resolution, not a broader infrastructure failure
- Custom error pages (403.html, 404.html) exist and are deployed
- The frontend build and deployment process is working correctly (issue is configuration, not build)
- **FR-004 clarification**: Due to S3 Origin Access Control (OAC) security behavior, the HTTP status code for non-existent routes will be 403. The custom 403.html error page provides 404-style messaging to users. True 404 status codes would require Lambda@Edge, which is out of scope for this fix.
