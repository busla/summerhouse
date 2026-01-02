'use client'

/**
 * Book Page
 *
 * Multi-step booking flow for direct reservations.
 * Steps: Date selection → Price review → Guest details → Confirmation
 *
 * Requirements: FR-011
 * Uses: BookingWidget (T015), GuestDetailsForm (T025), useCreateReservation (T030)
 */

import { useState, useCallback } from 'react'
import Link from 'next/link'
import { ArrowLeft, ArrowRight, Calendar, User, CheckCircle, AlertCircle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { DateRangePicker } from '@/components/booking/DateRangePicker'
import { PriceBreakdown } from '@/components/booking/PriceBreakdown'
import { GuestDetailsForm } from '@/components/booking/GuestDetailsForm'
import { BookingConfirmation } from '@/components/booking/BookingConfirmation'
import { usePricing } from '@/hooks/usePricing'
import { useAvailability } from '@/hooks/useAvailability'
import { useCreateReservation } from '@/hooks/useCreateReservation'
import type { DateRange as DayPickerRange } from 'react-day-picker'
import type { GuestDetails } from '@/lib/schemas/booking-form.schema'
import type { Reservation } from '@/lib/api-client'

// Step definition for the booking flow
type BookingStep = 'dates' | 'guest' | 'confirmation'

const STEPS: { key: BookingStep; label: string; icon: React.ReactNode }[] = [
  { key: 'dates', label: 'Select Dates', icon: <Calendar size={18} /> },
  { key: 'guest', label: 'Guest Details', icon: <User size={18} /> },
  { key: 'confirmation', label: 'Confirmation', icon: <CheckCircle size={18} /> },
]

export default function BookPage() {
  const [currentStep, setCurrentStep] = useState<BookingStep>('dates')
  const [selectedRange, setSelectedRange] = useState<DayPickerRange | undefined>()
  const [guestDetails, setGuestDetails] = useState<GuestDetails | null>(null)
  const [reservation, setReservation] = useState<Reservation | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Fetch availability (blocked dates)
  const { blockedDates, isLoading: availabilityLoading } = useAvailability()

  // Fetch pricing when dates are selected
  const { pricing, isLoading: pricingLoading } = usePricing({
    checkIn: selectedRange?.from,
    checkOut: selectedRange?.to,
  })

  // Reservation creation mutation
  const { createReservation, isLoading: isSubmitting } = useCreateReservation()

  const hasCompleteDates = selectedRange?.from && selectedRange?.to

  const handleDatesChange = useCallback((range: DayPickerRange | undefined) => {
    setSelectedRange(range)
  }, [])

  const handleContinueToGuest = useCallback(() => {
    if (hasCompleteDates) {
      setCurrentStep('guest')
    }
  }, [hasCompleteDates])

  const handleBackToDates = useCallback(() => {
    setCurrentStep('dates')
  }, [])

  const handleGuestSubmit = useCallback(async (data: GuestDetails) => {
    if (!selectedRange?.from || !selectedRange?.to) {
      setSubmitError('Please select dates first')
      return
    }

    setGuestDetails(data)
    setSubmitError(null)

    // Create the reservation via API
    const result = await createReservation({
      checkIn: selectedRange.from,
      checkOut: selectedRange.to,
      numAdults: data.guestCount, // Form captures total guests as adults
      numChildren: 0, // MVP: no separate child count in form
      specialRequests: data.specialRequests,
    })

    if (result.error) {
      setSubmitError(result.error)
      return
    }

    if (result.reservation) {
      setReservation(result.reservation)
      setCurrentStep('confirmation')
    }
  }, [selectedRange, createReservation])

  // Step indicator component
  const StepIndicator = () => (
    <div className="flex items-center justify-center gap-2 mb-8">
      {STEPS.map((step, index) => {
        const stepIndex = STEPS.findIndex((s) => s.key === currentStep)
        const isActive = step.key === currentStep
        const isCompleted = index < stepIndex

        return (
          <div key={step.key} className="flex items-center">
            <div
              className={`
                flex items-center justify-center w-10 h-10 rounded-full border-2 transition-colors
                ${isActive ? 'border-primary bg-primary text-primary-foreground' : ''}
                ${isCompleted ? 'border-primary bg-primary/10 text-primary' : ''}
                ${!isActive && !isCompleted ? 'border-muted-foreground/30 text-muted-foreground' : ''}
              `}
            >
              {isCompleted ? <CheckCircle size={20} /> : step.icon}
            </div>
            {index < STEPS.length - 1 && (
              <div
                className={`w-12 h-0.5 mx-2 ${
                  isCompleted ? 'bg-primary' : 'bg-muted-foreground/30'
                }`}
              />
            )}
          </div>
        )
      })}
    </div>
  )

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Back to Home */}
      <Link
        href="/"
        className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-6 transition-colors"
      >
        <ArrowLeft size={18} />
        Back to Home
      </Link>

      <h1 className="text-3xl font-bold text-foreground mb-2">Book Your Stay</h1>
      <p className="text-muted-foreground mb-8">
        Complete your reservation in a few simple steps
      </p>

      <StepIndicator />

      {/* Step 1: Date Selection */}
      {currentStep === 'dates' && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calendar size={24} className="text-primary" />
              Select Your Dates
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <DateRangePicker
              selected={selectedRange}
              onSelect={handleDatesChange}
              disabled={blockedDates}
              numberOfMonths={2}
              minNights={2}
              className={availabilityLoading ? 'opacity-50' : ''}
            />

            {hasCompleteDates && (
              <PriceBreakdown
                checkIn={selectedRange.from!}
                checkOut={selectedRange.to!}
                nightlyRate={pricing?.nightlyRate ?? 120}
                cleaningFee={pricing?.cleaningFee ?? 50}
                serviceFeePercent={0}
                isLoading={pricingLoading}
              />
            )}

            <div className="flex justify-end">
              <Button
                size="lg"
                disabled={!hasCompleteDates}
                onClick={handleContinueToGuest}
              >
                Continue to Guest Details
                <ArrowRight size={18} />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Guest Details */}
      {currentStep === 'guest' && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User size={24} className="text-primary" />
              Guest Details
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* Summary of selected dates */}
            {hasCompleteDates && (
              <div className="mb-6 p-4 bg-muted rounded-lg">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Check-in:</span>
                  <span className="font-medium">
                    {selectedRange.from!.toLocaleDateString('en-US', {
                      weekday: 'short',
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    })}
                  </span>
                </div>
                <div className="flex justify-between text-sm mt-1">
                  <span className="text-muted-foreground">Check-out:</span>
                  <span className="font-medium">
                    {selectedRange.to!.toLocaleDateString('en-US', {
                      weekday: 'short',
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    })}
                  </span>
                </div>
                {pricing && (
                  <div className="flex justify-between text-sm mt-2 pt-2 border-t border-border">
                    <span className="text-muted-foreground">Total:</span>
                    <span className="font-bold text-primary">
                      &euro;{pricing.total}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Error Display */}
            {submitError && (
              <div className="mb-6 p-4 bg-destructive/10 border border-destructive/20 rounded-lg flex items-start gap-3">
                <AlertCircle size={20} className="text-destructive flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-destructive">Booking Failed</p>
                  <p className="text-sm text-destructive/80">{submitError}</p>
                </div>
              </div>
            )}

            <GuestDetailsForm
              onSubmit={handleGuestSubmit}
              isSubmitting={isSubmitting}
            >
              <div className="flex justify-between gap-4 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  size="lg"
                  onClick={handleBackToDates}
                  disabled={isSubmitting}
                >
                  <ArrowLeft size={18} />
                  Back
                </Button>
                <Button type="submit" size="lg" disabled={isSubmitting}>
                  {isSubmitting ? 'Processing...' : 'Complete Booking'}
                  {!isSubmitting && <ArrowRight size={18} />}
                </Button>
              </div>
            </GuestDetailsForm>
          </CardContent>
        </Card>
      )}

      {/* Step 3: Confirmation */}
      {currentStep === 'confirmation' && reservation && guestDetails && (
        <BookingConfirmation
          reservation={reservation}
          guestName={guestDetails.name}
          guestEmail={guestDetails.email}
          guestPhone={guestDetails.phone}
        />
      )}
    </div>
  )
}
