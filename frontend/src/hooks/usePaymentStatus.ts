'use client'

/**
 * usePaymentStatus Hook
 *
 * Polls payment status for a reservation with automatic retry and
 * state management. Stops polling on terminal states.
 *
 * @see specs/014-stripe-checkout-frontend/spec.md - FR-008 (Status Polling)
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { ensureValidIdToken } from '@/lib/auth'
import { getPaymentStatusPaymentsReservationIdGet } from '@/lib/api-client'
import type { Payment, TransactionStatus } from '@/lib/api-client'
// Ensure client is configured
import '@/lib/api-client/config'

// ============================================================================
// Constants
// ============================================================================

/** Default polling interval in milliseconds */
const DEFAULT_POLL_INTERVAL = 3000

/** Maximum number of poll attempts before giving up */
const MAX_POLL_ATTEMPTS = 20

/** Terminal states that stop polling */
const TERMINAL_STATES: TransactionStatus[] = ['completed', 'failed', 'refunded']

// ============================================================================
// Types
// ============================================================================

export interface PaymentStatusState {
  /** Payment data from API */
  payment: Payment | null
  /** Whether currently loading (initial or polling) */
  isLoading: boolean
  /** Whether initial load is complete */
  isInitialLoad: boolean
  /** Error message if fetch failed */
  error: string | null
  /** Whether polling is active */
  isPolling: boolean
  /** Number of poll attempts made */
  pollCount: number
}

export interface UsePaymentStatusOptions {
  /** Reservation ID to poll payment status for */
  reservationId: string | null
  /** Whether to start polling automatically (default: true) */
  autoStart?: boolean
  /** Polling interval in milliseconds (default: 3000) */
  pollInterval?: number
  /** Maximum poll attempts (default: 20) */
  maxAttempts?: number
  /** Callback when status reaches terminal state */
  onComplete?: (payment: Payment) => void
  /** Callback when polling fails */
  onError?: (error: string) => void
}

export interface UsePaymentStatusReturn {
  /** Current state */
  state: PaymentStatusState
  /** Manually trigger a status fetch */
  refresh: () => Promise<void>
  /** Start polling */
  startPolling: () => void
  /** Stop polling */
  stopPolling: () => void
  /** Whether status is in a terminal state */
  isTerminal: boolean
}

// ============================================================================
// Hook
// ============================================================================

/**
 * Hook for polling payment status.
 *
 * Automatically polls the payment status API until a terminal state
 * is reached (completed, failed, refunded) or max attempts exceeded.
 *
 * @example
 * ```tsx
 * const { state, isTerminal } = usePaymentStatus({
 *   reservationId: 'RES-123',
 *   onComplete: (payment) => console.log('Payment complete!', payment),
 * })
 *
 * if (state.isLoading) return <Spinner />
 * if (state.error) return <Error message={state.error} />
 * if (state.payment) return <PaymentStatusBadge status={state.payment.status} />
 * ```
 */
export function usePaymentStatus(options: UsePaymentStatusOptions): UsePaymentStatusReturn {
  const {
    reservationId,
    autoStart = true,
    pollInterval = DEFAULT_POLL_INTERVAL,
    maxAttempts = MAX_POLL_ATTEMPTS,
    onComplete,
    onError,
  } = options

  const [state, setState] = useState<PaymentStatusState>({
    payment: null,
    isLoading: true,
    isInitialLoad: true,
    error: null,
    isPolling: false,
    pollCount: 0,
  })

  // Refs for cleanup and stale closure prevention
  const intervalRef = useRef<NodeJS.Timeout | null>(null)
  const mountedRef = useRef(true)
  const onCompleteRef = useRef(onComplete)
  const onErrorRef = useRef(onError)

  // Keep callback refs up to date
  useEffect(() => {
    onCompleteRef.current = onComplete
    onErrorRef.current = onError
  }, [onComplete, onError])

  /**
   * Check if a status is terminal (no more polling needed).
   */
  const isTerminalStatus = useCallback((status: TransactionStatus): boolean => {
    return TERMINAL_STATES.includes(status)
  }, [])

  /**
   * Fetch payment status once.
   */
  const fetchStatus = useCallback(async (): Promise<Payment | null> => {
    if (!reservationId) return null

    try {
      const token = await ensureValidIdToken()
      if (!token) {
        throw new Error('Authentication required')
      }

      const response = await getPaymentStatusPaymentsReservationIdGet({
        path: { reservation_id: reservationId },
        auth: () => token,
      })

      if (response.error) {
        // 404 means no payment exists yet - not an error for polling
        if (response.response?.status === 404) {
          return null
        }
        const errorDetail =
          typeof response.error === 'object' && 'detail' in response.error
            ? String((response.error as { detail: unknown }).detail)
            : 'Failed to fetch payment status'
        throw new Error(errorDetail)
      }

      return response.data as Payment
    } catch (err) {
      throw err instanceof Error ? err : new Error('Failed to fetch payment status')
    }
  }, [reservationId])

  /**
   * Single poll iteration.
   */
  const poll = useCallback(async () => {
    if (!mountedRef.current) return

    setState((prev) => ({
      ...prev,
      isLoading: prev.isInitialLoad, // Only show loading on initial
      pollCount: prev.pollCount + 1,
    }))

    try {
      const payment = await fetchStatus()

      if (!mountedRef.current) return

      if (payment) {
        setState((prev) => ({
          ...prev,
          payment,
          isLoading: false,
          isInitialLoad: false,
          error: null,
        }))

        // Check if we should stop polling
        if (isTerminalStatus(payment.status)) {
          // Clear interval
          if (intervalRef.current) {
            clearInterval(intervalRef.current)
            intervalRef.current = null
          }
          setState((prev) => ({ ...prev, isPolling: false }))
          onCompleteRef.current?.(payment)
        }
      } else {
        // No payment yet - continue polling
        setState((prev) => ({
          ...prev,
          isLoading: false,
          isInitialLoad: false,
        }))
      }
    } catch (err) {
      if (!mountedRef.current) return

      const errorMsg = err instanceof Error ? err.message : 'Failed to fetch payment status'
      setState((prev) => ({
        ...prev,
        isLoading: false,
        isInitialLoad: false,
        error: errorMsg,
      }))
      onErrorRef.current?.(errorMsg)
    }
  }, [fetchStatus, isTerminalStatus])

  /**
   * Stop polling.
   */
  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    setState((prev) => ({ ...prev, isPolling: false }))
  }, [])

  /**
   * Start polling.
   */
  const startPolling = useCallback(() => {
    if (!reservationId || intervalRef.current) return

    setState((prev) => ({ ...prev, isPolling: true, pollCount: 0 }))

    // Initial fetch
    poll()

    // Set up interval
    intervalRef.current = setInterval(() => {
      // Check max attempts
      setState((prev) => {
        if (prev.pollCount >= maxAttempts) {
          stopPolling()
          const errorMsg = 'Payment status check timed out. Please refresh the page.'
          onErrorRef.current?.(errorMsg)
          return { ...prev, error: errorMsg, isPolling: false }
        }
        return prev
      })

      // Only poll if still mounted and polling
      if (mountedRef.current && intervalRef.current) {
        poll()
      }
    }, pollInterval)
  }, [reservationId, poll, pollInterval, maxAttempts, stopPolling])

  /**
   * Manual refresh (single fetch, doesn't affect polling).
   */
  const refresh = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }))
    try {
      const payment = await fetchStatus()
      if (mountedRef.current && payment) {
        setState((prev) => ({
          ...prev,
          payment,
          isLoading: false,
          error: null,
        }))

        if (isTerminalStatus(payment.status)) {
          stopPolling()
          onCompleteRef.current?.(payment)
        }
      } else if (mountedRef.current) {
        setState((prev) => ({ ...prev, isLoading: false }))
      }
    } catch (err) {
      if (mountedRef.current) {
        const errorMsg = err instanceof Error ? err.message : 'Failed to fetch payment status'
        setState((prev) => ({ ...prev, isLoading: false, error: errorMsg }))
      }
    }
  }, [fetchStatus, isTerminalStatus, stopPolling])

  // Auto-start polling on mount
  useEffect(() => {
    mountedRef.current = true

    if (autoStart && reservationId) {
      startPolling()
    }

    return () => {
      mountedRef.current = false
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [autoStart, reservationId, startPolling])

  // Compute isTerminal
  const isTerminal = state.payment ? isTerminalStatus(state.payment.status) : false

  return {
    state,
    refresh,
    startPolling,
    stopPolling,
    isTerminal,
  }
}

export default usePaymentStatus
