'use client'

/**
 * useCheckoutSession Hook
 *
 * Manages Stripe Checkout flow: creates checkout sessions and handles redirects.
 * Used by PaymentStep component to initiate payment flow.
 *
 * @see specs/014-stripe-checkout-frontend/spec.md - FR-002, FR-003, FR-014
 * @see specs/014-stripe-checkout-frontend/contracts/checkout-session.types.ts
 */

import { useState, useCallback } from 'react'
import { ensureValidIdToken } from '@/lib/auth'
import {
  createCheckoutSessionPaymentsCheckoutSessionPost,
  retryPaymentPaymentsReservationIdRetryPost,
} from '@/lib/api-client'
import type {
  CheckoutSessionResponse,
  CreateCheckoutSessionPaymentsCheckoutSessionPostErrors,
  RetryPaymentPaymentsReservationIdRetryPostErrors,
} from '@/lib/api-client'
// Ensure client is configured
import '@/lib/api-client/config'

// ============================================================================
// Types
// ============================================================================

/**
 * State for the checkout session creation process.
 */
export interface CheckoutSessionState {
  /** Whether a checkout session is being created */
  isLoading: boolean
  /** Error message if session creation failed */
  error: string | null
  /** Whether redirect to Stripe is in progress */
  isRedirecting: boolean
}

/**
 * Result of creating a checkout session.
 */
export interface CreateSessionResult {
  /** Checkout session data on success */
  session?: CheckoutSessionResponse
  /** Error message on failure */
  error?: string
  /** Error code for programmatic handling */
  errorCode?: string
}

/**
 * Return type for the useCheckoutSession hook.
 */
export interface UseCheckoutSessionReturn {
  /** Current state */
  state: CheckoutSessionState
  /**
   * Create a new checkout session and redirect to Stripe.
   * @param reservationId - Reservation ID to pay for
   */
  createSession: (reservationId: string) => Promise<CreateSessionResult>
  /**
   * Retry payment for a reservation with failed payment.
   * @param reservationId - Reservation ID to retry
   */
  retryPayment: (reservationId: string) => Promise<CreateSessionResult>
  /** Reset error state */
  clearError: () => void
}

// ============================================================================
// Helper Functions
// ============================================================================

type CheckoutError =
  | CreateCheckoutSessionPaymentsCheckoutSessionPostErrors[keyof CreateCheckoutSessionPaymentsCheckoutSessionPostErrors]
  | RetryPaymentPaymentsReservationIdRetryPostErrors[keyof RetryPaymentPaymentsReservationIdRetryPostErrors]

/**
 * Extract user-friendly error message from API error response.
 */
function extractErrorMessage(error: CheckoutError | unknown): {
  message: string
  code: string
} {
  let message = 'Failed to create checkout session'
  let code = 'CHECKOUT_FAILED'

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

/**
 * Redirect to Stripe Checkout.
 * Uses window.location.href for full-page redirect (required by Stripe).
 */
function redirectToStripe(checkoutUrl: string): void {
  window.location.href = checkoutUrl
}

// ============================================================================
// Hook
// ============================================================================

/**
 * Hook for managing Stripe Checkout sessions.
 *
 * Creates checkout sessions and handles redirect to Stripe's hosted page.
 * Supports both initial payment and retry flows.
 *
 * @example
 * ```tsx
 * const { state, createSession, clearError } = useCheckoutSession()
 *
 * const handlePay = async () => {
 *   const result = await createSession(reservationId)
 *   // If successful, user is redirected to Stripe
 *   // If error, result.error contains message
 * }
 * ```
 */
export function useCheckoutSession(): UseCheckoutSessionReturn {
  const [state, setState] = useState<CheckoutSessionState>({
    isLoading: false,
    error: null,
    isRedirecting: false,
  })

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }))
  }, [])

  /**
   * Create a new checkout session for initial payment.
   */
  const createSession = useCallback(
    async (reservationId: string): Promise<CreateSessionResult> => {
      setState({ isLoading: true, error: null, isRedirecting: false })

      try {
        // Get authenticated token
        const token = await ensureValidIdToken()

        if (!token) {
          const errorMsg = 'Authentication required. Please sign in to continue.'
          setState({ isLoading: false, error: errorMsg, isRedirecting: false })
          return { error: errorMsg, errorCode: 'AUTH_REQUIRED' }
        }

        // Create checkout session via API
        const response = await createCheckoutSessionPaymentsCheckoutSessionPost({
          body: { reservation_id: reservationId },
          auth: () => token,
        })

        // Handle error response
        if (response.error) {
          const { message, code } = extractErrorMessage(response.error)
          setState({ isLoading: false, error: message, isRedirecting: false })
          return { error: message, errorCode: code }
        }

        // Success - redirect to Stripe
        const session = response.data as CheckoutSessionResponse
        setState({ isLoading: false, error: null, isRedirecting: true })

        // Perform redirect (this will navigate away from the page)
        redirectToStripe(session.checkout_url)

        return { session }
      } catch (err) {
        const errorMsg =
          err instanceof Error ? err.message : 'An unexpected error occurred'
        setState({ isLoading: false, error: errorMsg, isRedirecting: false })
        return { error: errorMsg, errorCode: 'NETWORK_ERROR' }
      }
    },
    []
  )

  /**
   * Retry payment for a reservation with failed payment.
   */
  const retryPayment = useCallback(
    async (reservationId: string): Promise<CreateSessionResult> => {
      setState({ isLoading: true, error: null, isRedirecting: false })

      try {
        // Get authenticated token
        const token = await ensureValidIdToken()

        if (!token) {
          const errorMsg = 'Authentication required. Please sign in to continue.'
          setState({ isLoading: false, error: errorMsg, isRedirecting: false })
          return { error: errorMsg, errorCode: 'AUTH_REQUIRED' }
        }

        // Create retry checkout session via API
        const response = await retryPaymentPaymentsReservationIdRetryPost({
          path: { reservation_id: reservationId },
          body: {},
          auth: () => token,
        })

        // Handle error response
        if (response.error) {
          const { message, code } = extractErrorMessage(response.error)
          setState({ isLoading: false, error: message, isRedirecting: false })
          return { error: message, errorCode: code }
        }

        // Success - redirect to Stripe
        const session = response.data as CheckoutSessionResponse
        setState({ isLoading: false, error: null, isRedirecting: true })

        // Perform redirect
        redirectToStripe(session.checkout_url)

        return { session }
      } catch (err) {
        const errorMsg =
          err instanceof Error ? err.message : 'An unexpected error occurred'
        setState({ isLoading: false, error: errorMsg, isRedirecting: false })
        return { error: errorMsg, errorCode: 'NETWORK_ERROR' }
      }
    },
    []
  )

  return {
    state,
    createSession,
    retryPayment,
    clearError,
  }
}

export default useCheckoutSession
