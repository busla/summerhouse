'use client'

/**
 * Amplify Provider Component
 *
 * Initializes AWS Amplify on the client side for use with Cognito EMAIL_OTP
 * authentication. Must be wrapped around components that use Amplify auth.
 *
 * Why client-side only?
 * - Amplify stores auth state in localStorage (browser-only)
 * - Static export means no SSR - all auth is client-side
 * - Provider pattern ensures initialization happens once before any auth calls
 */

import { useEffect, useState, type ReactNode } from 'react'
import { configureAmplify } from '@/lib/amplify-config'

interface AmplifyProviderProps {
  children: ReactNode
}

export function AmplifyProvider({ children }: AmplifyProviderProps) {
  const [isConfigured, setIsConfigured] = useState(false)

  useEffect(() => {
    // Configure Amplify on mount (client-side only)
    configureAmplify()
    setIsConfigured(true)
  }, [])

  // Render children immediately - auth state will hydrate asynchronously
  // This prevents hydration mismatch issues with static export
  if (!isConfigured) {
    return null
  }

  return <>{children}</>
}
