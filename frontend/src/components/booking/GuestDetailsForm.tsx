'use client'

/**
 * GuestDetailsForm Component
 *
 * Collects guest information for booking with validation.
 * Uses shadcn/ui Form primitives with react-hook-form and Zod.
 *
 * Requirements: FR-012, FR-013
 * Uses: shadcn/ui Form, FormField, FormItem, FormLabel, FormControl, FormMessage (T027)
 */

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
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  guestDetailsSchema,
  MAX_GUESTS,
  MIN_GUESTS,
  type GuestDetails,
} from '@/lib/schemas/booking-form.schema'

export interface GuestDetailsFormProps {
  /** Initial values for the form */
  defaultValues?: Partial<GuestDetails>
  /** Callback when form is submitted with valid data */
  onSubmit: (data: GuestDetails) => void
  /** Whether the form is submitting */
  isSubmitting?: boolean
  /** Custom class name */
  className?: string
  /** Children to render (e.g., submit button) */
  children?: React.ReactNode
}

export function GuestDetailsForm({
  defaultValues,
  onSubmit,
  isSubmitting = false,
  className,
  children,
}: GuestDetailsFormProps) {
  const form = useForm<GuestDetails>({
    resolver: zodResolver(guestDetailsSchema),
    defaultValues: {
      name: '',
      email: '',
      phone: '',
      guestCount: 2,
      specialRequests: '',
      ...defaultValues,
    },
    mode: 'onBlur',
  })

  const handleSubmit = form.handleSubmit((data) => {
    onSubmit(data)
  })

  // Generate guest count options (1 to MAX_GUESTS)
  const guestCountOptions = Array.from(
    { length: MAX_GUESTS - MIN_GUESTS + 1 },
    (_, i) => i + MIN_GUESTS
  )

  return (
    <Form {...form}>
      <form onSubmit={handleSubmit} className={cn('space-y-6', className)}>
        {/* Name Field */}
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Full Name</FormLabel>
              <FormControl>
                <Input
                  placeholder="John Smith"
                  autoComplete="name"
                  disabled={isSubmitting}
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Email Field */}
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email Address</FormLabel>
              <FormControl>
                <Input
                  type="email"
                  placeholder="john@example.com"
                  autoComplete="email"
                  disabled={isSubmitting}
                  {...field}
                />
              </FormControl>
              <FormDescription>
                We&apos;ll send your booking confirmation here
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Phone Field */}
        <FormField
          control={form.control}
          name="phone"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Phone Number</FormLabel>
              <FormControl>
                <Input
                  type="tel"
                  placeholder="+34 612 345 678"
                  autoComplete="tel"
                  disabled={isSubmitting}
                  {...field}
                />
              </FormControl>
              <FormDescription>
                For check-in coordination
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

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

        {/* Children (submit button, etc.) */}
        {children}
      </form>
    </Form>
  )
}

export default GuestDetailsForm
