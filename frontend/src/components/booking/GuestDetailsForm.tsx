'use client'

/**
 * GuestDetailsForm Component
 *
 * Collects guest information for booking with validation.
 * Uses shadcn/ui Form primitives with react-hook-form and Zod.
 *
 * When user is authenticated (via useAuthenticatedUser hook), displays
 * email and name as read-only with a sign-out option.
 *
 * Requirements: FR-012, FR-013
 * Uses: shadcn/ui Form, FormField, FormItem, FormLabel, FormControl, FormMessage (T027)
 */

import { useEffect, useState } from 'react'
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
import { Button } from '@/components/ui/button'
import {
  guestDetailsSchema,
  MAX_GUESTS,
  MIN_GUESTS,
  type GuestDetails,
} from '@/lib/schemas/booking-form.schema'
import { useAuthenticatedUser } from '@/hooks/useAuthenticatedUser'

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
  // Auth state hook - checks for existing session on mount
  const { step, user, error, errorType, signOut, initiateAuth, confirmOtp, retry } =
    useAuthenticatedUser()

  // Local state for OTP code input
  const [otpCode, setOtpCode] = useState('')
  const [pendingEmail, setPendingEmail] = useState('')
  const isAuthenticated = step === 'authenticated' && user !== null

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

  // Update form values when user authenticates
  useEffect(() => {
    if (isAuthenticated && user) {
      form.setValue('email', user.email)
      if (user.name) {
        form.setValue('name', user.name)
      }
    }
  }, [isAuthenticated, user, form])

  const handleSubmit = form.handleSubmit((data) => {
    // Ensure authenticated user's email is used even if form wasn't manually updated
    if (isAuthenticated && user) {
      data.email = user.email
      if (user.name) {
        data.name = user.name
      }
    }
    onSubmit(data)
  })

  const handleSignOut = async () => {
    await signOut()
    // Reset the form fields that were locked
    form.setValue('email', '')
    form.setValue('name', '')
  }

  // Generate guest count options (1 to MAX_GUESTS)
  const guestCountOptions = Array.from(
    { length: MAX_GUESTS - MIN_GUESTS + 1 },
    (_, i) => i + MIN_GUESTS
  )

  return (
    <Form {...form}>
      <form onSubmit={handleSubmit} className={cn('space-y-6', className)}>
        {/* Authenticated User Banner */}
        {isAuthenticated && (
          <div
            className="rounded-lg border bg-muted/50 p-4"
            aria-label="authenticated"
          >
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <p className="text-sm font-medium text-muted-foreground">
                  Signed in as
                </p>
                <p className="font-medium">{user.email}</p>
                {user.name && (
                  <p className="text-sm text-muted-foreground">{user.name}</p>
                )}
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleSignOut}
              >
                Sign out
              </Button>
            </div>
          </div>
        )}

        {/* Name Field - Read-only when authenticated with name */}
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
                  disabled={isSubmitting || (isAuthenticated && !!user.name)}
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Email Field - Read-only when authenticated */}
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
                  disabled={isSubmitting || isAuthenticated}
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

        {/* Verify Email Button for Anonymous Users (hide when awaiting OTP or verifying) */}
        {!isAuthenticated && step !== 'awaiting_otp' && step !== 'verifying' && (
          <Button
            type="button"
            variant="outline"
            className="w-full"
            disabled={step === 'sending_otp'}
            onClick={() => {
              const email = form.getValues('email')
              if (email) {
                setPendingEmail(email)
                initiateAuth(email)
              }
            }}
          >
            {step === 'sending_otp' ? 'Sending...' : 'Verify email'}
          </Button>
        )}

        {/* Pre-OTP Error Display - shown in anonymous state (T034) */}
        {step === 'anonymous' && error && (
          <div
            className={`rounded-md p-3 text-sm ${
              errorType === 'network'
                ? 'bg-amber-100 text-amber-800 warning'
                : 'bg-destructive/10 text-destructive'
            }`}
          >
            {error}

            {/* Network errors: Retry button */}
            {errorType === 'network' && (
              <Button
                type="button"
                variant="link"
                className="ml-2 h-auto p-0 text-amber-800 underline"
                onClick={() => retry()}
              >
                Retry
              </Button>
            )}
          </div>
        )}

        {/* OTP Entry Section */}
        {(step === 'awaiting_otp' || step === 'verifying') && (
          <div className="space-y-4 rounded-lg border bg-muted/30 p-4">
            <div className="space-y-1">
              <p className="text-sm font-medium">Enter verification code</p>
              <p className="text-sm text-muted-foreground">
                We sent a code to {pendingEmail || form.getValues('email')}
              </p>
            </div>

            {/* Error Display - type-aware styling (T034) */}
            {error && (
              <div
                className={`rounded-md p-3 text-sm ${
                  errorType === 'network'
                    ? 'bg-amber-100 text-amber-800 warning'
                    : 'bg-destructive/10 text-destructive'
                }`}
              >
                {error}

                {/* Network errors: Retry button */}
                {errorType === 'network' && (
                  <Button
                    type="button"
                    variant="link"
                    className="ml-2 h-auto p-0 text-amber-800 underline"
                    onClick={() => retry()}
                  >
                    Retry
                  </Button>
                )}

                {/* Auth errors: Sign in again for session expired */}
                {errorType === 'auth' && error.toLowerCase().includes('session expired') && (
                  <Button
                    type="button"
                    variant="link"
                    className="ml-2 h-auto p-0 text-destructive underline"
                    onClick={() => {
                      const email = pendingEmail || form.getValues('email')
                      if (email) {
                        initiateAuth(email)
                      }
                    }}
                  >
                    Sign in again
                  </Button>
                )}

                {/* Code expired: Resend code */}
                {error.toLowerCase().includes('expired') && !error.toLowerCase().includes('session') && (
                  <Button
                    type="button"
                    variant="link"
                    className="ml-2 h-auto p-0 text-destructive underline"
                    onClick={() => {
                      const email = pendingEmail || form.getValues('email')
                      if (email) {
                        initiateAuth(email)
                      }
                    }}
                  >
                    Resend code
                  </Button>
                )}
              </div>
            )}

            {/* OTP Input */}
            <div className="space-y-2">
              <label htmlFor="otp-code" className="text-sm font-medium">
                Verification code
              </label>
              <Input
                id="otp-code"
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                placeholder="Enter 6-digit code"
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value)}
                disabled={step === 'verifying'}
                autoComplete="one-time-code"
              />
            </div>

            {/* Confirm Button */}
            <Button
              type="button"
              className="w-full"
              disabled={step === 'verifying' || !otpCode}
              onClick={() => {
                if (otpCode) {
                  confirmOtp(otpCode)
                }
              }}
            >
              {step === 'verifying' ? 'Verifying...' : 'Confirm code'}
            </Button>
          </div>
        )}

        {/* Children (submit button, etc.) */}
        {children}
      </form>
    </Form>
  )
}

export default GuestDetailsForm
