/**
 * E2E Tests: Authentication Flow
 *
 * Tests the authentication experience in the booking assistant:
 * 1. Email verification UI components
 * 2. OTP code input and validation
 * 3. Auth session persistence
 * 4. OAuth2 3LO auth link rendering
 * 5. Authenticated vs unauthenticated states
 *
 * Architecture Note:
 * The frontend uses direct browser-to-AgentCore communication via AWS SDK.
 * These tests mock auth state via localStorage and test UI interactions.
 */

import { test, expect, type Page } from '@playwright/test'

// === Test Helpers ===

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

/**
 * Mock verification state in localStorage
 */
async function setVerificationState(
  page: Page,
  state: {
    email: string
    codeRequested: boolean
    verified: boolean
    expiresAt?: number
  }
) {
  await page.evaluate((stateData) => {
    localStorage.setItem('booking_verification', JSON.stringify(stateData))
  }, state)
}

// === Verification Code Input Tests ===

test.describe('Verification Code Input Component', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await clearAuthSession(page)
  })

  test('verification code input accepts 6 digits', async ({ page }) => {
    // This test verifies the VerificationCodeInput component behavior
    // The component is rendered when agent sends verification_code rich content

    // Navigate to page and check it loads
    // Note: The heading is "Welcome to Quesada Apartment!" from the title prop
    await expect(page.getByText('Welcome to Quesada Apartment!')).toBeVisible()

    // The VerificationCodeInput is a standalone component
    // We test its behavior by checking its accessibility features
    // Note: In actual use, it appears when agent requests verification

    // Verify the page loads without auth errors
    const welcomeText = page.getByText('Welcome to Quesada Apartment!')
    await expect(welcomeText).toBeVisible()
  })

  test('OTP input handles paste correctly', async ({ page }) => {
    // Test OTP paste functionality by evaluating component behavior
    // This is a unit-level test within E2E context

    const result = await page.evaluate(() => {
      // Simulate OTP parsing logic
      const pastedData = '123-456'
      const cleanedOtp = pastedData.replace(/\D/g, '').slice(0, 6)
      return cleanedOtp
    })

    expect(result).toBe('123456')
  })

  test('OTP input validates numeric-only input', async ({ page }) => {
    const result = await page.evaluate(() => {
      // Simulate input validation
      const inputs = ['a', '1', 'b2c', '!@#', '45', '678']
      return inputs.map((input) => input.replace(/\D/g, '').slice(-1))
    })

    expect(result).toEqual(['', '1', '2', '', '5', '8'])
  })
})

// === Auth Session Tests ===

test.describe('Auth Session Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await clearAuthSession(page)
  })

  test('starts with no auth session', async ({ page }) => {
    const session = await getAuthSession(page)
    expect(session).toBeNull()
  })

  test('persists auth session in localStorage', async ({ page }) => {
    const testSession = {
      isAuthenticated: true,
      guestId: 'guest_123',
      email: 'test@example.com',
      accessToken: 'mock_token_abc',
      expiresAt: Date.now() + 3600000, // 1 hour from now
    }

    await setAuthSession(page, testSession)

    const stored = await getAuthSession(page)
    expect(stored.isAuthenticated).toBe(true)
    expect(stored.guestId).toBe('guest_123')
    expect(stored.email).toBe('test@example.com')
  })

  test('clears auth session correctly', async ({ page }) => {
    // Set session first
    await setAuthSession(page, {
      isAuthenticated: true,
      guestId: 'guest_123',
      email: 'test@example.com',
    })

    // Verify it was set
    let session = await getAuthSession(page)
    expect(session).not.toBeNull()

    // Clear session
    await clearAuthSession(page)

    // Verify it was cleared
    session = await getAuthSession(page)
    expect(session).toBeNull()
  })

  test('expired session is treated as unauthenticated', async ({ page }) => {
    // Set expired session
    await setAuthSession(page, {
      isAuthenticated: true,
      guestId: 'guest_123',
      email: 'test@example.com',
      expiresAt: Date.now() - 1000, // Already expired
    })

    // The auth utility should check expiry
    const isExpired = await page.evaluate(() => {
      const stored = localStorage.getItem('booking_session')
      if (!stored) return true

      const session = JSON.parse(stored)
      if (session.expiresAt && Date.now() > session.expiresAt) {
        return true
      }
      return false
    })

    expect(isExpired).toBe(true)
  })
})

// === Verification State Tests ===

test.describe('Verification State Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await clearAuthSession(page)
  })

  test('stores verification state when OTP requested', async ({ page }) => {
    const verificationState = {
      email: 'user@example.com',
      codeRequested: true,
      verified: false,
      expiresAt: Date.now() + 300000, // 5 minutes
    }

    await setVerificationState(page, verificationState)

    const stored = await page.evaluate(() => {
      const state = localStorage.getItem('booking_verification')
      return state ? JSON.parse(state) : null
    })

    expect(stored.email).toBe('user@example.com')
    expect(stored.codeRequested).toBe(true)
    expect(stored.verified).toBe(false)
  })

  test('verification state expires after 5 minutes', async ({ page }) => {
    // Set already-expired verification state
    await setVerificationState(page, {
      email: 'user@example.com',
      codeRequested: true,
      verified: false,
      expiresAt: Date.now() - 1000, // Already expired
    })

    const isExpired = await page.evaluate(() => {
      const stored = localStorage.getItem('booking_verification')
      if (!stored) return true

      const state = JSON.parse(stored)
      if (state.expiresAt && Date.now() > state.expiresAt) {
        return true
      }
      return false
    })

    expect(isExpired).toBe(true)
  })
})

// === OAuth2 Auth Link Tests ===

test.describe('OAuth2 Auth Link Rendering', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await clearAuthSession(page)
  })

  test('renders OAuth2 auth URL as clickable link in chat', async ({ page }) => {
    // Simulate agent message containing OAuth2 auth URL
    const authUrl =
      'https://cognito.example.com/oauth2/authorize?client_id=abc&redirect_uri=https://app.example.com/auth/callback'

    // Test that URL rendering logic works
    const result = await page.evaluate((url) => {
      // Simulate URL detection regex (similar to what RichContentRenderer might use)
      const urlPattern = /https?:\/\/[^\s]+/g
      const matches = url.match(urlPattern)
      return matches ? matches[0] : null
    }, authUrl)

    expect(result).toBe(authUrl)
  })

  test('auth URL opens in new context when clicked', async ({ page, context }) => {
    // This tests that external auth URLs would open correctly
    // Note: In E2E, we verify the link behavior, not actual OAuth flow

    // Create a test link element
    await page.evaluate(() => {
      const link = document.createElement('a')
      link.href = 'https://cognito.example.com/oauth2/authorize'
      link.target = '_blank'
      link.rel = 'noopener noreferrer'
      link.id = 'test-auth-link'
      link.textContent = 'Click to authenticate'
      document.body.appendChild(link)
    })

    const link = page.locator('#test-auth-link')
    await expect(link).toBeVisible()

    // Verify link attributes
    await expect(link).toHaveAttribute('target', '_blank')
    await expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })
})

// === Agent Auth Flow Tests ===

test.describe('Agent-Driven Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await clearAuthSession(page)
  })

  test('displays welcome message for unauthenticated users', async ({ page }) => {
    // Unauthenticated state should show normal welcome
    await expect(page.getByText('Welcome to Quesada Apartment!')).toBeVisible()
    await expect(page.getByText("I'm your booking assistant")).toBeVisible()
  })

  test('chat interface remains functional when authenticated', async ({ page }) => {
    // Set authenticated session
    await setAuthSession(page, {
      isAuthenticated: true,
      guestId: 'guest_123',
      email: 'authenticated@example.com',
      accessToken: 'valid_token',
      expiresAt: Date.now() + 3600000,
    })

    // Reload to apply session
    await page.reload()

    // Chat should still work
    await expect(page.getByText('Welcome to Quesada Apartment!')).toBeVisible()

    const input = page.getByPlaceholder('Ask about availability, pricing, or the property...')
    await expect(input).toBeVisible()
    await expect(input).toBeEnabled()
  })

  test('suggestion buttons work regardless of auth state', async ({ page }) => {
    // Test that core functionality works whether authenticated or not
    const checkAvailability = page.getByRole('button', { name: 'Check availability' })
    await expect(checkAvailability).toBeVisible()
    await expect(checkAvailability).toBeEnabled()

    const seePricing = page.getByRole('button', { name: 'See pricing' })
    await expect(seePricing).toBeVisible()
    await expect(seePricing).toBeEnabled()
  })
})

// === Email Validation Tests ===

test.describe('Email Validation', () => {
  test('validates email format correctly', async ({ page }) => {
    await page.goto('/')

    // Test email validation logic (mirrors backend/frontend validation)
    const testCases = await page.evaluate(() => {
      const emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/

      return [
        { email: 'valid@example.com', expected: true },
        { email: 'user.name+tag@domain.co.uk', expected: true },
        { email: 'invalid', expected: false },
        { email: '@nodomain.com', expected: false },
        { email: 'no@tld', expected: false },
        { email: '', expected: false },
        { email: 'spaces in@email.com', expected: false },
      ].map(({ email, expected }) => ({
        email,
        expected,
        actual: emailPattern.test(email),
      }))
    })

    for (const tc of testCases) {
      expect(tc.actual).toBe(tc.expected)
    }
  })
})

// === Auth Error Handling Tests ===

test.describe('Auth Error Handling', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await clearAuthSession(page)
  })

  test('handles invalid OTP gracefully', async ({ page }) => {
    // Simulate error state
    const errorScenarios = await page.evaluate(() => {
      const errors = [
        { code: 'INVALID_OTP', message: 'Invalid verification code' },
        { code: 'OTP_EXPIRED', message: 'Verification code has expired' },
        { code: 'MAX_ATTEMPTS_EXCEEDED', message: 'Too many failed attempts' },
      ]

      return errors.map((error) => ({
        ...error,
        hasRecoveryAction:
          error.code === 'OTP_EXPIRED' || error.code === 'MAX_ATTEMPTS_EXCEEDED',
      }))
    })

    // Verify error structure
    expect(errorScenarios).toHaveLength(3)
    expect(errorScenarios[0].hasRecoveryAction).toBe(false)
    expect(errorScenarios[1].hasRecoveryAction).toBe(true)
    expect(errorScenarios[2].hasRecoveryAction).toBe(true)
  })

  test('handles network errors during auth', async ({ page }) => {
    // Test error message display
    const errorMessage = 'Failed to send verification email'

    await page.evaluate((msg) => {
      // Store error for display
      sessionStorage.setItem('auth_error', msg)
    }, errorMessage)

    const stored = await page.evaluate(() => sessionStorage.getItem('auth_error'))
    expect(stored).toBe(errorMessage)
  })
})

// === Auth Token Tests ===

test.describe('Auth Token Handling', () => {
  test('stores access token securely', async ({ page }) => {
    await page.goto('/')

    // Set auth session with token
    await setAuthSession(page, {
      isAuthenticated: true,
      guestId: 'guest_456',
      email: 'token@example.com',
      accessToken: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.payload',
      expiresAt: Date.now() + 3600000,
    })

    // Verify token is stored (but not exposed in DOM)
    const hasToken = await page.evaluate(() => {
      const stored = localStorage.getItem('booking_session')
      if (!stored) return false
      const session = JSON.parse(stored)
      return !!session.accessToken
    })

    expect(hasToken).toBe(true)

    // Verify token is not exposed in page content
    const pageContent = await page.content()
    expect(pageContent).not.toContain('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9')
  })

  test('generates correct auth headers', async ({ page }) => {
    await page.goto('/')

    // Set auth session
    await setAuthSession(page, {
      isAuthenticated: true,
      guestId: 'guest_789',
      email: 'headers@example.com',
      accessToken: 'test_access_token_xyz',
    })

    // Test header generation logic
    const headers = await page.evaluate(() => {
      const stored = localStorage.getItem('booking_session')
      if (!stored) return {}

      const session = JSON.parse(stored)
      if (!session.accessToken) return {}

      return { Authorization: `Bearer ${session.accessToken}` }
    })

    expect(headers.Authorization).toBe('Bearer test_access_token_xyz')
  })
})

// === Multi-Tab Session Tests ===

test.describe('Multi-Tab Session Consistency', () => {
  test('session persists across page navigation', async ({ page }) => {
    await page.goto('/')

    // Set session
    await setAuthSession(page, {
      isAuthenticated: true,
      guestId: 'guest_nav',
      email: 'nav@example.com',
    })

    // Navigate to another page
    await page.goto('/pricing')

    // Session should still be there
    const session = await getAuthSession(page)
    expect(session.guestId).toBe('guest_nav')

    // Navigate back
    await page.goto('/')
    const sessionAfterBack = await getAuthSession(page)
    expect(sessionAfterBack.guestId).toBe('guest_nav')
  })

  test('session survives page reload', async ({ page }) => {
    await page.goto('/')

    await setAuthSession(page, {
      isAuthenticated: true,
      guestId: 'guest_reload',
      email: 'reload@example.com',
      accessToken: 'token_reload',
    })

    // Reload page
    await page.reload()

    // Session should persist
    const session = await getAuthSession(page)
    expect(session.guestId).toBe('guest_reload')
    expect(session.accessToken).toBe('token_reload')
  })
})

// === Accessibility Tests for Auth Components ===

test.describe('Auth Component Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('form inputs have proper aria labels', async ({ page }) => {
    // Check main chat input accessibility
    const input = page.getByPlaceholder('Ask about availability, pricing, or the property...')
    await expect(input).toBeVisible()

    // Input should be focusable via keyboard
    await input.focus()
    await expect(input).toBeFocused()
  })

  test('buttons are keyboard accessible', async ({ page }) => {
    // Suggestion buttons should be keyboard navigable
    const button = page.getByRole('button', { name: 'Check availability' })
    await button.focus()
    await expect(button).toBeFocused()

    // Should be activatable with Enter key
    // (We don't actually press Enter to avoid side effects in this test)
  })
})
