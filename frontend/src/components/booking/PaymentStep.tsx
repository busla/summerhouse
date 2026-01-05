'use client'

/**
 * PaymentStep Component
 *
 * Displays booking summary and initiates Stripe Checkout redirect.
 * Part of the 4-step booking flow: dates → guest → payment → confirmation.
 *
 * @see specs/014-stripe-checkout-frontend/spec.md - FR-001, FR-002, FR-003, FR-017, FR-021
 * @see specs/014-stripe-checkout-frontend/contracts/checkout-session.types.ts
 */

import { CreditCard, Loader2, ExternalLink, AlertCircle, X } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useCheckoutSession } from '@/hooks/useCheckoutSession'

// ============================================================================
// Types
// ============================================================================

export interface PaymentStepProps {
  /** Reservation ID to create checkout session for */
  reservationId: string
  /** Total amount in cents (EUR) */
  totalAmount: number
  /** Check-in date */
  checkIn: Date
  /** Check-out date */
  checkOut: Date
  /** Guest name for display */
  guestName: string
  /** Number of nights */
  nights: number
  /** Callback when payment is initiated (before redirect) */
  onPaymentInitiated?: () => void
  /** Callback on error */
  onError?: (error: string) => void
  /** Callback to go back to previous step */
  onBack?: () => void
}

// ============================================================================
// Helpers
// ============================================================================

/**
 * Format cents to EUR currency string.
 */
function formatCurrency(cents: number): string {
  return new Intl.NumberFormat('en-EU', {
    style: 'currency',
    currency: 'EUR',
  }).format(cents / 100)
}

/**
 * Format date for display.
 */
function formatDate(date: Date): string {
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

// ============================================================================
// Component
// ============================================================================

export function PaymentStep({
  reservationId,
  totalAmount,
  checkIn,
  checkOut,
  guestName,
  nights,
  onPaymentInitiated,
  onError,
  onBack,
}: PaymentStepProps) {
  const { state, createSession, clearError } = useCheckoutSession()
  const { isLoading, isRedirecting, error } = state

  const handlePayment = async () => {
    const result = await createSession(reservationId)

    if (result.error) {
      onError?.(result.error)
    } else {
      onPaymentInitiated?.()
      // Note: User will be redirected to Stripe at this point
    }
  }

  const handleDismissError = () => {
    clearError()
  }

  // Redirecting state - show loading with external link indicator
  if (isRedirecting) {
    return (
      <Card>
        <CardContent className="py-12">
          <div className="flex flex-col items-center justify-center gap-4 text-center">
            <div className="relative">
              <Loader2 className="h-12 w-12 animate-spin text-primary" />
              <ExternalLink className="absolute -right-1 -top-1 h-4 w-4 text-muted-foreground" />
            </div>
            <div>
              <p className="text-lg font-medium">Redirecting to payment...</p>
              <p className="text-sm text-muted-foreground mt-1">
                You&apos;ll be taken to Stripe&apos;s secure checkout page
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CreditCard size={24} className="text-primary" />
          Complete Payment
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Booking Summary */}
        <div className="rounded-lg bg-muted p-4 space-y-3">
          <h3 className="font-medium text-sm text-muted-foreground uppercase tracking-wide">
            Booking Summary
          </h3>
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Guest</span>
              <span className="font-medium">{guestName}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Check-in</span>
              <span className="font-medium">{formatDate(checkIn)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Check-out</span>
              <span className="font-medium">{formatDate(checkOut)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Duration</span>
              <span className="font-medium">
                {nights} {nights === 1 ? 'night' : 'nights'}
              </span>
            </div>
          </div>
          <div className="border-t border-border pt-3 mt-3">
            <div className="flex justify-between">
              <span className="font-medium">Total</span>
              <span className="text-xl font-bold text-primary">
                {formatCurrency(totalAmount)}
              </span>
            </div>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription className="flex items-center justify-between">
              <span>{error}</span>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0 hover:bg-destructive/20"
                onClick={handleDismissError}
              >
                <X className="h-4 w-4" />
                <span className="sr-only">Dismiss</span>
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {/* Payment Info */}
        <div className="text-sm text-muted-foreground text-center">
          <p>You&apos;ll be redirected to Stripe&apos;s secure checkout page.</p>
          <p className="mt-1">Your booking will be confirmed after successful payment.</p>
        </div>

        {/* Action Buttons */}
        <div className="flex justify-between gap-4 pt-2">
          {onBack && (
            <Button
              type="button"
              variant="outline"
              size="lg"
              onClick={onBack}
              disabled={isLoading}
            >
              Back
            </Button>
          )}
          <Button
            size="lg"
            onClick={handlePayment}
            disabled={isLoading}
            className={onBack ? '' : 'w-full'}
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Creating session...
              </>
            ) : (
              <>
                <CreditCard className="mr-2 h-4 w-4" />
                Proceed to Payment
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export default PaymentStep
