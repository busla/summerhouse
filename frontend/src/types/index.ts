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
 * Auth required event from @requires_access_token decorated tools.
 *
 * When an agent tool requires authentication via AgentCore Identity OAuth2,
 * it returns this event structure. The frontend should detect this and
 * redirect the user to the login page with the auth_url.
 *
 * @see specs/005-agentcore-amplify-oauth2/spec.md
 */
export interface AuthRequiredEvent {
  /** Status indicator - always "auth_required" for this event */
  status: 'auth_required'
  /** AgentCore OAuth2 callback URL to redirect to after login */
  auth_url: string
  /** User-friendly message explaining why auth is needed */
  message: string
  /** Recommended action for the frontend */
  action: 'redirect_to_auth'
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
