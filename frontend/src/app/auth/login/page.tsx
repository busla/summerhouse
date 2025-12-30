'use client'

/**
 * Login Page for Passwordless EMAIL_OTP Authentication
 *
 * Custom form for EMAIL_OTP flow (no Amplify Authenticator - it shows password field).
 *
 * Flow:
 * 1. User enters email
 * 2. Cognito sends OTP to email (USER_AUTH + EMAIL_OTP)
 * 3. User enters OTP code
 * 4. On success, redirect back to chat
 */

import { Suspense, useState, useEffect, FormEvent } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { signIn, confirmSignIn, getCurrentUser, signOut } from 'aws-amplify/auth'
import { AmplifyProvider } from '@/components/providers/AmplifyProvider'

type AuthStep = 'email' | 'otp' | 'success' | 'error'

function LoginLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="animate-pulse text-gray-500">Loading...</div>
    </div>
  )
}

function LoginContent() {
  const searchParams = useSearchParams()
  const router = useRouter()

  const [step, setStep] = useState<AuthStep>('email')
  const [email, setEmail] = useState('')
  const [otp, setOtp] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [redirectUrl, setRedirectUrl] = useState<string | null>(null)

  // Get redirect URL from query params
  useEffect(() => {
    const url = searchParams.get('redirect') || searchParams.get('auth_url')
    if (url) {
      setRedirectUrl(decodeURIComponent(url))
    }
  }, [searchParams])

  // Check if already authenticated
  useEffect(() => {
    async function checkAuth() {
      try {
        await getCurrentUser()
        // Already logged in - redirect to destination
        const destination = redirectUrl || '/'
        router.push(destination)
      } catch {
        // Not logged in, show form
      }
    }
    checkAuth()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [redirectUrl])

  const handleSuccess = () => {
    setStep('success')
    // Amplify stores tokens internally - just redirect
    const destination = redirectUrl || '/'
    setTimeout(() => {
      router.push(destination)
    }, 500)
  }

  const handleEmailSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!email.trim()) return

    setIsLoading(true)
    setError(null)

    try {
      const result = await signIn({
        username: email.trim().toLowerCase(),
        options: {
          authFlowType: 'USER_AUTH',
          preferredChallenge: 'EMAIL_OTP',
        },
      })

      console.log('[Login] signIn result:', result.nextStep.signInStep)

      if (result.nextStep.signInStep === 'CONFIRM_SIGN_IN_WITH_EMAIL_CODE') {
        setStep('otp')
      } else if (result.nextStep.signInStep === 'DONE') {
        handleSuccess()
      } else {
        setError(`Unexpected auth step: ${result.nextStep.signInStep}`)
      }
    } catch (err) {
      console.error('[Login] signIn error:', err)
      const message = err instanceof Error ? err.message : 'Failed to send verification code'

      // Handle "already signed in" error
      if (message.includes('already a signed in user')) {
        try {
          await signOut()
          // Retry after sign out
          handleEmailSubmit(e)
          return
        } catch {
          // Ignore signOut error
        }
      }

      setError(message)
    } finally {
      setIsLoading(false)
    }
  }

  const handleOtpSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!otp.trim()) return

    setIsLoading(true)
    setError(null)

    try {
      const result = await confirmSignIn({
        challengeResponse: otp.trim(),
      })

      console.log('[Login] confirmSignIn result:', result.nextStep.signInStep)

      if (result.nextStep.signInStep === 'DONE') {
        handleSuccess()
      } else {
        setError(`Unexpected confirmation step: ${result.nextStep.signInStep}`)
      }
    } catch (err) {
      console.error('[Login] confirmSignIn error:', err)
      const message = err instanceof Error ? err.message : 'Invalid verification code'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }

  const handleBackToEmail = () => {
    setStep('email')
    setOtp('')
    setError(null)
  }

  return (
    <AmplifyProvider>
      <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 px-4">
        <div className="max-w-md w-full space-y-8">
          {/* Header */}
          <div className="text-center">
            <h1 className="text-3xl font-bold text-gray-900">
              {step === 'email' && 'Sign In'}
              {step === 'otp' && 'Enter Verification Code'}
              {step === 'success' && 'Success!'}
              {step === 'error' && 'Error'}
            </h1>
            <p className="mt-2 text-gray-600">
              {step === 'email' && 'Enter your email to receive a one-time code'}
              {step === 'otp' && `We sent a code to ${email}`}
              {step === 'success' && 'Redirecting you back...'}
            </p>
          </div>

          {/* Error message */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
              {error}
            </div>
          )}

          {/* Email form */}
          {step === 'email' && (
            <form onSubmit={handleEmailSubmit} className="space-y-6">
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                  Email Address
                </label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  autoFocus
                  autoComplete="email"
                  className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500"
                />
              </div>
              <button
                type="submit"
                disabled={isLoading || !email.trim()}
                className="w-full py-3 px-4 bg-sky-600 hover:bg-sky-700 text-white font-medium rounded-lg shadow-sm disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isLoading ? 'Sending...' : 'Send Verification Code'}
              </button>
            </form>
          )}

          {/* OTP form */}
          {step === 'otp' && (
            <form onSubmit={handleOtpSubmit} className="space-y-6">
              <div>
                <label htmlFor="otp" className="block text-sm font-medium text-gray-700">
                  Verification Code
                </label>
                <input
                  id="otp"
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                  placeholder="12345678"
                  required
                  autoFocus
                  autoComplete="one-time-code"
                  maxLength={8}
                  className="mt-1 block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500 text-center text-2xl tracking-widest"
                />
              </div>
              <button
                type="submit"
                disabled={isLoading || otp.length < 8}
                className="w-full py-3 px-4 bg-sky-600 hover:bg-sky-700 text-white font-medium rounded-lg shadow-sm disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isLoading ? 'Verifying...' : 'Verify Code'}
              </button>
              <button
                type="button"
                onClick={handleBackToEmail}
                className="w-full py-2 text-sm text-gray-600 hover:text-gray-900"
              >
                Use a different email
              </button>
            </form>
          )}

          {/* Success state */}
          {step === 'success' && (
            <div className="text-center py-8">
              <div className="text-green-600 text-5xl mb-4">✓</div>
              <p className="text-gray-600">Redirecting you back to the chat...</p>
            </div>
          )}

          {/* Footer */}
          {(step === 'email' || step === 'otp') && (
            <p className="text-center text-sm text-gray-500">
              No password needed. We&apos;ll send a code to your email.
            </p>
          )}
        </div>
      </div>
    </AmplifyProvider>
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginLoading />}>
      <LoginContent />
    </Suspense>
  )
}
