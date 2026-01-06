'use client'

/**
 * GuestDetailsForm Component (Simplified per FR-018)
 *
 * Collects guest count and special requests for booking.
 * Name, email, and phone are now collected in the AuthStep component.
 *
 * This is a simplified version that only handles:
 * - Guest count (1-4 guests)
 * - Special requests (optional)
 *
 * Requirements: FR-012, FR-013, FR-018
 */

import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { cn } from '@/lib/utils'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  simplifiedGuestDetailsSchema,
  MAX_GUESTS,
  MIN_GUESTS,
  type SimplifiedGuestDetails,
} from '@/lib/schemas/booking-form.schema'

export interface GuestDetailsFormProps {
  /** Initial values for the form */
  defaultValues?: Partial<SimplifiedGuestDetails>
  /** Callback when form is submitted with valid data */
  onSubmit: (data: SimplifiedGuestDetails) => void
  /** Callback when form values change (for persistence) */
  onChange?: (values: Partial<SimplifiedGuestDetails>) => void
  /** Whether the form is submitting */
  isSubmitting?: boolean
  /** Custom class name */
  className?: string
  /** Children to render (e.g., navigation buttons) */
  children?: React.ReactNode
}

/**
 * Simplified guest details form.
 * Collects only guest count and special requests - identity fields are in AuthStep.
 */
export function GuestDetailsForm({
  defaultValues,
  onSubmit,
  onChange,
  isSubmitting = false,
  className,
  children,
}: GuestDetailsFormProps) {
  const form = useForm<SimplifiedGuestDetails>({
    resolver: zodResolver(simplifiedGuestDetailsSchema),
    defaultValues: {
      guestCount: 2,
      specialRequests: '',
      ...defaultValues,
    },
    mode: 'onBlur',
  })

  // Subscribe to form value changes for persistence callback
  useEffect(() => {
    if (!onChange) return
    const subscription = form.watch((values) => {
      onChange(values as Partial<SimplifiedGuestDetails>)
    })
    return () => subscription.unsubscribe()
  }, [form, onChange])

  const handleSubmit = form.handleSubmit(onSubmit)

  // Generate guest count options (1 to MAX_GUESTS)
  const guestCountOptions = Array.from(
    { length: MAX_GUESTS - MIN_GUESTS + 1 },
    (_, i) => i + MIN_GUESTS
  )

  return (
    <Form {...form}>
      <form onSubmit={handleSubmit} className={cn('space-y-6', className)}>
        {/* Guest Count Field */}
        <FormField
          control={form.control}
          name="guestCount"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Number of Guests</FormLabel>
              <Select
                onValueChange={(value) => field.onChange(parseInt(value, 10))}
                defaultValue={String(field.value)}
                disabled={isSubmitting}
              >
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Select number of guests" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {guestCountOptions.map((count) => (
                    <SelectItem key={count} value={String(count)}>
                      {count} {count === 1 ? 'guest' : 'guests'}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormDescription>
                Maximum {MAX_GUESTS} guests allowed
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Special Requests Field */}
        <FormField
          control={form.control}
          name="specialRequests"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Special Requests (Optional)</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Early check-in, dietary requirements, accessibility needs..."
                  className="resize-none"
                  rows={3}
                  disabled={isSubmitting}
                  {...field}
                />
              </FormControl>
              <FormDescription>
                Let us know about any special requirements
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Children (navigation buttons, etc.) */}
        {children}
      </form>
    </Form>
  )
}

export default GuestDetailsForm
