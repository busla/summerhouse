'use client'

/**
 * usePricing Hook
 *
 * Fetches pricing data from the backend API based on
 * selected dates to calculate total booking cost.
 *
 * Requirements: FR-009
 */

import { useState, useEffect, useCallback } from 'react'
import { format } from 'date-fns'

export interface PricingData {
  /** Nightly rate for the selected dates */
  nightlyRate: number
  /** Cleaning fee */
  cleaningFee: number
  /** Service fee (if applicable) */
  serviceFee: number
  /** Total cost */
  total: number
  /** Number of nights */
  nights: number
  /** Currency code */
  currency: string
  /** Seasonal pricing info */
  seasonalInfo?: {
    season: string
    minimumNights: number
  }
}

export interface UsePricingOptions {
  /** Check-in date */
  checkIn?: Date | null
  /** Check-out date */
  checkOut?: Date | null
  /** Number of guests (may affect pricing) */
  guests?: number
}

export interface UsePricingReturn {
  /** Calculated pricing data */
  pricing: PricingData | null
  /** Whether pricing is being fetched */
  isLoading: boolean
  /** Error if fetch failed */
  error: Error | null
  /** Refetch pricing data */
  refetch: () => Promise<void>
}

/**
 * Hook to fetch and calculate pricing from the booking API.
 *
 * @example
 * ```tsx
 * const { pricing, isLoading, error } = usePricing({
 *   checkIn: selectedRange?.from,
 *   checkOut: selectedRange?.to,
 *   guests: 2
 * })
 *
 * if (pricing) {
 *   return <PriceBreakdown {...pricing} />
 * }
 * ```
 */
export function usePricing(options: UsePricingOptions = {}): UsePricingReturn {
  const { checkIn, checkOut, guests = 2 } = options

  const [pricing, setPricing] = useState<PricingData | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const fetchPricing = useCallback(async () => {
    // Don't fetch if dates aren't complete
    if (!checkIn || !checkOut) {
      setPricing(null)
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      // Format dates for API query
      const checkInStr = format(checkIn, 'yyyy-MM-dd')
      const checkOutStr = format(checkOut, 'yyyy-MM-dd')

      // Fetch from pricing API endpoint
      // TODO: Replace with actual API endpoint when backend is ready
      const response = await fetch(
        `/api/pricing?check_in=${checkInStr}&check_out=${checkOutStr}&guests=${guests}`
      )

      if (!response.ok) {
        throw new Error(`Failed to fetch pricing: ${response.statusText}`)
      }

      const data = await response.json()

      // Transform API response to PricingData
      setPricing({
        nightlyRate: data.nightly_rate,
        cleaningFee: data.cleaning_fee ?? 50,
        serviceFee: data.service_fee ?? 0,
        total: data.total,
        nights: data.nights,
        currency: data.currency ?? 'EUR',
        seasonalInfo: data.seasonal_info,
      })
    } catch (err) {
      console.warn('Failed to fetch pricing:', err)
      setError(err instanceof Error ? err : new Error('Unknown error'))
      setPricing(null)
    } finally {
      setIsLoading(false)
    }
  }, [checkIn, checkOut, guests])

  // Fetch when dates change
  useEffect(() => {
    if (checkIn && checkOut) {
      fetchPricing()
    } else {
      // Reset pricing when dates are cleared
      setPricing(null)
      setError(null)
    }
  }, [checkIn, checkOut, fetchPricing])

  return {
    pricing,
    isLoading,
    error,
    refetch: fetchPricing,
  }
}

export default usePricing
