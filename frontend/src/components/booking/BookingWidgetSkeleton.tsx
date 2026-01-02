'use client'

/**
 * BookingWidgetSkeleton Component
 *
 * Loading state skeleton for the BookingWidget.
 * Shows animated placeholders while data is loading.
 *
 * Requirements: FR-004 - Loading state for booking widget
 * Uses: shadcn/ui Skeleton component (T016)
 */

import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/skeleton'

export interface BookingWidgetSkeletonProps {
  /** Compact mode for embedding in other sections */
  compact?: boolean
  /** Custom class name */
  className?: string
}

export function BookingWidgetSkeleton({
  compact = false,
  className,
}: BookingWidgetSkeletonProps) {
  return (
    <div
      className={cn(
        'bg-card rounded-2xl shadow-lg overflow-hidden border border-border',
        className
      )}
      role="status"
      aria-label="Loading booking widget"
    >
      <div
        className={cn(
          'flex flex-col items-center text-center gap-4',
          'md:flex-row md:text-left md:gap-6',
          compact ? 'p-5' : 'p-8'
        )}
      >
        {/* Icon placeholder */}
        <Skeleton
          className={cn(
            'rounded-xl shrink-0',
            compact ? 'w-12 h-12' : 'w-16 h-16'
          )}
        />

        {/* Text content placeholder */}
        <div className="grow space-y-2 w-full md:w-auto">
          <Skeleton
            className={cn(
              'mx-auto md:mx-0',
              compact ? 'h-4 w-24' : 'h-6 w-48'
            )}
          />
          <Skeleton
            className={cn(
              'mx-auto md:mx-0',
              compact ? 'h-3 w-32' : 'h-4 w-64'
            )}
          />
        </div>

        {/* Button placeholder */}
        <Skeleton
          className={cn(
            'rounded-lg shrink-0',
            compact ? 'h-10 w-32' : 'h-12 w-40'
          )}
        />
      </div>
    </div>
  )
}

export default BookingWidgetSkeleton
