'use client'

/**
 * AuthErrorBoundary - Error boundary for authentication-related components (T034).
 *
 * Catches JavaScript errors in child components and displays a fallback UI
 * with retry functionality. This prevents auth errors from crashing the
 * entire application.
 */

import { Component, ReactNode } from 'react'

interface AuthErrorBoundaryProps {
  children: ReactNode
  onRetry?: () => void
}

interface AuthErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

/**
 * Error Boundary component for catching and handling auth-related crashes.
 *
 * Usage:
 * ```tsx
 * <AuthErrorBoundary onRetry={() => window.location.reload()}>
 *   <GuestDetailsForm />
 * </AuthErrorBoundary>
 * ```
 */
export class AuthErrorBoundary extends Component<
  AuthErrorBoundaryProps,
  AuthErrorBoundaryState
> {
  constructor(props: AuthErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): AuthErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    // Log error for debugging (could send to error tracking service)
    console.error('AuthErrorBoundary caught error:', error, errorInfo)
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, error: null })
    this.props.onRetry?.()
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div
          className="rounded-lg border border-red-200 bg-red-50 p-6 text-center"
          role="alert"
          aria-live="assertive"
        >
          <div className="mb-4">
            <svg
              className="mx-auto h-12 w-12 text-red-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>

          <h3 className="mb-2 text-lg font-semibold text-red-800">
            Something went wrong
          </h3>

          <p className="mb-4 text-sm text-red-600">
            We encountered an unexpected error. Please try again.
          </p>

          <button
            type="button"
            onClick={this.handleRetry}
            className="inline-flex items-center rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
          >
            Try again
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
