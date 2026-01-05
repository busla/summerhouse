'use client'

/**
 * BookingConfirmation Component
 *
 * Displays successful booking confirmation with reservation details.
 * Shows booking summary, guest info, payment status, and next steps.
 *
 * Requirements: FR-011 (booking confirmation display)
 * @see specs/014-stripe-checkout-frontend/spec.md - FR-008 (Payment Status)
 */

import Link from 'next/link'
import { CheckCircle, Calendar, Users, Mail, Phone, Home, CreditCard, Loader2 } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { PaymentStatusBadge } from '@/components/booking/PaymentStatusBadge'
import type { Reservation, Payment } from '@/lib/api-client'

// === Types ===

export interface BookingConfirmationProps {
  /** The created reservation from the API */
  reservation: Reservation
  /** Guest name (from form, not in API response) */
  guestName: string
  /** Guest email (from form) */
  guestEmail: string
  /** Guest phone (from form, optional) */
  guestPhone?: string
  /** Payment information (optional - for payment-enabled flows) */
  payment?: Payment | null
  /** Whether payment status is being fetched/polled */
  isPaymentLoading?: boolean
}

// === Helper Functions ===

/**
 * Format a date string (YYYY-MM-DD) to a readable format.
 */
function formatDate(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00')
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

/**
 * Format cents to euros with currency symbol.
 */
function formatCurrency(cents: number): string {
  return new Intl.NumberFormat('en-EU', {
    style: 'currency',
    currency: 'EUR',
  }).format(cents / 100)
}

// === Component ===

export function BookingConfirmation({
  reservation,
  guestName,
  guestEmail,
  guestPhone,
  payment,
  isPaymentLoading,
}: BookingConfirmationProps) {
  return (
    <Card>
      <CardContent className="py-12">
        {/* Success Header */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-6">
            <div className="w-20 h-20 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center">
              <CheckCircle size={48} className="text-green-600 dark:text-green-400" />
            </div>
          </div>
          <h2 className="text-2xl font-bold text-foreground mb-2">
            Booking Confirmed!
          </h2>
          <p className="text-muted-foreground">
            Thank you, {guestName}! Your reservation has been successfully created.
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            Confirmation #{reservation.reservation_id}
          </p>
        </div>

        {/* Booking Details Card */}
        <div className="max-w-md mx-auto mb-8">
          <div className="bg-muted rounded-lg p-6 space-y-4">
            <h3 className="font-semibold text-lg flex items-center gap-2">
              <Home size={20} className="text-primary" />
              Reservation Details
            </h3>

            {/* Dates */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground uppercase tracking-wide mb-1">
                  <Calendar size={14} />
                  Check-in
                </div>
                <div className="font-medium">{formatDate(reservation.check_in)}</div>
              </div>
              <div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground uppercase tracking-wide mb-1">
                  <Calendar size={14} />
                  Check-out
                </div>
                <div className="font-medium">{formatDate(reservation.check_out)}</div>
              </div>
            </div>

            {/* Guests & Nights */}
            <div className="flex justify-between items-center py-2 border-t border-border">
              <div className="flex items-center gap-2 text-muted-foreground">
                <Users size={16} />
                Guests
              </div>
              <span className="font-medium">
                {reservation.num_adults} adult{reservation.num_adults > 1 ? 's' : ''}
                {reservation.num_children ? `, ${reservation.num_children} child${reservation.num_children > 1 ? 'ren' : ''}` : ''}
              </span>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">Duration</span>
              <span className="font-medium">
                {reservation.nights} night{reservation.nights > 1 ? 's' : ''}
              </span>
            </div>

            {/* Pricing Breakdown */}
            <div className="border-t border-border pt-4 space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">
                  {formatCurrency(reservation.nightly_rate)} x {reservation.nights} nights
                </span>
                <span>{formatCurrency(reservation.nightly_rate * reservation.nights)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Cleaning fee</span>
                <span>{formatCurrency(reservation.cleaning_fee)}</span>
              </div>
              <div className="flex justify-between font-semibold text-lg pt-2 border-t border-border">
                <span>Total</span>
                <span className="text-primary">{formatCurrency(reservation.total_amount)}</span>
              </div>
            </div>

            {/* Payment Status */}
            {(payment || isPaymentLoading) && (
              <div className="border-t border-border pt-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <CreditCard size={16} />
                    <span>Payment</span>
                  </div>
                  {isPaymentLoading ? (
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <Loader2 size={14} className="animate-spin" />
                      <span className="text-sm">Checking status...</span>
                    </div>
                  ) : payment ? (
                    <PaymentStatusBadge status={payment.status} />
                  ) : null}
                </div>
                {payment && payment.status === 'completed' && (
                  <p className="text-xs text-muted-foreground mt-2">
                    Payment confirmed via {payment.provider}
                  </p>
                )}
                {payment && payment.status === 'pending' && (
                  <p className="text-xs text-yellow-600 dark:text-yellow-400 mt-2">
                    Payment is being processed. This may take a few moments.
                  </p>
                )}
                {payment && payment.status === 'failed' && (
                  <p className="text-xs text-destructive mt-2">
                    Payment failed. Please try again or contact support.
                  </p>
                )}
              </div>
            )}

            {/* Special Requests */}
            {typeof reservation.special_requests === 'string' && reservation.special_requests && (
              <div className="border-t border-border pt-4">
                <div className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
                  Special Requests
                </div>
                <p className="text-sm">{reservation.special_requests}</p>
              </div>
            )}
          </div>
        </div>

        {/* Guest Contact Info */}
        <div className="max-w-md mx-auto mb-8">
          <div className="bg-muted/50 rounded-lg p-4 space-y-2">
            <h4 className="text-sm font-medium text-muted-foreground">
              Confirmation sent to:
            </h4>
            <div className="flex items-center gap-2">
              <Mail size={16} className="text-muted-foreground" />
              <span>{guestEmail}</span>
            </div>
            {guestPhone && (
              <div className="flex items-center gap-2">
                <Phone size={16} className="text-muted-foreground" />
                <span>{guestPhone}</span>
              </div>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex justify-center gap-4">
          <Button asChild variant="outline">
            <Link href="/">Return Home</Link>
          </Button>
          <Button asChild>
            <Link href="/agent">Chat with Our Agent</Link>
          </Button>
        </div>

        {/* Help Text */}
        <p className="text-center text-sm text-muted-foreground mt-8">
          Questions about your booking? Our agent is available 24/7 to help.
        </p>
      </CardContent>
    </Card>
  )
}

export default BookingConfirmation
