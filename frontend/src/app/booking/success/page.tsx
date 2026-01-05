'use client'

/**
 * Payment Success Page
 *
 * Handles return from Stripe Checkout after successful payment.
 * Validates session_id, correlates with stored state, and displays confirmation.
 *
 * Route: /booking/success?session_id=cs_xxx
 *
 * @see specs/014-stripe-checkout-frontend/spec.md - FR-006 to FR-010
 * @see specs/014-stripe-checkout-frontend/contracts/payment-routes.schema.ts
 */

import { useEffect, useState, useMemo, useCallback } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import {
  CheckCircle,
  Home,
  Calendar,
  User,
  CreditCard,
  AlertCircle,
  Loader2,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import {
  useFormPersistence,
  serializeWithDates,
  deserializeWithDates,
} from '@/hooks/useFormPersistence'
import { usePaymentStatus } from '@/hooks/usePaymentStatus'
import { PaymentStatusBadge } from '@/components/booking/PaymentStatusBadge'
import { PaymentRetryButton } from '@/components/booking/PaymentRetryButton'
import { isValidStripeSessionId } from '@/lib/payment'
import type { Payment } from '@/lib/api-client'
import type { DateRange as DayPickerRange } from 'react-day-picker'
import type { GuestDetails } from '@/lib/schemas/booking-form.schema'
// Ensure client is configured
import '@/lib/api-client/config'

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
  | { type: 'validating' }  // Session validated, now polling payment
  | { type: 'invalid_session'; message: string }
  | { type: 'success'; payment: Payment; formState: BookingFormState }
  | { type: 'pending'; payment: Payment; formState: BookingFormState }  // Payment processing
  | { type: 'failed'; payment: Payment; formState: BookingFormState }  // Payment failed
  | { type: 'error'; message: string }

// ============================================================================
// Helpers
// ============================================================================

function formatCurrency(cents: number): string {
  return new Intl.NumberFormat('en-EU', {
    style: 'currency',
    currency: 'EUR',
  }).format(cents / 100)
}

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

export default function PaymentSuccessPage() {
  const searchParams = useSearchParams()
  const sessionId = searchParams.get('session_id')

  const [formState, , clearFormState] = useFormPersistence<BookingFormState>({
    key: STORAGE_KEY,
    initialValue: initialFormState,
    serialize: serializeWithDates,
    deserialize: deserializeWithDates,
  })

  const [pageState, setPageState] = useState<PageState>({ type: 'loading' })
  const [sessionValid, setSessionValid] = useState(false)
  const [hasCleared, setHasCleared] = useState(false)

  // Calculate nights
  const nights = useMemo(() => {
    if (!formState.selectedRange?.from || !formState.selectedRange?.to) return 0
    const diff =
      formState.selectedRange.to.getTime() - formState.selectedRange.from.getTime()
    return Math.ceil(diff / (1000 * 60 * 60 * 24))
  }, [formState.selectedRange])

  // Callback when payment reaches terminal state
  const handlePaymentComplete = useCallback((payment: Payment) => {
    if (payment.status === 'completed') {
      setPageState({
        type: 'success',
        payment,
        formState: { ...formState },
      })
      // Clear sessionStorage after successful payment (FR-009)
      if (!hasCleared) {
        clearFormState()
        setHasCleared(true)
      }
    } else if (payment.status === 'failed') {
      setPageState({
        type: 'failed',
        payment,
        formState: { ...formState },
      })
    } else if (payment.status === 'refunded') {
      // Refund shouldn't happen on success page, but handle gracefully
      setPageState({
        type: 'error',
        message: 'This payment has been refunded. Please contact support.',
      })
    }
  }, [formState, clearFormState, hasCleared])

  // Callback for polling errors
  const handlePaymentError = useCallback((error: string) => {
    setPageState({
      type: 'error',
      message: error,
    })
  }, [])

  // Use the polling hook - only start if session is valid
  const { state: paymentState } = usePaymentStatus({
    reservationId: sessionValid ? formState.reservationId : null,
    autoStart: sessionValid,
    pollInterval: 3000,
    maxAttempts: 20,
    onComplete: handlePaymentComplete,
    onError: handlePaymentError,
  })

  // Validate session on mount (separate from polling)
  useEffect(() => {
    // Validate session_id is present and valid format
    if (!sessionId) {
      setPageState({
        type: 'invalid_session',
        message: 'No session ID provided. Please return to the booking page.',
      })
      return
    }

    if (!isValidStripeSessionId(sessionId)) {
      setPageState({
        type: 'invalid_session',
        message: 'Invalid session ID format. Please return to the booking page.',
      })
      return
    }

    // Check we have a reservation ID in storage
    if (!formState.reservationId) {
      setPageState({
        type: 'invalid_session',
        message:
          'No booking found. Your session may have expired. Please start a new booking.',
      })
      return
    }

    // Optional: Correlate with stored session ID (if we stored it before redirect)
    if (formState.stripeSessionId && formState.stripeSessionId !== sessionId) {
      setPageState({
        type: 'invalid_session',
        message:
          'Session mismatch. This may be a duplicate or stale session. Please check your email for confirmation.',
      })
      return
    }

    // Session is valid - start polling
    setPageState({ type: 'validating' })
    setSessionValid(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]) // Only run on mount and sessionId change

  // Update page state based on payment status (while polling)
  useEffect(() => {
    if (!sessionValid || pageState.type === 'success' || pageState.type === 'failed') {
      return
    }

    if (paymentState.error) {
      setPageState({
        type: 'error',
        message: paymentState.error,
      })
      return
    }

    if (paymentState.payment) {
      if (paymentState.payment.status === 'pending') {
        setPageState({
          type: 'pending',
          payment: paymentState.payment,
          formState: { ...formState },
        })
      } else if (paymentState.payment.status === 'completed' && !hasCleared) {
        // Terminal state reached via polling update
        handlePaymentComplete(paymentState.payment)
      } else if (paymentState.payment.status === 'failed') {
        setPageState({
          type: 'failed',
          payment: paymentState.payment,
          formState: { ...formState },
        })
      }
    }
  }, [sessionValid, paymentState, formState, pageState.type, hasCleared, handlePaymentComplete])

  // Loading/validating state
  if (pageState.type === 'loading' || pageState.type === 'validating') {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16">
        <Card>
          <CardContent className="py-12">
            <div className="flex flex-col items-center justify-center gap-4 text-center">
              <Loader2 className="h-12 w-12 animate-spin text-primary" />
              <div>
                <p className="text-lg font-medium">Verifying your payment...</p>
                <p className="text-sm text-muted-foreground mt-1">
                  Please wait while we confirm your booking
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Pending state - payment is processing
  if (pageState.type === 'pending') {
    const { payment, formState: savedFormState } = pageState
    return (
      <div className="max-w-2xl mx-auto px-4 py-16">
        <Card>
          <CardContent className="py-12">
            <div className="flex flex-col items-center justify-center gap-4 text-center mb-8">
              <Loader2 className="h-12 w-12 animate-spin text-yellow-500" />
              <div>
                <p className="text-lg font-medium">Payment Processing...</p>
                <p className="text-sm text-muted-foreground mt-1">
                  Your payment is being processed. This usually takes just a few seconds.
                </p>
              </div>
              <PaymentStatusBadge status={payment.status} />
            </div>

            {/* Show reservation details while waiting */}
            <div className="p-4 bg-muted rounded-lg">
              <div className="text-sm text-muted-foreground mb-1">Reservation ID</div>
              <div className="text-lg font-mono font-bold text-primary">
                {savedFormState.reservationId}
              </div>
              {savedFormState.guestDetails && (
                <div className="mt-2 text-sm text-muted-foreground">
                  {savedFormState.guestDetails.name} • {savedFormState.guestDetails.email}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Failed state - payment failed
  if (pageState.type === 'failed') {
    const { payment, formState: savedFormState } = pageState
    return (
      <div className="max-w-2xl mx-auto px-4 py-16">
        <Card>
          <CardContent className="py-8">
            <div className="flex flex-col items-center justify-center gap-4 text-center mb-6">
              <AlertCircle className="h-12 w-12 text-destructive" />
              <div>
                <p className="text-lg font-medium text-destructive">Payment Failed</p>
                <p className="text-sm text-muted-foreground mt-1">
                  Unfortunately, your payment could not be processed.
                </p>
              </div>
              <PaymentStatusBadge status={payment.status} />
            </div>

            <Alert variant="destructive" className="mb-6">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>What happened?</AlertTitle>
              <AlertDescription>
                Your payment was declined or failed. This can happen due to insufficient funds,
                card restrictions, or temporary issues with your payment method.
              </AlertDescription>
            </Alert>

            {/* Reservation details */}
            <div className="p-4 bg-muted rounded-lg mb-6">
              <div className="text-sm text-muted-foreground mb-1">Reservation ID</div>
              <div className="text-lg font-mono font-bold">
                {savedFormState.reservationId}
              </div>
            </div>

            {/* Retry Button with attempt tracking */}
            <PaymentRetryButton
              reservationId={savedFormState.reservationId || ''}
              attemptCount={savedFormState.paymentAttempts}
              className="mb-4"
            />

            <Button asChild variant="outline" className="w-full">
              <Link href="/">
                <Home className="mr-2 h-4 w-4" />
                Back to Home
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Invalid session state
  if (pageState.type === 'invalid_session') {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16">
        <Card>
          <CardContent className="py-8">
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Session Invalid</AlertTitle>
              <AlertDescription>{pageState.message}</AlertDescription>
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

  // Error state
  if (pageState.type === 'error') {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16">
        <Card>
          <CardContent className="py-8">
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Verification Error</AlertTitle>
              <AlertDescription>{pageState.message}</AlertDescription>
            </Alert>
            <div className="mt-6 flex justify-center gap-4">
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

  // Success state
  const { payment, formState: savedFormState } = pageState

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      {/* Success Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-100 dark:bg-green-900/30 mb-4">
          <CheckCircle className="h-8 w-8 text-green-600 dark:text-green-400" />
        </div>
        <h1 className="text-3xl font-bold text-foreground">Booking Confirmed!</h1>
        <p className="text-muted-foreground mt-2">
          Thank you for your reservation. A confirmation email has been sent.
        </p>
      </div>

      {/* Confirmation Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Calendar size={24} className="text-primary" />
              Reservation Details
            </CardTitle>
            <Badge variant="default" className="bg-green-600">
              Paid
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Reservation ID */}
          <div className="p-4 bg-muted rounded-lg">
            <div className="text-sm text-muted-foreground mb-1">Reservation ID</div>
            <div className="text-lg font-mono font-bold text-primary">
              {savedFormState.reservationId}
            </div>
          </div>

          {/* Booking Details */}
          <div className="space-y-3">
            {/* Dates */}
            {savedFormState.selectedRange?.from && savedFormState.selectedRange?.to && (
              <div className="flex items-start gap-3">
                <Calendar className="h-5 w-5 text-muted-foreground mt-0.5" />
                <div>
                  <div className="font-medium">
                    {formatDate(savedFormState.selectedRange.from)} -{' '}
                    {formatDate(savedFormState.selectedRange.to)}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {nights} {nights === 1 ? 'night' : 'nights'}
                  </div>
                </div>
              </div>
            )}

            {/* Guest */}
            {savedFormState.guestDetails && (
              <div className="flex items-start gap-3">
                <User className="h-5 w-5 text-muted-foreground mt-0.5" />
                <div>
                  <div className="font-medium">{savedFormState.guestDetails.name}</div>
                  <div className="text-sm text-muted-foreground">
                    {savedFormState.guestDetails.email}
                  </div>
                  {savedFormState.guestDetails.phone && (
                    <div className="text-sm text-muted-foreground">
                      {savedFormState.guestDetails.phone}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Payment */}
            <div className="flex items-start gap-3">
              <CreditCard className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div>
                <div className="font-medium">Payment Complete</div>
                <div className="text-sm text-muted-foreground">
                  {formatCurrency(payment.amount)} paid via{' '}
                  {payment.provider === 'stripe' ? 'Stripe' : payment.provider}
                </div>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="pt-4 border-t border-border">
            <div className="flex flex-col sm:flex-row gap-3">
              <Button asChild className="flex-1">
                <Link href="/">
                  <Home className="mr-2 h-4 w-4" />
                  Back to Home
                </Link>
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Additional Info */}
      <div className="mt-6 text-center text-sm text-muted-foreground">
        <p>
          Questions about your booking? Contact us at{' '}
          <a href="mailto:support@example.com" className="text-primary hover:underline">
            support@example.com
          </a>
        </p>
      </div>
    </div>
  )
}
