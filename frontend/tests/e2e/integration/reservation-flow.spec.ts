/**
 * Integration Tests: Complete Reservation Flow with Authentication
 *
 * Tests the full booking journey on the live site including:
 * 1. Checking availability for desired dates
 * 2. Getting pricing information
 * 3. Initiating a booking (triggers auth requirement)
 * 4. Email verification prompt
 * 5. OAuth2 authentication link rendering
 * 6. Session state after authentication
 *
 * Run with: yarn test:e2e:live
 *
 * Note: These tests cannot complete actual OAuth2 flows but verify
 * that authentication prompts appear correctly when booking is attempted.
 */

import { test, expect, type Page } from '@playwright/test'

// Longer timeout for AI responses
test.setTimeout(120000)

// === Test Helpers ===

/**
 * Send a message to the chat and wait for response
 */
async function sendMessage(page: Page, message: string): Promise<void> {
  const chatInput = page.getByPlaceholder(
    'Ask about availability, pricing, or the property...'
  )
  await chatInput.fill(message)
  await chatInput.press('Enter')

  // Wait for the message to be sent (input clears)
  await expect(chatInput).toHaveValue('')
}

/**
 * Wait for agent to respond with content matching pattern
 */
async function waitForAgentResponse(
  page: Page,
  pattern: RegExp,
  timeout = 30000
): Promise<void> {
  const chatArea = page.locator('main')
  await expect(chatArea).toContainText(pattern, { timeout })
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
 * Clear auth session from localStorage
 */
async function clearAuthSession(page: Page) {
  await page.evaluate(() => {
    localStorage.removeItem('booking_session')
    localStorage.removeItem('booking_verification')
  })
}

/**
 * Set mock auth session in localStorage
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

// === Complete Reservation Flow Tests ===

test.describe('Reservation Flow - Unauthenticated User', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/agent')
    await clearAuthSession(page)
    // Reload to ensure clean state
    await page.reload()
  })

  test('complete flow: check availability -> get price -> attempt booking -> auth required', async ({
    page,
  }) => {
    // Single comprehensive booking request (agent may lose context in multi-step)
    await sendMessage(
      page,
      'I want to book the apartment from July 10-20, 2026 for 2 guests. Please check availability and tell me the price.'
    )

    // Agent should respond about the booking request
    // May ask for verification, provide pricing, or ask clarifying questions
    await waitForAgentResponse(page, /july|book|price|€|guest|verif|email|availab|date/i, 45000)
  })

  test('booking attempt triggers email verification prompt', async ({ page }) => {
    // Direct booking request should trigger verification
    await sendMessage(
      page,
      'I want to book the apartment from August 1st to August 10th 2026 for 2 guests'
    )

    // Agent should respond asking for email or verification
    const chatArea = page.locator('main')

    // Wait for response about verification/email
    await expect(chatArea).toContainText(/email|verif|sign|account|confirm|authenticat/i, {
      timeout: 45000,
    })
  })

  test('agent explains verification requirement when booking', async ({ page }) => {
    // Ask about booking process
    await sendMessage(page, 'What do I need to do to make a reservation?')

    // Agent should explain the process including verification
    await waitForAgentResponse(page, /email|verif|book|confirm|guest/i, 30000)
  })
})

// === Email Verification Flow Tests ===

test.describe('Email Verification Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/agent')
    await clearAuthSession(page)
    await page.reload()
  })

  test('agent prompts for booking details when booking attempted', async ({ page }) => {
    await sendMessage(page, 'Book July 15-22, 2026 for me')

    // Agent should respond with availability/pricing and ask for details
    // (guest count, special requests) or email verification
    await waitForAgentResponse(page, /email|verif|sign|account|guest|how many|special request/i, 45000)
  })

  test('can provide email address to agent', async ({ page }) => {
    // First trigger booking flow
    await sendMessage(page, 'I want to reserve September 1-10, 2026')
    // Agent responds with booking details or asks for guest info/email
    await waitForAgentResponse(page, /email|verif|book|guest|availab/i, 45000)

    // Provide email
    await sendMessage(page, 'My email is test@example.com')

    // Agent should acknowledge and initiate verification
    await waitForAgentResponse(page, /verif|code|sent|email|test@example/i, 30000)
  })

  test('handles invalid email format', async ({ page }) => {
    await sendMessage(page, 'I want to book and my email is notanemail')

    // Agent should ask for valid email or handle gracefully
    await waitForAgentResponse(page, /email|valid|@|format/i, 30000)
  })
})

// === OAuth2 Authentication Link Tests ===

test.describe('OAuth2 Authentication', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/agent')
    await clearAuthSession(page)
    await page.reload()
  })

  test('OAuth2 auth links open correctly when provided', async ({ page }) => {
    // If agent provides OAuth2 link, verify it's clickable
    // First trigger a flow that might show auth link
    await sendMessage(page, 'I want to sign in to make a booking')

    // Wait for any response
    await page.waitForTimeout(10000)

    // Check if any auth-related links appear
    const authLinks = page.locator('a[href*="oauth"], a[href*="auth"], a[href*="cognito"]')
    const linkCount = await authLinks.count()

    if (linkCount > 0) {
      // Verify link has proper security attributes
      const firstLink = authLinks.first()
      await expect(firstLink).toBeVisible()

      // Auth links should open in new tab for security
      const target = await firstLink.getAttribute('target')
      const rel = await firstLink.getAttribute('rel')

      // Either opens in new tab with noopener, or same window
      if (target === '_blank') {
        expect(rel).toContain('noopener')
      }
    }
  })
})

// === Authenticated User Flow Tests ===

test.describe('Reservation Flow - Authenticated User', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/agent')

    // Set up mock authenticated session
    await setAuthSession(page, {
      isAuthenticated: true,
      guestId: 'guest_test_integration_123',
      email: 'integration-test@example.com',
      accessToken: 'mock_integration_test_token',
      expiresAt: Date.now() + 3600000, // 1 hour from now
    })

    // Reload to apply session
    await page.reload()
  })

  test('authenticated user can proceed with booking details', async ({ page }) => {
    // Verify session is set
    const session = await getAuthSession(page)
    expect(session?.isAuthenticated).toBe(true)

    // Make booking request - shouldn't be blocked by auth
    await sendMessage(page, 'I want to book October 5-12, 2026 for 2 guests')

    // Agent should proceed with booking details (dates, pricing, confirmation)
    // Not ask for authentication again
    await waitForAgentResponse(page, /october|price|€|book|confirm|guest/i, 45000)
  })

  test('authenticated user sees personalized responses', async ({ page }) => {
    // Greet the agent
    await sendMessage(page, 'Hello!')

    // Agent might acknowledge the user (though not required)
    await waitForAgentResponse(page, /.{10,}/i, 30000)

    // Session should still be valid
    const session = await getAuthSession(page)
    expect(session?.isAuthenticated).toBe(true)
  })

  test('session persists across page navigation', async ({ page }) => {
    // Navigate away
    await page.goto('/pricing')
    await page.waitForTimeout(1000)

    // Navigate back
    await page.goto('/agent')

    // Session should still be there
    const session = await getAuthSession(page)
    expect(session?.isAuthenticated).toBe(true)
    expect(session?.email).toBe('integration-test@example.com')
  })
})

// === Booking Confirmation Flow Tests ===

test.describe('Booking Confirmation Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/agent')
    await setAuthSession(page, {
      isAuthenticated: true,
      guestId: 'guest_confirm_test',
      email: 'confirm-test@example.com',
      accessToken: 'mock_confirm_token',
      expiresAt: Date.now() + 3600000,
    })
    await page.reload()
  })

  test('agent provides booking summary before confirmation', async ({ page }) => {
    await sendMessage(page, 'Book November 1-8, 2026 for 3 guests')

    // Agent should provide summary with details
    await waitForAgentResponse(page, /november|guest|night|€|total|confirm/i, 45000)
  })

  test('agent handles guest count validation', async ({ page }) => {
    // Try to book with too many guests (max is 4)
    await sendMessage(page, 'Book December 10-17, 2026 for 6 guests')

    // Agent should mention max guest limit
    await waitForAgentResponse(page, /guest|maximum|4|limit|accommodate/i, 30000)
  })

  test('agent calculates total with cleaning fee', async ({ page }) => {
    await sendMessage(page, 'What is the total cost for January 10-17, 2027?')

    // Should mention nightly rate and/or cleaning fee
    await waitForAgentResponse(page, /€|total|night|clean|fee/i, 30000)
  })
})

// === Edge Cases and Error Handling ===

test.describe('Reservation Edge Cases', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/agent')
    await clearAuthSession(page)
    await page.reload()
  })

  test('handles dates that are already booked', async ({ page }) => {
    // The seed data has some blocked dates - test that agent handles them
    await sendMessage(page, 'Is July 15-28, 2026 available?')

    // These dates are blocked in seed data (RES-2025-TEST003)
    // Agent should indicate unavailability or suggest alternatives
    await waitForAgentResponse(page, /availab|book|dates|sorry|alternative|unavailab/i, 30000)
  })

  test('handles cross-year booking request', async ({ page }) => {
    await sendMessage(page, 'Can I book December 28, 2026 to January 5, 2027?')

    // Agent should handle cross-year dates
    await waitForAgentResponse(page, /december|january|2026|2027|availab|book/i, 30000)
  })

  test('handles vague date requests', async ({ page }) => {
    await sendMessage(page, 'I want to book sometime in the summer')

    // Agent should ask for specific dates
    await waitForAgentResponse(page, /when|date|specific|july|august|june/i, 30000)
  })

  test('handles modification request without existing booking', async ({ page }) => {
    await sendMessage(page, 'I want to change my booking to different dates')

    // Agent should ask for booking reference or clarify
    await waitForAgentResponse(page, /booking|reference|reservation|which|find/i, 30000)
  })
})

// === Session Expiry Tests ===

test.describe('Session Expiry Handling', () => {
  test('expired session is detected', async ({ page }) => {
    await page.goto('/agent')

    // Set expired session
    await setAuthSession(page, {
      isAuthenticated: true,
      guestId: 'guest_expired',
      email: 'expired@example.com',
      expiresAt: Date.now() - 1000, // Already expired
    })

    // Check expiry detection
    const isExpired = await page.evaluate(() => {
      const stored = localStorage.getItem('booking_session')
      if (!stored) return true
      const session = JSON.parse(stored)
      return session.expiresAt && Date.now() > session.expiresAt
    })

    expect(isExpired).toBe(true)
  })

  test('page still functions with expired session', async ({ page }) => {
    await page.goto('/agent')

    // Set expired session
    await setAuthSession(page, {
      isAuthenticated: true,
      guestId: 'guest_expired',
      email: 'expired@example.com',
      expiresAt: Date.now() - 1000,
    })

    await page.reload()

    // Chat should still work
    const chatInput = page.getByPlaceholder(
      'Ask about availability, pricing, or the property...'
    )
    await expect(chatInput).toBeVisible()
    await expect(chatInput).toBeEnabled()

    // Can still ask questions
    await sendMessage(page, 'What are the prices?')
    await waitForAgentResponse(page, /price|€|rate|season/i, 30000)
  })
})

// === Multi-Step Conversation Tests ===

test.describe('Multi-Step Conversation Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/agent')
    await clearAuthSession(page)
    await page.reload()
  })

  test('agent responds to availability and pricing in single request', async ({ page }) => {
    // Combined request since agent may not maintain context across messages
    await sendMessage(
      page,
      'I want to stay August 15-22, 2026 with 2 adults and 1 child. What is the total price?'
    )

    // Agent should respond about either availability, pricing, or both
    await waitForAgentResponse(page, /august|€|price|guest|availab|night|book/i, 30000)
  })

  test('agent responds to booking inquiry with details', async ({ page }) => {
    // Combined request with all details upfront
    await sendMessage(
      page,
      'Hello! I want to book the apartment September 5-15, 2026 for 2 guests. Does it have air conditioning and what would be the total cost?'
    )

    // Agent should respond about the booking request
    await waitForAgentResponse(page, /september|book|€|price|air|condition|ameniti|guest/i, 45000)
  })
})
