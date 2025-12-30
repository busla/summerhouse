/**
 * Shared TypeScript types for Summerhouse frontend.
 * These types mirror the backend Pydantic models for type-safe API interactions.
 */

// === Reservation Types ===

export type ReservationStatus =
  | 'pending_verification'
  | 'pending_payment'
  | 'confirmed'
  | 'checked_in'
  | 'checked_out'
  | 'cancelled'

export interface Reservation {
  reservation_id: string
  guest_id: string
  check_in_date: string // ISO date string (YYYY-MM-DD)
  check_out_date: string
  num_guests: number
  status: ReservationStatus
  total_price: number
  nightly_rate: number
  cleaning_fee: number
  created_at: string // ISO datetime
  updated_at: string
  confirmation_number: string
  special_requests?: string
  payment_id?: string
}

// === Guest Types ===

export interface Guest {
  guest_id: string
  email: string
  full_name: string
  phone?: string
  preferred_language: 'en' | 'es'
  email_verified: boolean
  created_at: string
  updated_at: string
  reservation_count: number
}

export interface GuestInput {
  email: string
  full_name: string
  phone?: string
  num_guests: number
  preferred_language?: 'en' | 'es'
}

// === Availability Types ===

export type DayAvailability = 'available' | 'booked' | 'blocked'

export interface AvailabilityDay {
  date: string
  status: DayAvailability
  min_stay?: number
}

export interface MonthAvailability {
  year: number
  month: number
  days: AvailabilityDay[]
}

// === Pricing Types ===

export type SeasonType = 'low' | 'mid' | 'high' | 'peak'

export interface PriceBreakdown {
  check_in_date: string
  check_out_date: string
  num_nights: number
  nightly_rate: number
  subtotal: number
  cleaning_fee: number
  total: number
  currency: string
  season: SeasonType
  min_stay_met: boolean
  min_stay_required?: number
}

// === Payment Types ===

export type PaymentStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'refunded'

export interface Payment {
  payment_id: string
  reservation_id: string
  amount: number
  currency: string
  status: PaymentStatus
  created_at: string
  updated_at: string
}

// === Chat Types ===

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  createdAt: Date
  /** Structured data for rich rendering (e.g., calendar, booking summary) */
  data?: RichContent
}

export type RichContentType =
  | 'calendar'
  | 'price_breakdown'
  | 'booking_summary'
  | 'verification_code'
  | 'photo_gallery'
  | 'confirmation'

export interface RichContent {
  type: RichContentType
  payload: CalendarPayload | PriceBreakdownPayload | BookingSummaryPayload | ConfirmationPayload
}

export interface CalendarPayload {
  availability: MonthAvailability
}

export interface PriceBreakdownPayload {
  breakdown: PriceBreakdown
}

export interface BookingSummaryPayload {
  reservation: Partial<Reservation>
  guest: Partial<Guest>
  pricing: PriceBreakdown
}

export interface ConfirmationPayload {
  confirmationNumber: string
  reservation: Reservation
}

// === Auth Types ===

/**
 * Browser-side auth session stored in localStorage (T005).
 * Updated to include refreshToken and cognitoSub for JWT session auth.
 */
export interface AuthSession {
  isAuthenticated: boolean
  guestId?: string
  email?: string
  accessToken?: string
  idToken?: string
  refreshToken?: string // T005: Added for token refresh
  cognitoSub?: string // T005: Added for user identity
  expiresAt?: number
}

export interface VerificationState {
  email: string
  codeRequested: boolean
  verified: boolean
  expiresAt?: number
}

/**
 * Token delivery event from backend via AgentCore SSE stream (T003).
 *
 * The frontend detects this event by checking `event_type === "auth_tokens"`
 * in tool results. When detected, tokens are extracted and stored in localStorage.
 *
 * Per spec clarification #1: Direct localStorage storage, no Amplify Auth.
 */
export interface TokenDeliveryEvent {
  /** Type discriminator - always "auth_tokens" for this event */
  event_type: 'auth_tokens'
  /** Always true for successful token delivery */
  success: true
  /** Cognito ID token (JWT) */
  id_token: string
  /** Cognito access token (JWT) */
  access_token: string
  /** Cognito refresh token */
  refresh_token: string
  /** Token expiry in seconds */
  expires_in: number
  /** Guest profile ID */
  guest_id: string
  /** Verified email address */
  email: string
  /** Cognito user sub (UUID) */
  cognito_sub: string
}

/**
 * Request payload for authenticated AgentCore requests (T004).
 *
 * Per spec clarification #2: JWT passed in request payload (`auth_token` field),
 * not the Authorization header.
 */
export interface AuthenticatedRequest {
  /** Chat messages to send */
  messages: Array<{ role: string; content: string }>
  /** Optional auth token for authenticated requests */
  auth_token?: string
}

// === API Response Types ===

export interface ApiError {
  code: string
  message: string
  details?: Record<string, unknown>
}

export interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: ApiError
}
