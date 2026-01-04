# Booking: Agent-First Vacation Rental Booking Platform

An AI agent-driven vacation rental booking platform for a single apartment in Quesada, Alicante. Users can interact with the conversational AI agent OR complete bookings through a traditional web interface, providing flexible paths to reserve their stay.

**Live Site**: Deployed on AWS (S3 + CloudFront)
**Agent Chat**: `/agent` route
**Direct Booking**: `/book` route

## Features

### Homepage & Discovery (`/`)
- Hero section with property imagery and value proposition
- Property highlights (bedrooms, guest capacity, key amenities)
- Prominent availability checker widget
- Quick navigation to booking options and agent chat
- Search-optimized metadata for SEO

### Direct Booking Flow (`/book`)
- Visual date picker (React Day Picker) for selecting check-in/check-out dates
- Real-time availability validation against DynamoDB
- Instant price breakdown (nightly rate, nights count, cleaning fee, total)
- Seasonal pricing calculation
- Minimum night stay enforcement
- Guest information form (name, email, phone, number of guests)
- Cognito email verification (OTP-based)
- Complete reservation creation via FastAPI backend
- Form state persistence using session storage

### Property Gallery (`/gallery`)
- Organized image grid showcasing all rooms and amenities
- Full-screen lightbox viewer with keyboard navigation (arrows, escape)
- Touch gesture support on mobile (swipe, pinch-to-zoom)
- Descriptive captions for each image
- Lazy loading for performance

### AI Agent Chat (`/agent`)
- Conversational interface for property inquiries and bookings
- Available tools: availability checking, pricing, property information, area recommendations
- Verification-required booking capability
- Session-based conversation history
- Links to relevant static pages within agent responses

### Property Location (`/location`)
- Interactive map (Leaflet + OpenStreetMap) showing property position
- Points of interest (POI) markers: beaches, golf courses, restaurants
- Clickable markers with details (name, distance, description)
- Responsive map interactions (zoom, pan)
- Mobile-touch optimized

### Payment Processing (`/booking/checkout`)
- Stripe Checkout integration for secure card payments
- Real-time payment status updates via webhooks
- Maximum 3 payment retry attempts per reservation
- Refund policy-based cancellation:
  - 14+ days before check-in: Full refund (100%)
  - 7-13 days before check-in: Partial refund (50%)
  - Less than 7 days before check-in: No refund
- Idempotent webhook handling with duplicate event detection
- Webhook events tracked with 90-day TTL for compliance

### Additional Pages
- **Pricing** (`/pricing`): Seasonal rates and minimum stay requirements
- **About** (`/about`): Property description and story
- **Area Guide** (`/area-guide`): Local attractions and activities
- **FAQ** (`/faq`): Common questions
- **Contact** (`/contact`): Direct contact form

## Technology Stack

### Frontend
- **Framework**: Next.js 14+ (App Router)
- **Language**: TypeScript 5.x (strict mode)
- **Package Manager**: Yarn Berry (v4.12+)
- **Styling**: Tailwind CSS 3.4+
- **UI Library**: shadcn/ui (button, form, dialog, select, input, card, alert, badge components)
- **Authentication**: AWS Amplify (Cognito EMAIL_OTP passwordless auth)
- **AI Integration**: Vercel AI SDK v6, @ai-sdk/react
- **Date Picking**: React Day Picker 9.13+
- **Photo Gallery**: yet-another-react-lightbox 3.28+
- **Maps**: Leaflet 1.9+ with react-leaflet 5.0+
- **API Integration**: Generated TypeScript client from FastAPI OpenAPI spec
- **Forms**: React Hook Form 7.69+ with Zod validation
- **Testing**: Playwright (E2E), Vitest (unit)

### Backend
- **Framework**: Strands Agents (Python 3.13+)
- **API**: FastAPI
- **Package Manager**: UV workspaces (3 packages: shared, api, agent)
- **Data Validation**: Pydantic v2 (strict mode)
- **LLM**: Amazon Bedrock (Claude Sonnet)
- **Database**: AWS DynamoDB (7 tables including webhook events)
- **Auth**: AWS Cognito (passwordless email OTP, customer profile schema with email, name, phone_number)
- **Agent Runtime**: AWS Bedrock AgentCore Runtime
- **Payments**: Stripe (Checkout sessions, refunds, webhook handling)
- **Secrets**: AWS SSM Parameter Store (Stripe API keys)

### Infrastructure
- **IaC**: Terraform with cloudposse modules and terraform-aws-modules
- **Hosting**:
  - Frontend: S3 + CloudFront with WAF
  - Backend API: AWS Lambda + API Gateway (REST API)
  - Agent: AWS Bedrock AgentCore Runtime
- **Region**: Configurable per environment (terraform.tfvars.json)

## Project Structure

```
booking/
├── README.md                   # This file
├── CLAUDE.md                   # Project instructions & constraints
├── Taskfile.yaml               # Task automation (dev, build, test, deploy)
├── frontend/                   # Next.js application
│   ├── src/
│   │   ├── app/                # Next.js App Router
│   │   │   ├── page.tsx        # Homepage
│   │   │   ├── book/           # Booking flow
│   │   │   ├── gallery/        # Photo gallery
│   │   │   ├── agent/          # AI chat interface
│   │   │   ├── location/       # Map & POI
│   │   │   ├── pricing/        # Seasonal rates
│   │   │   ├── about/          # Property info
│   │   │   ├── area-guide/     # Local guide
│   │   │   ├── faq/            # FAQ
│   │   │   └── contact/        # Contact form
│   │   ├── components/
│   │   │   ├── booking/        # Booking widgets (DatePicker, GuestForm, etc.)
│   │   │   ├── home/           # Homepage components (Hero, Highlights)
│   │   │   ├── ui/             # shadcn/ui component exports
│   │   │   ├── layout/         # Header, Footer, Navigation
│   │   │   └── providers/      # React context providers
│   │   ├── hooks/              # Custom React hooks
│   │   │   ├── useAvailability.ts  # Check date availability
│   │   │   ├── usePricing.ts       # Calculate pricing
│   │   │   ├── useCreateReservation.ts  # Submit bookings
│   │   │   └── useAuthenticatedUser.ts  # Cognito OTP auth & session mgmt
│   │   └── lib/                # Utilities
│   ├── tests/
│   │   ├── e2e/                # Playwright E2E tests
│   │   │   └── direct-booking.spec.ts  # Complete booking flow test
│   │   └── unit/               # Vitest unit tests
│   ├── tailwind.config.ts      # Tailwind configuration
│   ├── postcss.config.mjs      # PostCSS plugins
│   └── package.json
├── backend/                    # UV workspace root
│   ├── pyproject.toml          # Workspace definition
│   ├── shared/                 # Shared components
│   │   ├── src/shared/
│   │   │   ├── models/         # Pydantic models (Reservation, Customer, etc.)
│   │   │   ├── services/       # Business logic (DynamoDB, booking, pricing)
│   │   │   ├── tools/          # @tool decorated functions (agent tools)
│   │   │   └── utils/          # Utilities (JWT, errors, etc.)
│   ├── api/                    # FastAPI REST API
│   │   ├── src/api/
│   │   │   ├── main.py         # FastAPI app + Mangum handler
│   │   │   ├── docs.py         # OpenAPI documentation generation
│   │   │   ├── routes/         # API endpoints
│   │   │   │   ├── availability.py
│   │   │   │   ├── pricing.py
│   │   │   │   ├── reservations.py  (JWT required for create/modify/delete)
│   │   │   │   ├── customers.py    (JWT required: profile management)
│   │   │   │   ├── payments.py
│   │   │   │   ├── guests.py
│   │   │   │   ├── property.py
│   │   │   │   └── area.py
│   │   │   ├── middleware/     # Request/response middleware
│   │   │   └── models/         # Request/response Pydantic models
│   ├── agent/                  # Strands Agent
│   │   ├── src/agent/
│   │   │   ├── main.py         # Lambda handler
│   │   │   ├── booking_agent.py # Agent definition
│   │   │   └── prompts/        # System prompts
│   └── tests/                  # Test suites
│       ├── unit/
│       ├── integration/
│       └── contract/
├── infrastructure/             # Terraform IaC
│   ├── main.tf                 # Root Terraform configuration
│   ├── environments/           # Environment-specific configs
│   │   ├── dev/
│   │   │   ├── terraform.tfvars.json
│   │   │   └── backend.hcl
│   │   └── prod/
│   └── modules/
│       ├── static-website/     # S3 + CloudFront + WAF
│       ├── gateway-v2/         # API Gateway (REST API) + Lambda
│       ├── cognito-passwordless/ # Cognito User Pool
│       └── [other modules]
└── specs/                      # Feature specifications
    ├── 001-agent-booking-platform/ # Original platform
    ├── 007-tools-api-endpoints/    # REST API endpoints
    ├── 008-rest-api-gateway/       # REST API Gateway migration
    └── 009-booking-frontend/       # Direct booking UI
        ├── spec.md             # Complete requirements
        ├── plan.md             # Implementation plan
        ├── quickstart.md       # Getting started guide
        ├── tasks.md            # Task breakdown
        ├── data-model.md       # Entity models
        ├── research.md         # Technology research
        └── contracts/          # API contracts
```

## Quick Start

### Prerequisites
- Node.js 18+ and Yarn 4.12+
- Python 3.13+ with UV
- Terraform 1.5+
- AWS CLI configured with credentials
- Docker (optional, for local infrastructure testing)

### Development Setup

```bash
# Clone repository
git clone <repo-url>
cd booking

# Install all dependencies
task install

# Setup environment variables
cp .env.example .env.local
# Edit .env.local with your AWS credentials and config

# Start development servers
task dev
# Frontend: http://localhost:3000
# Backend API: http://localhost:3001
```

### Running Tests

```bash
# All tests
task test

# Frontend tests only
cd frontend && yarn test:e2e
# or unit tests: yarn test

# Backend tests
cd backend && task backend:test

# Specific E2E test (direct booking flow)
cd frontend && yarn test:e2e -- direct-booking.spec.ts
```

### Building for Production

```bash
# Build all packages
task build

# Or specific packages
cd frontend && yarn build
cd backend && uv build
```

### Deploying Infrastructure

```bash
# Initialize Terraform
task tf:init:dev

# Plan changes
task tf:plan:dev

# Apply changes
task tf:apply:dev

# View outputs
task tf:output:dev
```

## Frontend Booking Flow

### 1. Homepage Discovery
User lands on `/` and sees:
- Hero section with property photos
- Property highlights (2 bedrooms, 4 guests max, pool, WiFi)
- Availability widget (quick date check)
- Links to Gallery, Pricing, Location, Agent

### 2. Check Availability
User interacts with availability checker:
- Selects check-in date (today or future)
- Selects check-out date
- Widget calls `GET /api/availability` to verify dates
- Widget displays `useAvailability` hook results

### 3. Navigate to Booking (`/book`)
User clicks "Book Now" from availability widget or homepage CTA

### 4. Select Dates & Calculate Pricing
- Calendar picker (React Day Picker)
- Disabled dates from DynamoDB availability table
- Price calculation via `usePricing` hook calling `POST /api/pricing/calculate`
- Price breakdown displays:
  - Nightly rate (seasonal) × number of nights
  - Cleaning fee
  - Total price
- Enforces minimum night stay requirement

### 5. Select Guest Count
- Dropdown for number of guests (1-4, per property max)
- Validates against property capacity

### 6. Enter Guest Details
Form collects:
- Full name (required)
- Email (required, email format)
- Phone (required, valid format)
- Special requests (optional, text area)

Form uses React Hook Form with Zod validation for client-side validation.

Form also integrates `useAuthenticatedUser` hook to detect existing Cognito sessions:
- If authenticated: email and name fields display as read-only with signed-in banner
- If anonymous: inline "Verify email" button initiates OTP flow
- Users can sign out to switch accounts

### 7. Email Verification (Inline OTP)
After clicking "Verify email" button:
- `useAuthenticatedUser.initiateAuth(email)` attempts sign-in (existing user) or sign-up (new user)
- User receives OTP email via Cognito
- Form transitions to OTP entry state with input field
- User enters 6-digit code
- `useAuthenticatedUser.confirmOtp(code)` verifies and establishes session
- Error handling with type-aware messaging (network, validation, auth, rate_limit)
- Retry actions appear based on error type (resend, sign in again, etc.)

### 8. Create Reservation
After verification:
- Frontend calls `POST /api/reservations` with JWT token
- Backend validates dates haven't changed
- Creates `booking-{env}-reservations` DynamoDB entry
- Returns confirmation with reservation ID

### 9. Confirmation
Display confirmation screen:
- Reservation ID
- Guest name & email
- Check-in/check-out dates
- Total price
- Confirmation email sent to guest

## Backend API Endpoints

All endpoints auto-generated from OpenAPI spec. Frontend uses generated TypeScript client (`@hey-api/openapi-ts`).

### Public Endpoints (no auth required)
- `GET /api/availability` - Check if dates are available
- `GET /api/availability/calendar/{month}` - Get availability for entire month
- `GET /api/pricing` - Get current pricing
- `GET /api/pricing/rates` - Get seasonal rates
- `GET /api/pricing/calculate` - Calculate total for date range
- `GET /api/pricing/minimum-stay` - Get minimum stay requirements
- `GET /api/property` - Get property details
- `GET /api/property/photos` - Get photo URLs and metadata
- `GET /api/area` - Get area information
- `GET /api/area/recommendations` - Get activity recommendations

### Customer Endpoints (JWT required)
- `GET /api/customers/me` - Get current customer profile
- `POST /api/customers/me` - Create customer profile
- `PUT /api/customers/me` - Update current customer profile

Note: Email verification is now handled via AWS Amplify's native EMAIL_OTP authentication flow, no API endpoints required.

### Booking Endpoints (JWT required)
- `POST /api/reservations` - Create reservation
- `PATCH /api/reservations/{id}` - Modify reservation
- `DELETE /api/reservations/{id}` - Cancel reservation
- `GET /api/reservations/{id}` - Get reservation details

### Payment Endpoints (JWT required)
- `POST /api/payments/checkout-session` - Create Stripe Checkout session for payment
- `POST /api/payments` - Process payment (legacy)
- `GET /api/payments/{reservation_id}` - Get payment status
- `GET /api/payments/{reservation_id}/history` - Get payment history
- `POST /api/payments/{reservation_id}/retry` - Retry failed payment via Checkout
- `POST /api/payments/refund/{payment_id}` - Initiate refund (refund policy enforced)

### Webhook Endpoints (no auth required)
- `POST /api/webhooks/stripe` - Receive Stripe webhook events (signature verified)

## AI Agent Tools

Available in `/agent` chat interface:

### Availability Tools
- `check_availability` - Check if dates are available
- `get_calendar` - Get month availability

### Pricing Tools
- `get_pricing` - Get current pricing
- `calculate_total` - Calculate price for dates
- `get_seasonal_rates` - Get all seasonal rates
- `check_minimum_stay` - Check minimum night requirement
- `get_minimum_stay_info` - Get minimum stay details

### Reservation Tools
- `get_reservation` - Get existing reservation details
- `get_my_reservations` - Get customer's past reservations

### Property & Area Tools
- `get_property_details` - Full property information
- `get_photos` - Get photo gallery
- `get_area_info` - Area attractions and information
- `get_recommendations` - Personalized activity recommendations

### Customer Profile Tools
- `get_customer_info` - Retrieve customer profile
- `update_customer_details` - Update customer profile

### Booking Tools (requires verification)
- `create_reservation` - Create new booking
- `modify_reservation` - Change existing booking
- `cancel_reservation` - Cancel booking

### Payment Tools
- `process_payment` - Process payment
- `get_payment_status` - Check payment status
- `retry_payment` - Retry failed payment

### Verification Tools
- `initiate_verification` - Send OTP to email
- `verify_code` - Verify OTP code

## Database Schema

### DynamoDB Tables

| Table Name | PK | SK | Purpose |
|-----------|----|----|---------|
| `booking-{env}-reservations` | `reservation_id` | — | Customer bookings |
| `booking-{env}-customers` | `customer_id` | — | Customer profiles |
| `booking-{env}-availability` | `date` | — | Date availability flags |
| `booking-{env}-pricing` | `season_id` | — | Seasonal pricing tiers |
| `booking-{env}-payments` | `payment_id` | — | Payment records (Stripe integration) |
| `booking-{env}-verification-codes` | `email` | — | OTP codes (TTL: 10 min) |
| `booking-{env}-stripe-webhook-events` | `event_id` | — | Webhook events for idempotency (TTL: 90 days) |

### Reservation Schema

```json
{
  "reservation_id": "RES-2025-ABC123",
  "customer_id": "CUST-12345",
  "email": "customer@example.com",
  "guest_name": "John Doe",
  "phone": "+34-123-456789",
  "check_in": "2025-06-15",
  "check_out": "2025-06-20",
  "num_adults": 2,
  "total_price": 450.00,
  "status": "confirmed",
  "special_requests": "High floor preferred",
  "created_at": "2025-01-02T10:30:00Z",
  "verified": true
}
```

## Environment Variables

### Frontend (.env.local)
```
NEXT_PUBLIC_AWS_REGION=eu-west-1
NEXT_PUBLIC_COGNITO_IDENTITY_POOL_ID=eu-west-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
NEXT_PUBLIC_AGENTCORE_RUNTIME_ARN=arn:aws:bedrock-agentcore:eu-west-1:123456789012:runtime/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
NEXT_PUBLIC_API_BASE_URL=https://api.example.com
```

### Backend (backend/.env)
```
AWS_REGION=eu-west-1
DYNAMODB_RESERVATIONS_TABLE=booking-dev-reservations
DYNAMODB_CUSTOMERS_TABLE=booking-dev-customers
DYNAMODB_AVAILABILITY_TABLE=booking-dev-availability
DYNAMODB_PRICING_TABLE=booking-dev-pricing
DYNAMODB_PAYMENTS_TABLE=booking-dev-payments
DYNAMODB_VERIFICATION_CODES_TABLE=booking-dev-verification-codes
DYNAMODB_STRIPE_WEBHOOK_EVENTS_TABLE=booking-dev-stripe-webhook-events
COGNITO_USER_POOL_ID=eu-west-1_xxxxx
COGNITO_CLIENT_ID=xxxxx
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514
LOG_LEVEL=INFO
JWT_SECRET=your-secret-key-here
ENVIRONMENT=dev
FRONTEND_URL=http://localhost:3000
```

**Stripe Configuration** (stored in AWS SSM Parameter Store):
```
/booking/dev/stripe/secret_key     - Stripe secret API key (SecureString)
/booking/dev/stripe/webhook_secret - Stripe webhook signing secret (SecureString)
/booking/prod/stripe/secret_key    - Stripe secret API key for prod (SecureString)
/booking/prod/stripe/webhook_secret - Stripe webhook signing secret for prod (SecureString)
```

**Note**: Stripe keys are retrieved from SSM Parameter Store instead of .env for security. Ensure these parameters exist before running the payment endpoints.

## Features Matrix

| Feature | Status | Notes |
|---------|--------|-------|
| Homepage Discovery | ✓ Complete | Hero, highlights, availability widget |
| Direct Booking Flow | ✓ Complete | Date picker, pricing, form, verification |
| Photo Gallery | ✓ Complete | Lightbox with keyboard/touch support |
| AI Agent Chat | ✓ Complete | All tools available at `/agent` |
| Location Map | ✓ Complete | POI markers with details |
| Email Verification | ✓ Complete | OTP via Cognito, inline in form |
| User Profile Management | ✓ Complete | GET/POST/PUT /customers/me endpoints |
| Session Persistence | ✓ Complete | Cognito session auto-restore on page load |
| Authenticated State Display | ✓ Complete | Read-only fields + sign-out option |
| Seasonal Pricing | ✓ Complete | Rate calculation per period |
| Availability Calendar | ✓ Complete | Real-time DynamoDB checks |
| Price Breakdown | ✓ Complete | Nightly rate + cleaning fee |
| Session Storage | ✓ Complete | Form state persistence |
| Mobile Responsive | ✓ Complete | Tailwind-based design |
| Accessibility (WCAG AA) | ✓ Complete | Keyboard nav, screen reader support |
| E2E Tests | ✓ Complete | Direct booking flow coverage |
| Stripe Payments | ✓ Complete | Checkout sessions, refunds, webhook handling |
| Payment Retry | ✓ Complete | Max 3 attempts per reservation |
| Refund Policy | ✓ Complete | Policy-based refund calculation (14d, 7d tiers) |
| Webhook Handling | ✓ Complete | Idempotent event processing with deduplication |

## Testing

### E2E Test Coverage

**File**: `frontend/tests/e2e/direct-booking.spec.ts`

Complete user journey tests:
1. Navigate to homepage
2. Open booking widget
3. Select dates
4. Verify availability
5. Calculate pricing
6. Navigate to booking page
7. Fill guest details form
8. Submit booking
9. Verify email sent
10. Enter OTP verification
11. Confirmation displayed

### Running E2E Tests

```bash
# Run all E2E tests
task frontend:test:e2e

# Run specific test
cd frontend && yarn test:e2e -- direct-booking.spec.ts

# Run with UI mode
task frontend:test:e2e:ui

# Run against live environment
task frontend:test:e2e:live
```

## Performance Optimization

- **Image Optimization**: Next.js Image component with lazy loading
- **Code Splitting**: Route-based code splitting in Next.js
- **Caching**: CloudFront caching for static assets (frontend)
- **API Caching**: ETag support for API responses
- **Font Optimization**: System font stack (no custom fonts)
- **CSS**: Tailwind CSS purging unused styles in production

### Lighthouse Goals
- Performance: >80
- Accessibility: >90
- Best Practices: >85
- SEO: >90

## Monitoring & Logging

### Frontend
- Browser console for development
- Structured error logging to CloudWatch (production)
- Performance metrics via web-vitals

### Backend
- Python logging module with JSON structured logs
- AWS CloudWatch integration
- Correlation IDs for request tracing
- Error tracking with stack traces

## Troubleshooting

### Booking not submitting?
- Check email verification flow (OTP should arrive within 30 seconds)
- Verify JWT token in Authorization header
- Check DynamoDB tables exist and have correct names in env vars

### Availability showing as unavailable?
- Verify DynamoDB `booking-{env}-availability` table has current dates
- Check seed data: `task seed:dev`

### Map not loading?
- Verify Leaflet and OpenStreetMap CDN accessibility
- Check browser console for errors
- Ensure POI endpoint is returning valid data

### Agent chat not responding?
- Verify Bedrock credentials and runtime ARN
- Check CloudWatch logs for agent Lambda errors
- Verify conversation history is being stored

### Payment not processing?
- Verify Stripe API keys are stored in SSM Parameter Store: `/booking/{env}/stripe/secret_key`
- Check that webhook endpoint is configured in Stripe Dashboard: `POST /api/webhooks/stripe`
- Verify webhook signing secret matches: `/booking/{env}/stripe/webhook_secret`
- Check DynamoDB `booking-{env}-payments` and `booking-{env}-stripe-webhook-events` tables exist
- Review CloudWatch logs for StripeServiceError messages
- Ensure checkout session URLs redirect to valid domain (configured in `FRONTEND_URL`)

### Refund not processing?
- Verify payment is in "completed" status before attempting refund
- Check that refund policy allows refund for the check-in date
- Verify Stripe PaymentIntent ID is stored in payment record
- Check CloudWatch logs for refund-related errors
- Ensure customer owns the reservation they're refunding

## Roadmap

### MVP (Current)
- Homepage with hero and highlights
- Direct booking flow with date picker
- Photo gallery with lightbox
- AI agent chat at `/agent`
- Location map with POI
- Email OTP verification
- Static placeholder pages (Pricing, About, Area Guide, FAQ, Contact)
- Stripe payment processing with Checkout
- Payment retry mechanism (max 3 attempts)
- Refund policy enforcement (14-day, 7-day cancellation tiers)
- Webhook handling with idempotency

### Phase 2 (Future)
- Guest management dashboard
- Admin booking management interface
- SMS notifications for bookings
- Multi-language support
- Reviews and ratings system
- Automated reminders (24h, 48h pre-arrival)

### Phase 3 (Future)
- Multiple properties support
- Group booking discounts
- Seasonal pricing rule builder
- Dynamic pricing optimization
- Waitlist/notification system
- Integration with booking.com, Airbnb

## Contributing

This project follows test-first development principles:
1. Write tests first
2. Implement feature to pass tests
3. Refactor for clarity
4. Update documentation

See `CLAUDE.md` for detailed contributing guidelines and technology constraints.

## License

Copyright 2025 - All rights reserved

## Support

For issues or questions:
- Check the troubleshooting section above
- Review `specs/009-booking-frontend/` for detailed specifications
- Check CloudWatch logs for backend errors
- Review browser console for frontend errors
