'use client'

/**
 * OAuth2 Callback Page for AgentCore Session Binding
 *
 * This page handles the callback after AgentCore OAuth2 flow completes.
 * It binds the user's Cognito session to the AgentCore token vault so
 * the agent can access the user's token for @requires_access_token tools.
 *
 * Flow:
 * 1. User authenticates via EMAIL_OTP on /auth/login
 * 2. Login page redirects to AgentCore callback URL
 * 3. AgentCore processes and redirects here with session_id
 * 4. This page calls CompleteResourceTokenAuth to bind the token
 * 5. Redirect back to chat where the agent can now access the token
 *
 * @see specs/005-agentcore-amplify-oauth2/spec.md
 */

import { Suspense, useEffect, useState } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { fetchAuthSession } from 'aws-amplify/auth'
import {
  completeSessionBinding,
  extractSessionId,
  shouldRestartAuthFlow,
  isRetryableError,
  AgentCoreAuthErrorCode,
} from '@/lib/agentcore-auth'
import { AmplifyProvider } from '@/components/providers/AmplifyProvider'

type CallbackStatus =
  | 'loading'
  | 'binding'
  | 'success'
  | 'error'
  | 'no_session'

interface CallbackState {
  status: CallbackStatus
  errorCode?: AgentCoreAuthErrorCode
  errorMessage?: string
}

/**
 * Loading fallback for Suspense boundary.
 */
function CallbackLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="animate-pulse text-gray-500">Loading...</div>
    </div>
  )
}

/**
 * Inner callback component that uses useSearchParams (requires Suspense).
 */
function CallbackContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const [state, setState] = useState<CallbackState>({ status: 'loading' })

  useEffect(() => {
    async function handleCallback() {
      // Extract session_id from URL
      const sessionId = extractSessionId(searchParams)

      if (!sessionId) {
        setState({
          status: 'no_session',
          errorMessage: 'No session identifier found. Please return to the chat and try again.',
        })
        return
      }

      setState({ status: 'binding' })

      try {
        // Get the Cognito access token from Amplify
        const session = await fetchAuthSession()
        const accessToken = session.tokens?.accessToken?.toString()

        if (!accessToken) {
          // User not authenticated - redirect to login
          const loginUrl = `/auth/login?session_id=${encodeURIComponent(sessionId)}`
          router.push(loginUrl)
          return
        }

        // Complete the session binding with AgentCore
        const result = await completeSessionBinding(sessionId, accessToken)

        if (result.success) {
          setState({ status: 'success' })
          // Redirect back to chat after short delay
          setTimeout(() => {
            router.push('/')
          }, 1500)
        } else {
          setState({
            status: 'error',
            errorCode: result.errorCode,
            errorMessage: result.errorMessage,
          })
        }
      } catch (error) {
        console.error('[Callback] Unexpected error:', error)
        setState({
          status: 'error',
          errorCode: AgentCoreAuthErrorCode.UNKNOWN,
          errorMessage: 'An unexpected error occurred. Please try again.',
        })
      }
    }

    handleCallback()
  }, [searchParams, router])

  // Handle retry for throttling errors
  const handleRetry = () => {
    setState({ status: 'loading' })
    // Re-trigger the effect by reloading
    window.location.reload()
  }

  // Handle restart for session expired errors
  const handleRestartFlow = () => {
    router.push('/')
  }

  return (
    <AmplifyProvider>
      <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 px-4">
        <div className="max-w-md w-full space-y-8 text-center">
          {/* Loading State */}
          {(state.status === 'loading' || state.status === 'binding') && (
            <div className="space-y-4">
              <div className="animate-spin h-12 w-12 border-4 border-sky-500 border-t-transparent rounded-full mx-auto" />
              <h2 className="text-xl font-semibold text-gray-900">
                {state.status === 'loading' ? 'Processing...' : 'Completing Sign In...'}
              </h2>
              <p className="text-gray-500">
                Please wait while we complete your authentication.
              </p>
            </div>
          )}

          {/* Success State */}
          {state.status === 'success' && (
            <div className="space-y-4">
              <div className="h-12 w-12 bg-green-100 rounded-full flex items-center justify-center mx-auto">
                <svg
                  className="h-6 w-6 text-green-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-gray-900">
                Sign In Complete
              </h2>
              <p className="text-gray-500">
                Redirecting you back to the chat...
              </p>
            </div>
          )}

          {/* No Session State */}
          {state.status === 'no_session' && (
            <div className="space-y-4">
              <div className="h-12 w-12 bg-yellow-100 rounded-full flex items-center justify-center mx-auto">
                <svg
                  className="h-6 w-6 text-yellow-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-gray-900">
                Missing Session
              </h2>
              <p className="text-gray-500">{state.errorMessage}</p>
              <button
                onClick={handleRestartFlow}
                className="mt-4 px-6 py-2 bg-sky-500 text-white rounded-lg hover:bg-sky-600 transition-colors"
              >
                Return to Chat
              </button>
            </div>
          )}

          {/* Error State */}
          {state.status === 'error' && (
            <div className="space-y-4">
              <div className="h-12 w-12 bg-red-100 rounded-full flex items-center justify-center mx-auto">
                <svg
                  className="h-6 w-6 text-red-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-gray-900">
                Authentication Failed
              </h2>
              <p className="text-gray-500">{state.errorMessage}</p>

              {/* Action buttons based on error type */}
              <div className="mt-6 space-y-3">
                {state.errorCode && isRetryableError(state.errorCode) && (
                  <button
                    onClick={handleRetry}
                    className="w-full px-6 py-2 bg-sky-500 text-white rounded-lg hover:bg-sky-600 transition-colors"
                  >
                    Try Again
                  </button>
                )}
                {state.errorCode && shouldRestartAuthFlow(state.errorCode) && (
                  <button
                    onClick={handleRestartFlow}
                    className="w-full px-6 py-2 bg-sky-500 text-white rounded-lg hover:bg-sky-600 transition-colors"
                  >
                    Return to Chat
                  </button>
                )}
                {!state.errorCode ||
                  (!isRetryableError(state.errorCode) &&
                    !shouldRestartAuthFlow(state.errorCode) && (
                      <button
                        onClick={handleRestartFlow}
                        className="w-full px-6 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
                      >
                        Return to Chat
                      </button>
                    ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </AmplifyProvider>
  )
}

/**
 * Callback page wrapped with Suspense for static export compatibility.
 * useSearchParams() requires a Suspense boundary in Next.js 14 static exports.
 */
export default function CallbackPage() {
  return (
    <Suspense fallback={<CallbackLoading />}>
      <CallbackContent />
    </Suspense>
  )
}
