'use client'

/**
 * useAvailability Hook
 *
 * Fetches availability data from the backend API to determine
 * which dates are blocked (unavailable for booking).
 *
 * Requirements: FR-008
 */

import { useState, useEffect, useCallback } from 'react'
import { startOfMonth, addMonths, parseISO, format } from 'date-fns'
// Import config first to ensure API client is initialized with base URL
import '@/lib/api-client/config'
import { getCalendarAvailabilityCalendarMonthGet } from '@/lib/api-client/sdk.gen'
import type { CalendarDay } from '@/lib/api-client/types.gen'

export interface AvailabilityData {
  /** Dates that are blocked/unavailable */
  blockedDates: Date[]
  /** Date range that was queried */
  dateRange: {
    start: Date
    end: Date
  }
}

export interface UseAvailabilityOptions {
  /** Start date for availability query (defaults to current month start) */
  startDate?: Date
  /** End date for availability query (defaults to 6 months from start) */
  endDate?: Date
  /** Number of months ahead to fetch (default: 6) */
  monthsAhead?: number
  /** Whether to auto-fetch on mount (default: true) */
  autoFetch?: boolean
}

export interface UseAvailabilityReturn {
  /** Array of unavailable dates */
  blockedDates: Date[]
  /** Whether data is currently loading */
  isLoading: boolean
  /** Error if fetch failed */
  error: Error | null
  /** Refetch availability data */
  refetch: () => Promise<void>
}

/**
 * Hook to fetch availability data from the booking API.
 *
 * @example
 * ```tsx
 * const { blockedDates, isLoading, error } = useAvailability({
 *   monthsAhead: 6
 * })
 *
 * return (
 *   <DateRangePicker disabled={blockedDates} />
 * )
 * ```
 */
export function useAvailability(
  options: UseAvailabilityOptions = {}
): UseAvailabilityReturn {
  const { monthsAhead = 6, autoFetch = true } = options

  const [blockedDates, setBlockedDates] = useState<Date[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const fetchAvailability = useCallback(async () => {
    const startDate = options.startDate ?? startOfMonth(new Date())

    setIsLoading(true)
    setError(null)

    try {
      // Fetch calendar data for each month in the range
      const months: string[] = []
      for (let i = 0; i <= monthsAhead; i++) {
        const monthDate = addMonths(startDate, i)
        months.push(format(monthDate, 'yyyy-MM'))
      }

      // Fetch all months in parallel
      const responses = await Promise.all(
        months.map((month) =>
          getCalendarAvailabilityCalendarMonthGet({
            path: { month },
          })
        )
      )

      // Extract blocked dates from all responses
      const blocked: Date[] = []
      for (const response of responses) {
        if (response.data?.days) {
          for (const day of response.data.days as CalendarDay[]) {
            // Include both 'booked' and 'blocked' status as unavailable
            if (day.status === 'booked' || day.status === 'blocked') {
              blocked.push(parseISO(day.date))
            }
          }
        }
      }

      setBlockedDates(blocked)
    } catch (err) {
      // For MVP, return empty blocked dates on error
      // This allows the UI to still function (calendar shows all dates available)
      console.warn('Failed to fetch availability:', err)
      setError(err instanceof Error ? err : new Error('Unknown error'))
      setBlockedDates([])
    } finally {
      setIsLoading(false)
    }
  }, [options.startDate, monthsAhead])

  // Auto-fetch on mount if enabled
  useEffect(() => {
    if (autoFetch) {
      fetchAvailability()
    }
  }, [autoFetch, fetchAvailability])

  return {
    blockedDates,
    isLoading,
    error,
    refetch: fetchAvailability,
  }
}

export default useAvailability
