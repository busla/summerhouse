'use client'

/**
 * GuestCountSelector Component
 *
 * Dropdown selector for number of guests (1-4).
 * Uses shadcn Select for consistent styling.
 *
 * Requirements: FR-013
 */

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import { MAX_GUESTS, MIN_GUESTS } from '@/lib/schemas/booking-form.schema'

export interface GuestCountSelectorProps {
  /** Current value */
  value?: number
  /** Callback when value changes */
  onChange?: (value: number) => void
  /** Maximum guests allowed (default: 4) */
  max?: number
  /** Minimum guests allowed (default: 1) */
  min?: number
  /** Whether the selector is disabled */
  disabled?: boolean
  /** Custom class name */
  className?: string
  /** Error state */
  hasError?: boolean
}

export function GuestCountSelector({
  value,
  onChange,
  max = MAX_GUESTS,
  min = MIN_GUESTS,
  disabled = false,
  className,
  hasError = false,
}: GuestCountSelectorProps) {
  // Generate options array
  const options = Array.from(
    { length: max - min + 1 },
    (_, i) => min + i
  )

  const handleValueChange = (newValue: string) => {
    const numValue = parseInt(newValue, 10)
    if (!isNaN(numValue) && onChange) {
      onChange(numValue)
    }
  }

  return (
    <Select
      value={value?.toString()}
      onValueChange={handleValueChange}
      disabled={disabled}
    >
      <SelectTrigger
        className={cn(
          'w-full',
          hasError && 'border-red-500 focus:ring-red-500',
          className
        )}
        aria-label="Select number of guests"
      >
        <SelectValue placeholder="Select guests" />
      </SelectTrigger>
      <SelectContent>
        {options.map((num) => (
          <SelectItem key={num} value={num.toString()}>
            {num} {num === 1 ? 'guest' : 'guests'}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

export default GuestCountSelector
