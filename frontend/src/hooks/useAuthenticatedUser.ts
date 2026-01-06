'use client'

/**
 * useAuthenticatedUser - Auth-aware hook for forms.
 *
 * Handles both authenticated and anonymous states using Amplify EMAIL_OTP flow.
 * Created as part of T005b (Green Phase).
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  signIn,
  signUp,
  confirmSignIn,
  confirmSignUp,
  autoSignIn,
  getCurrentUser,
  fetchAuthSession,
  signOut as amplifySignOut,
} from 'aws-amplify/auth'
import { authEvents } from '@/lib/api-client/auth-events'

// === Structured Auth Logger (T035a) ===

/**
 * Mask email for privacy-conscious logging.
 * Shows first 3 chars + *** + @domain
 */
function maskEmail(email: string): string {
  if (!email || !email.includes('@')) return '***'
  const atIndex = email.indexOf('@')
  return email.slice(0, Math.min(3, atIndex)) + '***' + email.slice(atIndex)
}

/**
 * Structured logging for auth events (T035a).
 * Uses console.info for important events, console.debug for routine ones.
 */
const authLogger = {
  sessionRestored: (sub: string, email: string) => {
    console.info('[auth] session_restored', {
      sub: sub.slice(0, 8) + '...',
      email: maskEmail(email),
    })
  },
  noSession: () => {
    console.debug('[auth] no_existing_session')
  },
  otpInitiated: (email: string) => {
    console.info('[auth] otp_initiated', { email: maskEmail(email) })
  },
  otpSent: (email: string, isNewUser: boolean) => {
    console.info('[auth] otp_sent', {
      email: maskEmail(email),
      isNewUser,
    })
  },
  otpVerifying: () => {
    console.debug('[auth] otp_verifying')
  },
  authSuccess: (sub: string, email: string) => {
    console.info('[auth] auth_success', {
      sub: sub.slice(0, 8) + '...',
      email: maskEmail(email),
    })
  },
  authError: (errorType: ErrorType, errorName: string, context: string) => {
    console.warn('[auth] auth_error', {
      errorType,
      errorName,
      context,
    })
  },
  signedOut: () => {
    console.info('[auth] signed_out')
  },
  sessionExpired: (url: string) => {
    console.warn('[auth] session_expired_401', {
      url,
      hint: 'API returned 401, resetting to anonymous for re-auth',
    })
  },
  retry: (previousErrorType: ErrorType) => {
    console.debug('[auth] retry_triggered', { previousErrorType })
  },
}

/**
 * Authentication flow step.
 */
export type AuthStep =
  | 'anonymous' // Not authenticated, show input fields
  | 'sending_otp' // OTP being sent
  | 'awaiting_otp' // Waiting for user to enter OTP
  | 'verifying' // Verifying OTP
  | 'authenticated' // Authenticated, show read-only info

/**
 * Error type categorization for appropriate UI handling (T034).
 *
 * - network: Connection issues - show retry with "check internet" message
 * - auth: Session/token issues - show "sign in again" message
 * - validation: Invalid input (bad code format) - show inline field error
 * - rate_limit: Too many attempts - show wait message
 */
export type ErrorType = 'network' | 'auth' | 'validation' | 'rate_limit' | null

/**
 * Authenticated user information from Cognito session.
 */
export interface AuthenticatedUser {
  email: string
  name?: string
  sub: string
}

/**
 * Return type for useAuthenticatedUser hook.
 */
export interface UseAuthenticatedUserReturn {
  step: AuthStep
  user: AuthenticatedUser | null
  error: string | null
  errorType: ErrorType

  // Actions
  initiateAuth: (email: string) => Promise<void>
  confirmOtp: (code: string) => Promise<void>
  signOut: () => Promise<void>
  retry: () => void
}

/**
 * Hook for managing authentication state in forms.
 *
 * On mount, checks for existing Amplify session. If authenticated,
 * extracts user claims. Otherwise, starts in anonymous state.
 *
 * @returns Authentication state and actions
 */
/**
 * Categorize error by type for appropriate UI handling (T034).
 */
function categorizeError(err: unknown): { type: ErrorType; message: string } {
  if (!(err instanceof Error)) {
    return { type: 'auth', message: 'An unexpected error occurred' }
  }

  const name = err.name
  const message = err.message.toLowerCase()

  // Network errors - connection issues
  if (
    name === 'NetworkError' ||
    name === 'TypeError' || // fetch failures
    message.includes('network') ||
    message.includes('fetch') ||
    message.includes('connection')
  ) {
    return {
      type: 'network',
      message: 'Unable to connect. Please check your internet connection.',
    }
  }

  // Rate limit errors
  if (name === 'LimitExceededException') {
    return {
      type: 'rate_limit',
      message: 'Too many attempts. Please wait and try again.',
    }
  }

  // Validation errors - bad input format
  if (name === 'InvalidParameterException') {
    return {
      type: 'validation',
      message: err.message,
    }
  }

  // Auth errors - session/token/code issues
  if (
    name === 'TokenExpiredException' ||
    name === 'NotAuthorizedException' ||
    message.includes('session expired') ||
    message.includes('token')
  ) {
    return {
      type: 'auth',
      message: 'Session expired. Please sign in again.',
    }
  }

  // Cognito-specific auth errors
  if (name === 'CodeMismatchException') {
    return {
      type: 'auth',
      message: 'Invalid code. Please try again.',
    }
  }

  if (name === 'ExpiredCodeException') {
    return {
      type: 'auth',
      message: 'Code expired. Please request a new one.',
    }
  }

  // Default to auth error with original message
  return { type: 'auth', message: err.message }
}

export function useAuthenticatedUser(): UseAuthenticatedUserReturn {
  const [step, setStep] = useState<AuthStep>('anonymous')
  const [user, setUser] = useState<AuthenticatedUser | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [errorType, setErrorType] = useState<ErrorType>(null)

  // Track whether current flow is for a new user (signup) vs existing user (signin)
  // This determines whether confirmOtp should call confirmSignUp or confirmSignIn
  const isNewUserFlow = useRef(false)
  // Store email for new user signup (needed for confirmSignUp API)
  const pendingEmail = useRef<string | null>(null)

  // Check existing session on mount
  useEffect(() => {
    async function checkSession() {
      try {
        const currentUser = await getCurrentUser()
        const session = await fetchAuthSession()
        const claims = session.tokens?.idToken?.payload

        const email = claims?.email as string
        setUser({
          email,
          name: claims?.name as string | undefined,
          sub: currentUser.userId,
        })
        setStep('authenticated')
        authLogger.sessionRestored(currentUser.userId, email)
      } catch {
        // Not authenticated - stay in anonymous state
        setStep('anonymous')
        authLogger.noSession()
      }
    }
    checkSession()
  }, [])

  // Subscribe to 401 auth-required events from API client (T037)
  // When API returns 401, reset auth state to prompt re-authentication
  useEffect(() => {
    const unsubscribe = authEvents.on('auth-required', async (event) => {
      authLogger.sessionExpired(event.url)

      // Clear Amplify session
      try {
        await amplifySignOut()
      } catch {
        // Ignore signOut errors - session may already be invalid
      }

      // Reset to anonymous state with helpful error message
      setUser(null)
      setStep('anonymous')
      setError('Your session has expired. Please sign in again.')
      setErrorType('auth')
    })

    return unsubscribe
  }, [])

  /**
   * Initiate authentication with EMAIL_OTP flow.
   * Tries signIn first (existing user), falls back to signUp (new user).
   *
   * Handles multiple signIn response states:
   * - CONFIRM_SIGN_IN_WITH_EMAIL_CODE: Normal OTP flow, await code
   * - DONE: Already signed in (e.g., tokens still valid), transition to authenticated
   * - Others: Log and show error
   */
  const initiateAuth = useCallback(async (email: string) => {
    setError(null)
    setErrorType(null)
    setStep('sending_otp')
    authLogger.otpInitiated(email)

    // Reset flow tracking - assume existing user until proven otherwise
    isNewUserFlow.current = false
    pendingEmail.current = email

    try {
      // NOTE: Do NOT call signOut() before signIn() - this breaks the Cognito USER_AUTH flow
      // by clearing session context, causing Cognito to return CONTINUE_SIGN_IN_WITH_FIRST_FACTOR_SELECTION
      // instead of going directly to CONFIRM_SIGN_IN_WITH_EMAIL_CODE

      // Try sign in (existing user)
      const { nextStep, isSignedIn } = await signIn({
        username: email,
        options: {
          authFlowType: 'USER_AUTH',
          preferredChallenge: 'EMAIL_OTP',
        },
      })

      console.debug('[auth] signIn response', { signInStep: nextStep.signInStep, isSignedIn })

      if (nextStep.signInStep === 'CONFIRM_SIGN_IN_WITH_EMAIL_CODE') {
        setStep('awaiting_otp')
        authLogger.otpSent(email, false)
      } else if (nextStep.signInStep === 'CONTINUE_SIGN_IN_WITH_FIRST_FACTOR_SELECTION') {
        // Cognito is asking us to select an auth factor
        // This can happen when there's incomplete auth state or preferredChallenge wasn't applied
        const availableChallenges = (nextStep as { availableChallenges?: string[] }).availableChallenges
        console.info('[auth] available challenges:', availableChallenges)

        // Always attempt EMAIL_OTP selection - let Cognito reject if invalid
        // Don't preemptively block based on availableChallenges which may be stale
        console.debug('[auth] selecting EMAIL_OTP factor')
        const selectResult = await confirmSignIn({ challengeResponse: 'EMAIL_OTP' })

        if (selectResult.nextStep.signInStep === 'CONFIRM_SIGN_IN_WITH_EMAIL_CODE') {
          setStep('awaiting_otp')
          authLogger.otpSent(email, false)
        } else if (selectResult.isSignedIn) {
          // Unexpected but handle gracefully
          const currentUser = await getCurrentUser()
          const session = await fetchAuthSession()
          const claims = session.tokens?.idToken?.payload
          const userEmail = claims?.email as string
          setUser({
            email: userEmail,
            name: claims?.name as string | undefined,
            sub: currentUser.userId,
          })
          setStep('authenticated')
          authLogger.authSuccess(currentUser.userId, userEmail)
        } else {
          console.warn('[auth] unexpected step after factor selection:', selectResult.nextStep.signInStep)
          setError('Authentication configuration error. Please try again.')
          setErrorType('auth')
          setStep('anonymous')
        }
      } else if (isSignedIn || nextStep.signInStep === 'DONE') {
        // User was already authenticated - fetch session and complete
        const currentUser = await getCurrentUser()
        const session = await fetchAuthSession()
        const claims = session.tokens?.idToken?.payload

        const userEmail = claims?.email as string
        setUser({
          email: userEmail,
          name: claims?.name as string | undefined,
          sub: currentUser.userId,
        })
        setStep('authenticated')
        authLogger.authSuccess(currentUser.userId, userEmail)
      } else {
        // Unexpected step - log and show error
        console.warn('[auth] unexpected signIn step:', nextStep.signInStep)
        setError(`Unexpected authentication state: ${nextStep.signInStep}. Please try again.`)
        setErrorType('auth')
        setStep('anonymous')
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'UserAlreadyAuthenticatedException') {
        // User already has an active session - fetch their info and mark authenticated
        console.info('[auth] user already authenticated, fetching session')
        try {
          const currentUser = await getCurrentUser()
          const session = await fetchAuthSession()
          const claims = session.tokens?.idToken?.payload
          const userEmail = claims?.email as string
          setUser({
            email: userEmail,
            name: claims?.name as string | undefined,
            sub: currentUser.userId,
          })
          setStep('authenticated')
          authLogger.authSuccess(currentUser.userId, userEmail)
          return
        } catch {
          // If fetching session fails, continue to show error
          console.warn('[auth] failed to fetch existing session')
        }
      }

      if (err instanceof Error && err.name === 'UserNotFoundException') {
        // New user - sign up flow (requires confirmSignUp, NOT confirmSignIn)
        isNewUserFlow.current = true

        try {
          const signUpResult = await signUp({
            username: email,
            password: crypto.randomUUID(), // Required but unused for EMAIL_OTP
            options: {
              userAttributes: { email },
              autoSignIn: { authFlowType: 'USER_AUTH' },
            },
          })

          console.debug('[auth] signUp response', {
            signUpStep: signUpResult.nextStep.signUpStep,
            isSignUpComplete: signUpResult.isSignUpComplete,
            // codeDeliveryDetails only exists for CONFIRM_SIGN_UP step
            codeDeliveryDetails: 'codeDeliveryDetails' in signUpResult.nextStep
              ? signUpResult.nextStep.codeDeliveryDetails
              : undefined,
          })

          if (signUpResult.nextStep.signUpStep === 'CONFIRM_SIGN_UP') {
            // OTP was sent to email - await user input
            setStep('awaiting_otp')
            authLogger.otpSent(email, true)
          } else if (signUpResult.isSignUpComplete) {
            // Unexpected: user was signed up without confirmation needed
            // Try auto sign in
            console.info('[auth] signUp completed immediately, attempting autoSignIn')
            const autoSignInResult = await autoSignIn()
            if (autoSignInResult.isSignedIn) {
              const currentUser = await getCurrentUser()
              const session = await fetchAuthSession()
              const claims = session.tokens?.idToken?.payload
              const userEmail = claims?.email as string
              setUser({
                email: userEmail,
                name: claims?.name as string | undefined,
                sub: currentUser.userId,
              })
              setStep('authenticated')
              authLogger.authSuccess(currentUser.userId, userEmail)
            }
          } else {
            console.warn('[auth] unexpected signUp step:', signUpResult.nextStep.signUpStep)
            setError('Unexpected signup state. Please try again.')
            setErrorType('auth')
            setStep('anonymous')
          }
        } catch (signUpErr) {
          const { type, message } = categorizeError(signUpErr)
          authLogger.authError(type, signUpErr instanceof Error ? signUpErr.name : 'Unknown', 'signUp')
          setError(message)
          setErrorType(type)
          setStep('anonymous')
        }
      } else {
        const { type, message } = categorizeError(err)
        authLogger.authError(type, err instanceof Error ? err.name : 'Unknown', 'signIn')
        setError(message)
        setErrorType(type)
        setStep('anonymous')
      }
    }
  }, [])

  /**
   * Confirm OTP code to complete authentication.
   *
   * For EXISTING users (signin flow): calls confirmSignIn()
   * For NEW users (signup flow): calls confirmSignUp() → autoSignIn()
   */
  const confirmOtp = useCallback(async (code: string) => {
    setError(null)
    setErrorType(null)
    setStep('verifying')
    authLogger.otpVerifying()

    try {
      if (isNewUserFlow.current) {
        // NEW USER FLOW: confirmSignUp → autoSignIn
        console.debug('[auth] confirming signup for new user')

        const email = pendingEmail.current
        if (!email) {
          throw new Error('Email not found for signup confirmation')
        }

        const confirmResult = await confirmSignUp({
          username: email,
          confirmationCode: code,
        })

        console.debug('[auth] confirmSignUp response', {
          signUpStep: confirmResult.nextStep.signUpStep,
          isSignUpComplete: confirmResult.isSignUpComplete,
        })

        if (confirmResult.nextStep.signUpStep === 'COMPLETE_AUTO_SIGN_IN') {
          // Sign up confirmed, now auto sign in
          console.info('[auth] signup confirmed, calling autoSignIn')
          const autoSignInResult = await autoSignIn()

          if (autoSignInResult.isSignedIn) {
            const currentUser = await getCurrentUser()
            const session = await fetchAuthSession()
            const claims = session.tokens?.idToken?.payload

            const userEmail = claims?.email as string
            setUser({
              email: userEmail,
              name: claims?.name as string | undefined,
              sub: currentUser.userId,
            })
            setStep('authenticated')
            authLogger.authSuccess(currentUser.userId, userEmail)
          } else {
            // Auto sign in not complete, may need additional steps
            console.warn('[auth] autoSignIn step:', autoSignInResult.nextStep)
            setError('Please sign in to complete registration.')
            setErrorType('auth')
            setStep('anonymous')
          }
        } else if (confirmResult.isSignUpComplete) {
          // Signup complete without auto sign in - try manual auto sign in
          console.info('[auth] signup complete, attempting autoSignIn')
          const autoSignInResult = await autoSignIn()

          if (autoSignInResult.isSignedIn) {
            const currentUser = await getCurrentUser()
            const session = await fetchAuthSession()
            const claims = session.tokens?.idToken?.payload

            const userEmail = claims?.email as string
            setUser({
              email: userEmail,
              name: claims?.name as string | undefined,
              sub: currentUser.userId,
            })
            setStep('authenticated')
            authLogger.authSuccess(currentUser.userId, userEmail)
          } else {
            console.warn('[auth] autoSignIn failed, step:', autoSignInResult.nextStep)
            setError('Registration complete. Please sign in.')
            setErrorType('auth')
            setStep('anonymous')
          }
        } else {
          console.warn('[auth] unexpected confirmSignUp step:', confirmResult.nextStep.signUpStep)
          setError('Unexpected signup state. Please try again.')
          setErrorType('auth')
          setStep('anonymous')
        }
      } else {
        // EXISTING USER FLOW: confirmSignIn
        console.debug('[auth] confirming signin for existing user')

        const result = await confirmSignIn({ challengeResponse: code })

        if (result.isSignedIn) {
          const currentUser = await getCurrentUser()
          const session = await fetchAuthSession()
          const claims = session.tokens?.idToken?.payload

          const email = claims?.email as string
          setUser({
            email,
            name: claims?.name as string | undefined,
            sub: currentUser.userId,
          })
          setStep('authenticated')
          authLogger.authSuccess(currentUser.userId, email)
        } else {
          console.warn('[auth] confirmSignIn not signed in, step:', result.nextStep)
          setError('Verification incomplete. Please try again.')
          setErrorType('auth')
          setStep('awaiting_otp')
        }
      }
    } catch (err) {
      const { type, message } = categorizeError(err)
      authLogger.authError(type, err instanceof Error ? err.name : 'Unknown', 'confirmOtp')
      setError(message)
      setErrorType(type)
      setStep('awaiting_otp')
    }
  }, [])

  /**
   * Sign out and return to anonymous state.
   */
  const signOut = useCallback(async () => {
    await amplifySignOut()
    setUser(null)
    setStep('anonymous')
    authLogger.signedOut()
  }, [])

  /**
   * Retry after an error or reset to form state (T034).
   * Clears error state and resets to anonymous to allow fresh attempt.
   * Also used for "Change email" flow from OTP view.
   */
  const retry = useCallback(() => {
    const currentErrorType = errorType
    authLogger.retry(currentErrorType)
    setError(null)
    setErrorType(null)

    // Reset flow tracking
    isNewUserFlow.current = false
    pendingEmail.current = null

    // Reset to anonymous for fresh attempt (handles both error recovery and "change email")
    setStep('anonymous')
  }, [errorType])

  return {
    step,
    user,
    error,
    errorType,
    initiateAuth,
    confirmOtp,
    signOut,
    retry,
  }
}
