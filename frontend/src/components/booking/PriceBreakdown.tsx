'use client'

/**
 * PriceBreakdown Component
 *
 * Displays itemized pricing for a booking including
 * nightly rates, fees, and total cost.
 *
 * Requirements: FR-009, FR-010
 */

import { useMemo } from 'react'
import { differenceInDays, format } from 'date-fns'
import { cn } from '@/lib/utils'

export interface PriceBreakdownProps {
  /** Check-in date */
  checkIn: Date
  /** Check-out date */
  checkOut: Date
  /** Nightly rate in euros */
  nightlyRate: number
  /** Cleaning fee in euros */
  cleaningFee?: number
  /** Service fee percentage (default: 0) */
  serviceFeePercent?: number
  /** Whether pricing is loading */
  isLoading?: boolean
  /** Custom class name */
  className?: string
}

export function PriceBreakdown({
  checkIn,
  checkOut,
  nightlyRate,
  cleaningFee = 50,
  serviceFeePercent = 0,
  isLoading = false,
  className,
}: PriceBreakdownProps) {
  // Calculate pricing breakdown
  const pricing = useMemo(() => {
    const nights = differenceInDays(checkOut, checkIn)
    const accommodationTotal = nights * nightlyRate
    const serviceFee = Math.round(accommodationTotal * (serviceFeePercent / 100))
    const total = accommodationTotal + cleaningFee + serviceFee

    return {
      nights,
      accommodationTotal,
      serviceFee,
      total,
    }
  }, [checkIn, checkOut, nightlyRate, cleaningFee, serviceFeePercent])

  // Format currency
  const formatCurrency = (amount: number) =>
    new Intl.NumberFormat('en-EU', {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount)

  if (isLoading) {
    return (
      <div
        className={cn('bg-white rounded-xl p-5 shadow-sm animate-pulse', className)}
        aria-label="Loading pricing..."
      >
        <div className="h-5 bg-gray-200 rounded w-24 mb-4" />
        <div className="space-y-3">
          <div className="h-4 bg-gray-200 rounded w-full" />
          <div className="h-4 bg-gray-200 rounded w-3/4" />
          <div className="h-4 bg-gray-200 rounded w-2/3" />
        </div>
        <div className="border-t border-gray-200 mt-4 pt-4">
          <div className="h-6 bg-gray-200 rounded w-1/2" />
        </div>
      </div>
    )
  }

  return (
    <div
      className={cn('bg-white rounded-xl p-5 shadow-sm border border-gray-100', className)}
    >
      {/* Header with date summary */}
      <div className="mb-4">
        <h3 className="font-semibold text-gray-900">Price Details</h3>
        <p className="text-sm text-gray-500 mt-1">
          {format(checkIn, 'MMM d')} - {format(checkOut, 'MMM d, yyyy')}
        </p>
      </div>

      {/* Line items */}
      <div className="space-y-3">
        {/* Accommodation */}
        <div className="flex justify-between text-sm">
          <span className="text-gray-600">
            {formatCurrency(nightlyRate)} × {pricing.nights} night
            {pricing.nights !== 1 ? 's' : ''}
          </span>
          <span className="text-gray-900">
            {formatCurrency(pricing.accommodationTotal)}
          </span>
        </div>

        {/* Cleaning fee */}
        {cleaningFee > 0 && (
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Cleaning fee</span>
            <span className="text-gray-900">{formatCurrency(cleaningFee)}</span>
          </div>
        )}

        {/* Service fee (if applicable) */}
        {pricing.serviceFee > 0 && (
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Service fee</span>
            <span className="text-gray-900">
              {formatCurrency(pricing.serviceFee)}
            </span>
          </div>
        )}
      </div>

      {/* Total */}
      <div className="border-t border-gray-200 mt-4 pt-4">
        <div className="flex justify-between items-center">
          <span className="font-semibold text-gray-900">Total</span>
          <span className="text-xl font-bold text-gray-900">
            {formatCurrency(pricing.total)}
          </span>
        </div>
        <p className="text-xs text-gray-500 mt-1">
          Includes all taxes and fees
        </p>
      </div>
    </div>
  )
}

export default PriceBreakdown
