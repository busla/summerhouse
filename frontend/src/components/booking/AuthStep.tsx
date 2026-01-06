'use client'

/**
 * AuthStep Component (T012-T025)
 *
 * Dedicated identity verification step in the booking flow.
 * Collects name, email, phone, then verifies email via Cognito EMAIL_OTP.
 *
 * Flow:
 * 1. User fills name/email/phone → clicks "Verify Email"
 * 2. OTP sent → 6-digit input appears
 * 3. User enters code → verification completes
 * 4. onComplete called with customerId
 *
 * Requirements: FR-002, FR-004, FR-005, FR-006, FR-008
 */

import { useEffect, useCallback, useState, useRef } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Shield, ArrowLeft } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSlot,
} from '@/components/ui/input-otp'
import {
  authStepSchema,
  type AuthStepFormData,
} from '@/lib/schemas/auth-step.schema'
import { useAuthenticatedUser } from '@/hooks/useAuthenticatedUser'
import { useCustomerProfile } from '@/hooks/useCustomerProfile'

export interface AuthStepProps {
  /** Called when authentication completes successfully with customerId */
  onComplete: (customerId: string) => void
  /** Called when user clicks Back to return to dates */
  onBack: () => void
  /** Called when form values change (for persistence) */
  onChange?: (values: { name?: string; email?: string; phone?: string }) => void
  /** Initial values for the form (from persistence) */
  defaultValues?: {
    name?: string
    email?: string
    phone?: string
  }
  /** Custom class name */
  className?: string
}

export function AuthStep({
  onComplete,
  onBack,
  onChange,
  defaultValues,
  className,
}: AuthStepProps) {
  // Auth state machine from hook
  const {
    step: authStep,
    user,
    error,
    errorType,
    initiateAuth,
    confirmOtp,
    retry,
  } = useAuthenticatedUser()

  // Customer profile sync hook (T026-T029)
  const {
    syncCustomerProfile,
    isLoading: isProfileLoading,
    error: profileError,
  } = useCustomerProfile()

  // Local state for OTP code
  const [otpCode, setOtpCode] = useState('')

  // Track the email we're verifying (persists through OTP flow)
  const [pendingEmail, setPendingEmail] = useState('')

  // Track if we've already synced profile (prevent double-sync)
  const profileSyncedRef = useRef(false)

  // Form with Zod validation
  const form = useForm<AuthStepFormData>({
    resolver: zodResolver(authStepSchema),
    defaultValues: {
      name: defaultValues?.name || '',
      email: defaultValues?.email || '',
      phone: defaultValues?.phone || '',
    },
    mode: 'onBlur',
  })

  // When auth completes, sync customer profile with backend (T026-T029)
  // Then call onComplete with the customer_id from our backend (not cognito sub)
  useEffect(() => {
    if (authStep === 'authenticated' && user && !profileSyncedRef.current) {
      profileSyncedRef.current = true

      const syncProfile = async () => {
        // Get form values for profile sync
        const name = form.getValues('name')
        const phone = form.getValues('phone')

        // Sync with backend - creates new or fetches existing customer
        const result = await syncCustomerProfile({ name, phone })

        if (result.customer) {
          // Success - call onComplete with backend customer_id
          onComplete(result.customer.customer_id)
        } else if (result.error) {
          // Profile sync failed - fall back to cognito sub
          // This ensures the flow doesn't break if backend is down
          console.warn('[AuthStep] Profile sync failed, using cognito sub:', result.error)
          onComplete(user.sub)
        }
      }

      syncProfile()
    }
  }, [authStep, user, form, syncCustomerProfile, onComplete])

  // Subscribe to form value changes for persistence
  useEffect(() => {
    if (!onChange) return
    const subscription = form.watch((values) => {
      onChange({
        name: values.name,
        email: values.email,
        phone: values.phone,
      })
    })
    return () => subscription.unsubscribe()
  }, [form, onChange])

  // Handle "Verify Email" click - validate form then initiate auth
  const handleVerifyEmail = useCallback(async () => {
    const isValid = await form.trigger()
    if (!isValid) return

    const email = form.getValues('email')
    setPendingEmail(email)
    await initiateAuth(email)
  }, [form, initiateAuth])

  // Handle OTP code change - auto-submit when 6 digits entered
  const handleOtpChange = useCallback(
    (value: string) => {
      setOtpCode(value)

      // Auto-submit when all 6 digits entered
      if (value.length === 6) {
        confirmOtp(value)
      }
    },
    [confirmOtp]
  )

  // Handle "Change Email" - go back to form view
  const handleChangeEmail = useCallback(() => {
    setOtpCode('')
    setPendingEmail('')
    profileSyncedRef.current = false // Reset profile sync flag for new auth attempt
    retry()
  }, [retry])

  // Handle resend code
  const handleResendCode = useCallback(() => {
    setOtpCode('')
    if (pendingEmail) {
      initiateAuth(pendingEmail)
    }
  }, [pendingEmail, initiateAuth])

  // Determine what to show based on auth step
  // Show OTP input when awaiting, verifying, syncing profile, or resending (sending_otp after first send)
  const showOtpInput = authStep === 'awaiting_otp' || authStep === 'verifying' || isProfileLoading || (authStep === 'sending_otp' && pendingEmail !== '')
  const isLoading = authStep === 'sending_otp' || authStep === 'verifying' || isProfileLoading

  // Combined error from auth or profile sync
  const displayError = error || profileError

  return (
    <Card className={cn(className)}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Shield size={24} className="text-primary" />
          Verify Identity
        </CardTitle>
      </CardHeader>
      <CardContent>
        {!showOtpInput ? (
          // Form view - name/email/phone fields
          <Form {...form}>
            <form className="space-y-6">
              {/* Name Field */}
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Full Name</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="Jane Smith"
                        autoComplete="name"
                        disabled={isLoading}
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
                        placeholder="jane@example.com"
                        autoComplete="email"
                        disabled={isLoading}
                        {...field}
                      />
                    </FormControl>
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
                        disabled={isLoading}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Error Display (pre-OTP errors) */}
              {error && authStep === 'anonymous' && (
                <div
                  className={cn(
                    'rounded-md p-3 text-sm',
                    errorType === 'network'
                      ? 'bg-amber-100 text-amber-800'
                      : 'bg-destructive/10 text-destructive'
                  )}
                  role="alert"
                >
                  {error}
                  {errorType === 'network' && (
                    <Button
                      type="button"
                      variant="link"
                      className="ml-2 h-auto p-0 text-amber-800 underline"
                      onClick={retry}
                    >
                      Retry
                    </Button>
                  )}
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex justify-between gap-4 pt-2">
                <Button
                  type="button"
                  variant="outline"
                  size="lg"
                  onClick={onBack}
                  disabled={isLoading}
                >
                  <ArrowLeft size={18} />
                  Back
                </Button>
                <Button
                  type="button"
                  size="lg"
                  onClick={handleVerifyEmail}
                  disabled={isLoading}
                >
                  {authStep === 'sending_otp' ? 'Sending...' : 'Verify Email'}
                </Button>
              </div>
            </form>
          </Form>
        ) : (
          // OTP view - 6-digit code input
          <div className="space-y-6">
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">
                We sent a verification code to
              </p>
              <p className="font-medium">{pendingEmail}</p>
            </div>

            {/* OTP Input - 6 slots */}
            <div className="space-y-2">
              <label htmlFor="otp-input" className="text-sm font-medium">
                Verification code
              </label>
              <InputOTP
                id="otp-input"
                maxLength={6}
                value={otpCode}
                onChange={handleOtpChange}
                disabled={authStep === 'verifying'}
                aria-label="Verification code"
              >
                <InputOTPGroup>
                  <InputOTPSlot index={0} data-slot="otp-slot" />
                  <InputOTPSlot index={1} data-slot="otp-slot" />
                  <InputOTPSlot index={2} data-slot="otp-slot" />
                  <InputOTPSlot index={3} data-slot="otp-slot" />
                  <InputOTPSlot index={4} data-slot="otp-slot" />
                  <InputOTPSlot index={5} data-slot="otp-slot" />
                </InputOTPGroup>
              </InputOTP>
            </div>

            {/* Error Display (OTP or profile errors) */}
            {displayError && (
              <div
                className={cn(
                  'rounded-md p-3 text-sm',
                  errorType === 'network'
                    ? 'bg-amber-100 text-amber-800'
                    : 'bg-destructive/10 text-destructive'
                )}
                role="alert"
              >
                {displayError}
                {errorType === 'network' && (
                  <Button
                    type="button"
                    variant="link"
                    className="ml-2 h-auto p-0 text-amber-800 underline"
                    onClick={retry}
                  >
                    Retry
                  </Button>
                )}
              </div>
            )}

            {/* Loading state */}
            {(authStep === 'verifying' || isProfileLoading) && (
              <p className="text-sm text-muted-foreground">
                {isProfileLoading ? 'Setting up your profile...' : 'Verifying...'}
              </p>
            )}

            {/* OTP Actions */}
            <div className="flex flex-wrap gap-4">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleChangeEmail}
                disabled={authStep === 'verifying'}
              >
                Change email
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleResendCode}
                disabled={authStep === 'verifying' || authStep === 'sending_otp'}
              >
                Resend code
              </Button>
            </div>

            {/* Back Button */}
            <div className="pt-2">
              <Button
                type="button"
                variant="outline"
                size="lg"
                onClick={onBack}
                disabled={authStep === 'verifying'}
              >
                <ArrowLeft size={18} />
                Back
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default AuthStep
