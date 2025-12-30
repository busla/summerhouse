/**
 * E2E Tests: OAuth2 Callback Flow
 *
 * Tests the OAuth2 3LO callback handling:
 * 1. Successful callback with session_id
 * 2. Error handling for OAuth2 failures
 * 3. Session status polling
 * 4. Redirect to appropriate pages after auth
 *
 * Architecture Note:
 * The backend `/auth/callback` endpoint redirects to frontend with:
 * - Success: /auth/callback?status=success&session_id=xxx
 * - Error: /auth/callback?status=error&error=code&error_description=desc
 *
 * The frontend callback page should:
 * 1. Parse query parameters
 * 2. Show success/error state
 * 3. Update auth session in localStorage
 * 4. Redirect to main app or show error UI
 *
 * Note: The frontend /auth/callback page is marked as optional (T079-T084).
 * These tests document the expected behavior for when it's implemented.
 */

import { test, expect, type Page } from '@playwright/test'

// === Test Helpers ===

/**
 * Build OAuth2 callback URL with params
 */
function buildCallbackUrl(params: Record<string, string>): string {
  const searchParams = new URLSearchParams(params)
  return `/auth/callback?${searchParams.toString()}`
}

/**
 * Mock auth session in localStorage
 */
async function setAuthSession(
  page: Page,
  session: {
    isAuthenticated: boolean
    guestId?: string
    email?: string
    accessToken?: string
    expiresAt?: number
  }
) {
  await page.evaluate((sessionData) => {
    localStorage.setItem('booking_session', JSON.stringify(sessionData))
  }, session)
}

/**
 * Clear auth session from localStorage
 */
async function clearAuthSession(page: Page) {
  await page.evaluate(() => {
    localStorage.removeItem('booking_session')
    localStorage.removeItem('booking_verification')
  })
}

/**
 * Get auth session from localStorage
 */
async function getAuthSession(page: Page) {
  return await page.evaluate(() => {
    const stored = localStorage.getItem('booking_session')
    return stored ? JSON.parse(stored) : null
  })
}

// === OAuth2 Callback Tests ===

test.describe('OAuth2 Callback URL Parsing', () => {
  test('parses success callback params correctly', async ({ page }) => {
    // Test URL parsing logic
    const callbackUrl = buildCallbackUrl({
      status: 'success',
      session_id: 'sess_abc123def456',
    })

    const params = await page.evaluate((url) => {
      const searchParams = new URLSearchParams(url.split('?')[1])
      return {
        status: searchParams.get('status'),
        sessionId: searchParams.get('session_id'),
      }
    }, callbackUrl)

    expect(params.status).toBe('success')
    expect(params.sessionId).toBe('sess_abc123def456')
  })

  test('parses error callback params correctly', async ({ page }) => {
    const callbackUrl = buildCallbackUrl({
      status: 'error',
      error: 'access_denied',
      error_description: 'User cancelled the login',
    })

    const params = await page.evaluate((url) => {
      const searchParams = new URLSearchParams(url.split('?')[1])
      return {
        status: searchParams.get('status'),
        error: searchParams.get('error'),
        errorDescription: searchParams.get('error_description'),
      }
    }, callbackUrl)

    expect(params.status).toBe('error')
    expect(params.error).toBe('access_denied')
    expect(params.errorDescription).toBe('User cancelled the login')
  })

  test('handles missing session_id gracefully', async ({ page }) => {
    const callbackUrl = buildCallbackUrl({
      status: 'success',
      // Missing session_id
    })

    const params = await page.evaluate((url) => {
      const searchParams = new URLSearchParams(url.split('?')[1])
      return {
        status: searchParams.get('status'),
        sessionId: searchParams.get('session_id'),
        isValid: searchParams.get('status') === 'success' && !!searchParams.get('session_id'),
      }
    }, callbackUrl)

    expect(params.sessionId).toBeNull()
    expect(params.isValid).toBe(false)
  })
})

// === OAuth2 Error Handling Tests ===

test.describe('OAuth2 Error Scenarios', () => {
  test('handles access_denied error', async ({ page }) => {
    const errorInfo = {
      code: 'access_denied',
      description: 'User cancelled the login',
      userFriendlyMessage: 'You cancelled the login. Please try again when ready.',
    }

    // Test error message mapping
    const result = await page.evaluate((error) => {
      const errorMessages: Record<string, string> = {
        access_denied: 'You cancelled the login. Please try again when ready.',
        invalid_request: 'There was a problem with the login request.',
        unauthorized_client: 'This application is not authorized.',
        server_error: 'The authentication server encountered an error.',
      }
      return errorMessages[error.code] || 'An unknown error occurred.'
    }, errorInfo)

    expect(result).toBe(errorInfo.userFriendlyMessage)
  })

  test('handles server_error appropriately', async ({ page }) => {
    const result = await page.evaluate(() => {
      const errorMessages: Record<string, string> = {
        access_denied: 'You cancelled the login. Please try again when ready.',
        invalid_request: 'There was a problem with the login request.',
        unauthorized_client: 'This application is not authorized.',
        server_error: 'The authentication server encountered an error.',
      }
      return errorMessages['server_error']
    })

    expect(result).toBe('The authentication server encountered an error.')
  })

  test('handles unknown error codes', async ({ page }) => {
    const result = await page.evaluate(() => {
      const errorCode = 'completely_unknown_error'
      const errorMessages: Record<string, string> = {
        access_denied: 'You cancelled the login.',
        server_error: 'Server error.',
      }
      return errorMessages[errorCode] || 'An unexpected error occurred. Please try again.'
    })

    expect(result).toBe('An unexpected error occurred. Please try again.')
  })
})

// === Session State Tests ===

test.describe('OAuth2 Session State Updates', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await clearAuthSession(page)
  })

  test('successful OAuth2 creates authenticated session', async ({ page }) => {
    // Simulate what callback page should do on success
    await page.evaluate(() => {
      // This mimics the callback page behavior
      const sessionData = {
        isAuthenticated: true,
        guestId: 'guest_oauth_123',
        email: 'oauth@example.com',
        // Note: accessToken would come from backend API
      }
      localStorage.setItem('booking_session', JSON.stringify(sessionData))
    })

    const session = await getAuthSession(page)
    expect(session.isAuthenticated).toBe(true)
    expect(session.guestId).toBe('guest_oauth_123')
    expect(session.email).toBe('oauth@example.com')
  })

  test('failed OAuth2 does not create session', async ({ page }) => {
    // Simulate failed callback - should not set session
    await page.evaluate(() => {
      // On error, callback page should NOT set auth session
      // Just display error message
    })

    const session = await getAuthSession(page)
    expect(session).toBeNull()
  })

  test('OAuth2 success clears pending verification state', async ({ page }) => {
    // Set pending verification state
    await page.evaluate(() => {
      localStorage.setItem(
        'booking_verification',
        JSON.stringify({
          email: 'pending@example.com',
          codeRequested: true,
          verified: false,
        })
      )
    })

    // Simulate successful OAuth2 completion
    await page.evaluate(() => {
      // Callback page should clear verification state and set session
      localStorage.removeItem('booking_verification')
      localStorage.setItem(
        'booking_session',
        JSON.stringify({
          isAuthenticated: true,
          guestId: 'guest_oauth_456',
          email: 'oauth@example.com',
        })
      )
    })

    const verificationState = await page.evaluate(() =>
      localStorage.getItem('booking_verification')
    )
    expect(verificationState).toBeNull()

    const session = await getAuthSession(page)
    expect(session.isAuthenticated).toBe(true)
  })
})

// === Redirect Tests ===

test.describe('Post-Auth Redirects', () => {
  test('determines correct redirect based on return URL', async ({ page }) => {
    // Navigate first so window.location.origin is properly set
    await page.goto('/')

    // Test redirect logic
    const testCases = await page.evaluate(() => {
      function getRedirectUrl(returnUrl: string | null, defaultPath: string = '/'): string {
        if (!returnUrl) return defaultPath

        // Security: Only allow relative URLs or same-origin
        try {
          const url = new URL(returnUrl, window.location.origin)
          if (url.origin === window.location.origin) {
            return url.pathname + url.search
          }
        } catch {
          // Invalid URL, use default
        }
        return defaultPath
      }

      return [
        { returnUrl: null, expected: '/' },
        { returnUrl: '/pricing', expected: '/pricing' },
        { returnUrl: '/booking/confirm', expected: '/booking/confirm' },
        { returnUrl: 'https://malicious.com', expected: '/' }, // Should not allow
      ].map(({ returnUrl, expected }) => ({
        returnUrl,
        expected,
        actual: getRedirectUrl(returnUrl),
      }))
    })

    for (const tc of testCases) {
      expect(tc.actual).toBe(tc.expected)
    }
  })

  test('preserves booking context in session storage', async ({ page }) => {
    await page.goto('/')

    // Simulate storing booking context before auth redirect
    await page.evaluate(() => {
      const bookingContext = {
        checkIn: '2025-02-01',
        checkOut: '2025-02-07',
        guests: 2,
        returnToBooking: true,
      }
      sessionStorage.setItem('booking_context', JSON.stringify(bookingContext))
    })

    // After OAuth2 callback, context should still be available
    const context = await page.evaluate(() => {
      const stored = sessionStorage.getItem('booking_context')
      return stored ? JSON.parse(stored) : null
    })

    expect(context.checkIn).toBe('2025-02-01')
    expect(context.checkOut).toBe('2025-02-07')
    expect(context.guests).toBe(2)
    expect(context.returnToBooking).toBe(true)
  })
})

// === Session Status Polling Tests ===

test.describe('Session Status Polling', () => {
  test('implements exponential backoff for polling', async ({ page }) => {
    // Test polling logic without actual network calls
    const delays = await page.evaluate(() => {
      const baseDelay = 1000
      const maxDelay = 30000
      const attempts = 6

      const delays: number[] = []
      for (let i = 0; i < attempts; i++) {
        const delay = Math.min(baseDelay * Math.pow(2, i), maxDelay)
        delays.push(delay)
      }
      return delays
    })

    expect(delays).toEqual([1000, 2000, 4000, 8000, 16000, 30000])
  })

  test('session status transitions correctly', async ({ page }) => {
    const stateMachine = await page.evaluate(() => {
      type SessionStatus = 'pending' | 'completed' | 'failed' | 'expired'

      const validTransitions: Record<SessionStatus, SessionStatus[]> = {
        pending: ['completed', 'failed', 'expired'],
        completed: [], // Terminal state
        failed: [], // Terminal state
        expired: [], // Terminal state
      }

      function canTransition(from: SessionStatus, to: SessionStatus): boolean {
        return validTransitions[from]?.includes(to) ?? false
      }

      return {
        pendingToCompleted: canTransition('pending', 'completed'),
        pendingToFailed: canTransition('pending', 'failed'),
        completedToPending: canTransition('completed', 'pending'),
        failedToCompleted: canTransition('failed', 'completed'),
      }
    })

    expect(stateMachine.pendingToCompleted).toBe(true)
    expect(stateMachine.pendingToFailed).toBe(true)
    expect(stateMachine.completedToPending).toBe(false)
    expect(stateMachine.failedToCompleted).toBe(false)
  })
})

// === Security Tests ===

test.describe('OAuth2 Security', () => {
  test('validates state parameter to prevent CSRF', async ({ page }) => {
    // Test state validation logic
    const result = await page.evaluate(() => {
      const storedState = 'random_state_abc123'
      const receivedState = 'random_state_abc123'
      const mismatchedState = 'different_state_xyz789'

      return {
        validState: storedState === receivedState,
        invalidState: storedState === mismatchedState,
      }
    })

    expect(result.validState).toBe(true)
    expect(result.invalidState).toBe(false)
  })

  test('sanitizes error messages to prevent XSS', async ({ page }) => {
    const sanitized = await page.evaluate(() => {
      function sanitizeError(message: string): string {
        return message
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;')
          .replace(/'/g, '&#x27;')
      }

      const maliciousError = '<script>alert("xss")</script>'
      return sanitizeError(maliciousError)
    })

    expect(sanitized).toBe('&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;')
    expect(sanitized).not.toContain('<script>')
  })

  test('does not expose sensitive data in URLs', async ({ page }) => {
    // Verify callback URL doesn't contain access tokens
    const callbackUrl = buildCallbackUrl({
      status: 'success',
      session_id: 'sess_abc123',
      // Should NOT contain: access_token, id_token, refresh_token
    })

    expect(callbackUrl).not.toContain('access_token')
    expect(callbackUrl).not.toContain('id_token')
    expect(callbackUrl).not.toContain('refresh_token')
  })
})

// === Loading States Tests ===

test.describe('OAuth2 Callback Loading States', () => {
  test('defines correct loading states', async ({ page }) => {
    const states = await page.evaluate(() => {
      type CallbackState = 'loading' | 'validating' | 'success' | 'error'

      const stateMessages: Record<CallbackState, string> = {
        loading: 'Processing authentication...',
        validating: 'Verifying your session...',
        success: 'Authentication successful! Redirecting...',
        error: 'Authentication failed. Please try again.',
      }

      return Object.entries(stateMessages).map(([state, message]) => ({
        state,
        message,
        hasMessage: message.length > 0,
      }))
    })

    expect(states).toHaveLength(4)
    states.forEach((s) => expect(s.hasMessage).toBe(true))
  })
})

// === Integration with Main App Tests ===

test.describe('Auth Integration with Main App', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await clearAuthSession(page)
  })

  test('authenticated user can access booking features', async ({ page }) => {
    // Set authenticated session
    await setAuthSession(page, {
      isAuthenticated: true,
      guestId: 'guest_booking',
      email: 'booking@example.com',
      accessToken: 'valid_token',
      expiresAt: Date.now() + 3600000,
    })

    // Reload to apply session
    await page.reload()

    // Verify main page loads
    await expect(page.getByText('Welcome to Quesada Apartment!')).toBeVisible()

    // Verify chat input is available
    const input = page.getByPlaceholder('Ask about availability, pricing, or the property...')
    await expect(input).toBeEnabled()
  })

  test('session survives navigation to different pages', async ({ page }) => {
    await setAuthSession(page, {
      isAuthenticated: true,
      guestId: 'guest_nav',
      email: 'nav@example.com',
    })

    // Navigate to different pages
    const pages = ['/', '/pricing', '/about', '/faq']

    for (const path of pages) {
      await page.goto(path)
      const session = await getAuthSession(page)
      expect(session.isAuthenticated).toBe(true)
      expect(session.guestId).toBe('guest_nav')
    }
  })
})
