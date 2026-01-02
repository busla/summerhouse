'use client'

/**
 * useCreateReservation Hook
 *
 * Mutation hook for creating reservations via the generated OpenAPI client.
 * Uses @hey-api/openapi-ts SDK for type-safe API calls with JWT auth.
 *
 * Requirements: FR-011, FR-012
 */

import { useState, useCallback } from 'react'
import { ensureValidIdToken } from '@/lib/auth'
import { createReservationReservationsPost } from '@/lib/api-client'
import type {
  Reservation,
  ReservationCreateRequest,
  CreateReservationReservationsPostErrors,
} from '@/lib/api-client'
// Ensure client is configured
import '@/lib/api-client/config'

// === Types ===

export interface CreateReservationInput {
  /** Check-in date */
  checkIn: Date
  /** Check-out date */
  checkOut: Date
  /** Number of adult guests (1-4) */
  numAdults: number
  /** Number of children (0-4) */
  numChildren?: number
  /** Special requests from guest */
  specialRequests?: string
}

export interface CreateReservationResult {
  /** Created reservation on success */
  reservation?: Reservation
  /** Error message on failure */
  error?: string
  /** Error code for programmatic handling */
  errorCode?: string
}

export interface UseCreateReservationReturn {
  /** Execute the mutation */
  createReservation: (input: CreateReservationInput) => Promise<CreateReservationResult>
  /** Whether mutation is in progress */
  isLoading: boolean
  /** Last error from mutation */
  error: string | null
  /** Last successful result */
  data: Reservation | null
  /** Reset the hook state */
  reset: () => void
}

// === Helper Functions ===

/**
 * Format a Date to YYYY-MM-DD string for the API.
 */
function formatDateForApi(date: Date): string {
  return date.toISOString().slice(0, 10)
}

/**
 * Transform frontend input to API request body format.
 */
function toApiRequest(input: CreateReservationInput): ReservationCreateRequest {
  return {
    check_in: formatDateForApi(input.checkIn),
    check_out: formatDateForApi(input.checkOut),
    num_adults: input.numAdults,
    num_children: input.numChildren ?? 0,
    special_requests: input.specialRequests || undefined,
  }
}

/**
 * Extract user-friendly error message from API error response.
 */
function extractErrorMessage(
  error: CreateReservationReservationsPostErrors[keyof CreateReservationReservationsPostErrors] | unknown
): { message: string; code: string } {
  // Default fallbacks
  let message = 'Failed to create reservation'
  let code = 'RESERVATION_FAILED'

  if (!error || typeof error !== 'object') {
    return { message, code }
  }

  const errorObj = error as Record<string, unknown>

  // Backend ToolError format: { error_code, message, recovery, details }
  if (errorObj.error_code && typeof errorObj.error_code === 'string') {
    code = errorObj.error_code
    if (typeof errorObj.message === 'string') {
      message = errorObj.message
    }
  }
  // FastAPI HTTPException format: { detail: string | object }
  else if (errorObj.detail) {
    message =
      typeof errorObj.detail === 'string'
        ? errorObj.detail
        : JSON.stringify(errorObj.detail)
  }
  // Generic message field
  else if (typeof errorObj.message === 'string') {
    message = errorObj.message
  }

  return { message, code }
}

// === Hook ===

/**
 * Hook for creating reservations with authentication.
 *
 * Uses the generated OpenAPI client for type-safe API calls.
 *
 * @example
 * ```tsx
 * const { createReservation, isLoading, error } = useCreateReservation()
 *
 * const handleSubmit = async (data: FormData) => {
 *   const result = await createReservation({
 *     checkIn: data.dates.checkIn,
 *     checkOut: data.dates.checkOut,
 *     numAdults: data.guestCount,
 *     specialRequests: data.specialRequests,
 *   })
 *
 *   if (result.reservation) {
 *     // Success - navigate to confirmation
 *   } else {
 *     // Handle error
 *   }
 * }
 * ```
 */
export function useCreateReservation(): UseCreateReservationReturn {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<Reservation | null>(null)

  const reset = useCallback(() => {
    setError(null)
    setData(null)
    setIsLoading(false)
  }, [])

  const createReservation = useCallback(
    async (input: CreateReservationInput): Promise<CreateReservationResult> => {
      setIsLoading(true)
      setError(null)

      try {
        // Get authenticated token
        const token = await ensureValidIdToken()

        if (!token) {
          const errorMsg = 'Authentication required. Please sign in to continue.'
          setError(errorMsg)
          setIsLoading(false)
          return { error: errorMsg, errorCode: 'AUTH_REQUIRED' }
        }

        // Make API request using generated client
        // The client handles bearer token formatting via the auth callback
        const response = await createReservationReservationsPost({
          body: toApiRequest(input),
          auth: () => token, // Callback returns raw token; client adds "Bearer" prefix
        })

        // Handle error response (responseStyle='fields' returns { data, error, ... })
        if (response.error) {
          const { message, code } = extractErrorMessage(response.error)
          setError(message)
          setIsLoading(false)
          return { error: message, errorCode: code }
        }

        // Success - extract reservation from response
        const reservation = response.data as Reservation
        setData(reservation)
        setIsLoading(false)

        return { reservation }
      } catch (err) {
        // Network or unexpected errors
        const errorMsg =
          err instanceof Error ? err.message : 'An unexpected error occurred'
        setError(errorMsg)
        setIsLoading(false)
        return { error: errorMsg, errorCode: 'NETWORK_ERROR' }
      }
    },
    []
  )

  return {
    createReservation,
    isLoading,
    error,
    data,
    reset,
  }
}

export default useCreateReservation
