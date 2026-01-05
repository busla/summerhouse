'use client'

/**
 * Payment Cancel Page
 *
 * Handles return from Stripe Checkout when user cancels or abandons payment.
 * Preserves form state and offers retry options.
 *
 * Route: /booking/cancel
 *
 * @see specs/014-stripe-checkout-frontend/spec.md - FR-011 to FR-014
 */

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { XCircle, ArrowLeft, CreditCard, Home, AlertTriangle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import {
  useFormPersistence,
  serializeWithDates,
  deserializeWithDates,
} from '@/hooks/useFormPersistence'
import { MAX_PAYMENT_ATTEMPTS, canRetryPayment } from '@/lib/payment'
import type { DateRange as DayPickerRange } from 'react-day-picker'
import type { GuestDetails } from '@/lib/schemas/booking-form.schema'

// ============================================================================
// Types
// ============================================================================

/** Storage key matching book page */
const STORAGE_KEY = 'booking-form-state'

/** Persisted form state shape (must match book page) */
interface BookingFormState {
  currentStep: string
  selectedRange: DayPickerRange | undefined
  guestDetails: GuestDetails | null
  reservationId: string | null
  paymentAttempts: number
  lastPaymentError: string | null
  stripeSessionId: string | null
}

const initialFormState: BookingFormState = {
  currentStep: 'dates',
  selectedRange: undefined,
  guestDetails: null,
  reservationId: null,
  paymentAttempts: 0,
  lastPaymentError: null,
  stripeSessionId: null,
}

type PageState =
  | { type: 'loading' }
  | { type: 'no_booking' }
  | { type: 'cancelled'; formState: BookingFormState; canRetry: boolean }
  | { type: 'max_attempts'; formState: BookingFormState }

// ============================================================================
// Helpers
// ============================================================================

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

export default function PaymentCancelPage() {
  const router = useRouter()

  const [formState, setFormState] = useFormPersistence<BookingFormState>({
    key: STORAGE_KEY,
    initialValue: initialFormState,
    serialize: serializeWithDates,
    deserialize: deserializeWithDates,
  })

  const [pageState, setPageState] = useState<PageState>({ type: 'loading' })

  useEffect(() => {
    // Check if we have booking data to restore
    if (!formState.reservationId) {
      setPageState({ type: 'no_booking' })
      return
    }

    // Track this as a payment attempt (user abandoned checkout)
    const newAttempts = formState.paymentAttempts + 1

    // Update state with incremented attempts
    setFormState((prev) => ({
      ...prev,
      paymentAttempts: newAttempts,
      lastPaymentError: 'Payment was cancelled',
      // Reset to payment step so they can retry
      currentStep: 'payment',
    }))

    // Check if they've exceeded max attempts
    if (!canRetryPayment(newAttempts)) {
      setPageState({
        type: 'max_attempts',
        formState: { ...formState, paymentAttempts: newAttempts },
      })
    } else {
      setPageState({
        type: 'cancelled',
        formState: { ...formState, paymentAttempts: newAttempts },
        canRetry: true,
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Only run on mount

  const handleRetryPayment = () => {
    // Navigate back to booking page - form state is already preserved
    // The payment step will be shown since currentStep is 'payment'
    router.push('/book')
  }

  // Loading state
  if (pageState.type === 'loading') {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16">
        <Card>
          <CardContent className="py-12">
            <div className="flex flex-col items-center justify-center gap-4 text-center">
              <div className="h-12 w-12 rounded-full bg-muted animate-pulse" />
              <p className="text-muted-foreground">Loading...</p>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // No booking found
  if (pageState.type === 'no_booking') {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16">
        <Card>
          <CardContent className="py-8">
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>No Booking Found</AlertTitle>
              <AlertDescription>
                We couldn&apos;t find an active booking to resume. Your session may have expired.
              </AlertDescription>
            </Alert>
            <div className="mt-6 flex justify-center">
              <Button asChild>
                <Link href="/book">
                  <Home className="mr-2 h-4 w-4" />
                  Start New Booking
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Max attempts reached
  if (pageState.type === 'max_attempts') {
    const { formState: savedFormState } = pageState

    return (
      <div className="max-w-2xl mx-auto px-4 py-8">
        {/* Error Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-destructive/10 mb-4">
            <AlertTriangle className="h-8 w-8 text-destructive" />
          </div>
          <h1 className="text-3xl font-bold text-foreground">Payment Attempts Exceeded</h1>
          <p className="text-muted-foreground mt-2">
            You&apos;ve reached the maximum number of payment attempts ({MAX_PAYMENT_ATTEMPTS}).
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Need Help?</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Booking Summary */}
            {savedFormState.selectedRange?.from && savedFormState.selectedRange?.to && (
              <div className="p-4 bg-muted rounded-lg">
                <div className="text-sm text-muted-foreground mb-2">Your booking details:</div>
                <div className="space-y-1 text-sm">
                  <div>
                    <span className="text-muted-foreground">Dates:</span>{' '}
                    <span className="font-medium">
                      {formatDate(savedFormState.selectedRange.from)} -{' '}
                      {formatDate(savedFormState.selectedRange.to)}
                    </span>
                  </div>
                  {savedFormState.guestDetails && (
                    <div>
                      <span className="text-muted-foreground">Guest:</span>{' '}
                      <span className="font-medium">{savedFormState.guestDetails.name}</span>
                    </div>
                  )}
                  {savedFormState.reservationId && (
                    <div>
                      <span className="text-muted-foreground">Reservation:</span>{' '}
                      <span className="font-mono text-xs">{savedFormState.reservationId}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Contact Support</AlertTitle>
              <AlertDescription>
                Please contact us for assistance with your booking. We&apos;re happy to help resolve any
                payment issues.
              </AlertDescription>
            </Alert>

            <div className="text-center">
              <p className="text-sm text-muted-foreground mb-4">
                Contact us at{' '}
                <a href="mailto:support@example.com" className="text-primary hover:underline">
                  support@example.com
                </a>
              </p>
              <Button variant="outline" asChild>
                <Link href="/">
                  <Home className="mr-2 h-4 w-4" />
                  Back to Home
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Cancelled state with retry option
  const { formState: savedFormState } = pageState

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      {/* Cancel Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-amber-100 dark:bg-amber-900/30 mb-4">
          <XCircle className="h-8 w-8 text-amber-600 dark:text-amber-400" />
        </div>
        <h1 className="text-3xl font-bold text-foreground">Payment Not Completed</h1>
        <p className="text-muted-foreground mt-2">
          Your payment was cancelled or not completed. Your booking details have been saved.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CreditCard size={24} className="text-primary" />
            Resume Your Booking
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Booking Summary */}
          {savedFormState.selectedRange?.from && savedFormState.selectedRange?.to && (
            <div className="p-4 bg-muted rounded-lg">
              <div className="text-sm text-muted-foreground mb-2">Your saved booking:</div>
              <div className="space-y-1 text-sm">
                <div>
                  <span className="text-muted-foreground">Check-in:</span>{' '}
                  <span className="font-medium">
                    {formatDate(savedFormState.selectedRange.from)}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">Check-out:</span>{' '}
                  <span className="font-medium">
                    {formatDate(savedFormState.selectedRange.to)}
                  </span>
                </div>
                {savedFormState.guestDetails && (
                  <div>
                    <span className="text-muted-foreground">Guest:</span>{' '}
                    <span className="font-medium">{savedFormState.guestDetails.name}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Attempt Counter */}
          {savedFormState.paymentAttempts > 0 && (
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                Payment attempt {savedFormState.paymentAttempts} of {MAX_PAYMENT_ATTEMPTS}.{' '}
                {MAX_PAYMENT_ATTEMPTS - savedFormState.paymentAttempts} attempts remaining.
              </AlertDescription>
            </Alert>
          )}

          {/* Info Text */}
          <div className="text-sm text-muted-foreground text-center">
            <p>Click below to return to the payment step and complete your booking.</p>
            <p className="mt-1">All your details have been saved.</p>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row gap-3 pt-2">
            <Button variant="outline" asChild className="flex-1">
              <Link href="/">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Home
              </Link>
            </Button>
            <Button onClick={handleRetryPayment} className="flex-1">
              <CreditCard className="mr-2 h-4 w-4" />
              Try Again
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Additional Info */}
      <div className="mt-6 text-center text-sm text-muted-foreground">
        <p>
          Having trouble? Contact us at{' '}
          <a href="mailto:support@example.com" className="text-primary hover:underline">
            support@example.com
          </a>
        </p>
      </div>
    </div>
  )
}
