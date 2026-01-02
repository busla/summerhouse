'use client'

/**
 * DateRangePicker Component
 *
 * Wraps shadcn Calendar for check-in/check-out date selection.
 * Supports blocked dates (unavailable) and minimum night stays.
 *
 * Requirements: FR-007, FR-008
 */

import { useState, useCallback } from 'react'
import { DateRange } from 'react-day-picker'
import { format, isBefore, startOfDay, addDays } from 'date-fns'
import { Calendar } from '@/components/ui/calendar'
import { cn } from '@/lib/utils'

export interface DateRangePickerProps {
  /** Currently selected date range */
  selected?: DateRange
  /** Callback when date range changes */
  onSelect?: (range: DateRange | undefined) => void
  /** Dates that are unavailable for booking */
  disabled?: Date[]
  /** Number of months to display (default: 2) */
  numberOfMonths?: number
  /** Minimum nights required for booking */
  minNights?: number
  /** Custom class name */
  className?: string
}

export function DateRangePicker({
  selected,
  onSelect,
  disabled = [],
  numberOfMonths = 2,
  minNights = 2,
  className,
}: DateRangePickerProps) {
  const [month, setMonth] = useState<Date>(new Date())

  // Create date matchers for disabled dates
  const disabledDates = [
    // Past dates (before today)
    { before: startOfDay(new Date()) },
    // Blocked dates from availability API
    ...disabled,
  ]

  // Handle date selection with minimum nights validation
  const handleSelect = useCallback(
    (range: DateRange | undefined) => {
      if (!range || !onSelect) return

      // If only from date is selected, allow it (user is still selecting)
      if (range.from && !range.to) {
        onSelect(range)
        return
      }

      // If both dates selected, validate minimum nights
      if (range.from && range.to) {
        const minCheckout = addDays(range.from, minNights)
        if (isBefore(range.to, minCheckout)) {
          // Auto-adjust to minimum nights
          onSelect({ from: range.from, to: minCheckout })
          return
        }
        onSelect(range)
      }
    },
    [onSelect, minNights]
  )

  return (
    <div className={cn('date-range-picker', className)}>
      <Calendar
        mode="range"
        selected={selected}
        onSelect={handleSelect}
        onMonthChange={setMonth}
        month={month}
        numberOfMonths={numberOfMonths}
        disabled={disabledDates}
        showOutsideDays={false}
      />

      {/* Selected dates display */}
      {selected?.from && (
        <div className="mt-4 p-3 bg-muted rounded-lg text-sm">
          <div className="flex justify-between">
            <span className="font-medium">Check-in:</span>
            <span>{format(selected.from, 'EEE, MMM d, yyyy')}</span>
          </div>
          {selected.to && (
            <div className="flex justify-between mt-1">
              <span className="font-medium">Check-out:</span>
              <span>{format(selected.to, 'EEE, MMM d, yyyy')}</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default DateRangePicker
