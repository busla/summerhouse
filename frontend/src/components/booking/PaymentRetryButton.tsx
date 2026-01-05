'use client'

/**
 * PaymentRetryButton Component
 *
 * Handles payment retry logic with attempt tracking and max attempts enforcement.
 * Shows retry button when attempts remain, or contact support message when exhausted.
 *
 * @see specs/014-stripe-checkout-frontend/spec.md - FR-020 (Retry Limits)
 * @see specs/014-stripe-checkout-frontend/contracts/payment-components.schema.ts
 */

import { useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { RefreshCw, AlertTriangle, Mail } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { MAX_PAYMENT_ATTEMPTS, canRetryPayment } from '@/lib/payment'

// ============================================================================
// Types
// ============================================================================

export interface PaymentRetryButtonProps {
  /** Reservation ID for the failed payment */
  reservationId: string
  /** Current number of payment attempts */
  attemptCount: number
  /** Maximum allowed attempts (defaults to MAX_PAYMENT_ATTEMPTS) */
  maxAttempts?: number
  /** Callback when retry is initiated */
  onRetry?: () => void
  /** Callback when max attempts reached */
  onMaxAttemptsReached?: () => void
  /** Whether retry is currently in progress */
  isLoading?: boolean
  /** Custom className for the container */
  className?: string
}

// ============================================================================
// Component
// ============================================================================

/**
 * Payment retry button with attempt tracking.
 *
 * When attempts remain: Shows retry button with attempt counter.
 * When exhausted: Shows contact support message.
 *
 * @example
 * ```tsx
 * <PaymentRetryButton
 *   reservationId="RES-123"
 *   attemptCount={1}
 *   onRetry={() => navigateToPayment()}
 *   onMaxAttemptsReached={() => showSupportModal()}
 * />
 * ```
 */
export function PaymentRetryButton({
  reservationId,
  attemptCount,
  maxAttempts = MAX_PAYMENT_ATTEMPTS,
  onRetry,
  onMaxAttemptsReached,
  isLoading = false,
  className,
}: PaymentRetryButtonProps) {
  const router = useRouter()
  const attemptsRemaining = maxAttempts - attemptCount
  const canRetry = canRetryPayment(attemptCount)

  const handleRetry = useCallback(() => {
    if (!canRetry) {
      onMaxAttemptsReached?.()
      return
    }

    // Call custom handler if provided
    if (onRetry) {
      onRetry()
    } else {
      // Default behavior: navigate back to booking flow
      router.push('/book')
    }
  }, [canRetry, onRetry, onMaxAttemptsReached, router])

  // Max attempts reached - show contact support
  if (!canRetry) {
    return (
      <div className={className}>
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Maximum Payment Attempts Reached</AlertTitle>
          <AlertDescription>
            You&apos;ve reached the maximum of {maxAttempts} payment attempts for this reservation.
            Please contact support for assistance.
          </AlertDescription>
        </Alert>
        <div className="mt-4 flex flex-col sm:flex-row gap-3">
          <Button variant="outline" asChild className="flex-1">
            <a href={`mailto:support@example.com?subject=Payment Issue - ${reservationId}`}>
              <Mail className="mr-2 h-4 w-4" />
              Contact Support
            </a>
          </Button>
        </div>
        <p className="mt-3 text-xs text-muted-foreground text-center">
          Reference: {reservationId}
        </p>
      </div>
    )
  }

  // Can still retry - show button with attempt info
  return (
    <div className={className}>
      <Button
        onClick={handleRetry}
        disabled={isLoading}
        className="w-full sm:w-auto"
      >
        {isLoading ? (
          <>
            <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
            Retrying...
          </>
        ) : (
          <>
            <RefreshCw className="mr-2 h-4 w-4" />
            Try Again
          </>
        )}
      </Button>
      <p className="mt-2 text-sm text-muted-foreground">
        {attemptsRemaining} {attemptsRemaining === 1 ? 'attempt' : 'attempts'} remaining
      </p>
    </div>
  )
}

export default PaymentRetryButton
