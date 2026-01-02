'use client'

/**
 * BookingWidget Component
 *
 * Container for date selection, pricing display, and booking initiation.
 * Integrates DateRangePicker, PriceBreakdown, and booking CTA.
 *
 * Requirements: FR-004, FR-005, FR-009, FR-010
 * Uses: shadcn/ui Card + Button (T015, T018d, T024)
 */

import { useState, useCallback } from 'react'
import Link from 'next/link'
import { Calendar, ArrowRight } from 'lucide-react'
import { DateRange as DayPickerRange } from 'react-day-picker'
import { cn } from '@/lib/utils'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { DateRangePicker } from './DateRangePicker'
import { PriceBreakdown } from './PriceBreakdown'
import { usePricing } from '@/hooks/usePricing'
import { useAvailability } from '@/hooks/useAvailability'
import type { DateRange } from '@/lib/schemas/booking-form.schema'

export interface BookingWidgetProps {
  /** Callback when dates change */
  onDatesChange?: (dates: DateRange | null) => void
  /** Callback when user clicks book */
  onBook?: (dates: DateRange) => void
  /** Compact mode - shows CTA only, no date picker */
  compact?: boolean
  /** Custom class name */
  className?: string
  /** Default nightly rate in EUR (used before API response) */
  defaultRate?: number
}

export function BookingWidget({
  onDatesChange,
  onBook,
  compact = false,
  className,
  defaultRate = 120,
}: BookingWidgetProps) {
  const [selectedRange, setSelectedRange] = useState<DayPickerRange | undefined>()
  const [error, setError] = useState<string | null>(null)

  // Fetch availability (blocked dates)
  const { blockedDates, isLoading: availabilityLoading } = useAvailability()

  // Fetch pricing when dates are selected
  const { pricing, isLoading: pricingLoading } = usePricing({
    checkIn: selectedRange?.from,
    checkOut: selectedRange?.to,
  })

  // Convert DayPickerRange (from/to) to our DateRange type (checkIn/checkOut)
  const toDateRange = (range: DayPickerRange | undefined): DateRange | null => {
    if (!range?.from || !range?.to) return null
    return { checkIn: range.from, checkOut: range.to }
  }

  const handleDatesChange = useCallback(
    (range: DayPickerRange | undefined) => {
      setSelectedRange(range)
      setError(null)
      onDatesChange?.(toDateRange(range))
    },
    [onDatesChange]
  )

  const handleBook = useCallback(() => {
    const dateRange = toDateRange(selectedRange)
    if (!dateRange) {
      setError('Please select your check-in and check-out dates')
      return
    }
    onBook?.(dateRange)
  }, [selectedRange, onBook])

  // Compact mode: Simple CTA linking to /book page
  if (compact) {
    return (
      <Card className={cn('overflow-hidden', className)}>
        <CardContent className="p-5">
          <div className="flex flex-col items-center text-center gap-4 md:flex-row md:text-left md:gap-6">
            {/* Icon */}
            <div className="flex items-center justify-center w-12 h-12 bg-primary/10 rounded-xl text-primary shrink-0">
              <Calendar size={24} strokeWidth={1.5} />
            </div>

            {/* Text content */}
            <div className="grow">
              <h3 className="font-semibold text-foreground mb-1 text-base">
                Book Now
              </h3>
              <p className="text-muted-foreground text-sm leading-normal">
                Check availability and rates
              </p>
            </div>

            {/* CTA Button */}
            <Button asChild className="shrink-0">
              <Link href="/book">
                Check Availability
                <ArrowRight size={18} aria-hidden="true" />
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  // Full mode: Date picker + pricing
  const hasCompleteDates = selectedRange?.from && selectedRange?.to

  return (
    <Card className={cn('overflow-hidden', className)} role="region" aria-label="Booking widget">
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center gap-2 text-xl">
          <Calendar size={24} className="text-primary" />
          Select Your Dates
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Date Range Picker */}
        <DateRangePicker
          selected={selectedRange}
          onSelect={handleDatesChange}
          disabled={blockedDates}
          numberOfMonths={2}
          minNights={2}
          className={availabilityLoading ? 'opacity-50' : ''}
        />

        {/* Price Breakdown - shown when dates selected */}
        {hasCompleteDates && (
          <PriceBreakdown
            checkIn={selectedRange.from!}
            checkOut={selectedRange.to!}
            nightlyRate={pricing?.nightlyRate ?? defaultRate}
            cleaningFee={pricing?.cleaningFee ?? 50}
            serviceFeePercent={0}
            isLoading={pricingLoading}
          />
        )}

        {/* Error message */}
        {error && (
          <p
            className="p-3 bg-destructive/10 rounded-md text-sm text-destructive"
            role="alert"
          >
            {error}
          </p>
        )}

        {/* Booking CTA */}
        <div className="flex flex-col sm:flex-row gap-3">
          <Button
            size="lg"
            className="flex-1"
            disabled={!hasCompleteDates}
            onClick={handleBook}
          >
            {hasCompleteDates ? 'Continue to Guest Details' : 'Select Dates to Continue'}
            <ArrowRight size={18} aria-hidden="true" />
          </Button>

          {hasCompleteDates && (
            <Button variant="outline" size="lg" asChild>
              <Link href="/agent">Ask Our Agent</Link>
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export default BookingWidget
