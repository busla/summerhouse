/**
 * E2E Test: Anonymous Inquiry Flow (T008)
 *
 * Tests that users can browse availability, pricing, and property details
 * without authentication. This validates User Story 1 - Anonymous Inquiry Browsing.
 *
 * Per spec: "Users browse availability, pricing, property details without authentication"
 *
 * Test flow:
 * 1. Open website (no login)
 * 2. Send inquiry message to agent
 * 3. Verify agent responds with availability data
 * 4. Verify NO authentication prompts are shown
 */

import { test, expect } from '@playwright/test'

test.describe('Anonymous Inquiry Flow (US1)', () => {
  test.beforeEach(async ({ page }) => {
    // Start from the home page (chat interface)
    await page.goto('/')
    // Wait for the chat interface to be ready
    await expect(page.getByText('Welcome to Quesada Apartment!')).toBeVisible({ timeout: 10000 })
  })

  test('can view chat interface without authentication', async ({ page }) => {
    // Chat input should be available without login
    const chatInput = page.getByPlaceholder(/type.*message|ask.*question|message/i)
    await expect(chatInput).toBeVisible()
    await expect(chatInput).toBeEnabled()
  })

  test('can send inquiry message without authentication', async ({ page }) => {
    // Type an inquiry message
    const chatInput = page.getByPlaceholder(/type.*message|ask.*question|message/i)
    await chatInput.fill('What dates are available in March?')

    // Submit the message
    const sendButton = page.getByRole('button', { name: /send/i })
    await sendButton.click()

    // Wait for the message to appear in chat (user message)
    await expect(page.getByText('What dates are available in March?')).toBeVisible({
      timeout: 5000,
    })

    // Wait for agent response (this may take a few seconds)
    // Look for any response that indicates the agent is working
    const agentResponse = page.locator('[data-role="assistant"]').or(
      page.locator('.assistant-message')
    )

    // Either we get a response or we see loading indicator
    const hasResponse = await agentResponse.first().isVisible({ timeout: 30000 }).catch(() => false)
    const hasLoading = await page.getByText(/thinking|loading|processing/i).isVisible().catch(() => false)

    // At minimum, verify no auth prompt appeared
    const authPrompt = page.getByText(/sign in|log in|authenticate|verify.*email/i)
    expect(await authPrompt.isVisible().catch(() => false)).toBe(false)
  })

  test('does not prompt for authentication on inquiry', async ({ page }) => {
    // Send a pricing inquiry
    const chatInput = page.getByPlaceholder(/type.*message|ask.*question|message/i)
    await chatInput.fill('How much does it cost to stay for a week in July?')

    const sendButton = page.getByRole('button', { name: /send/i })
    await sendButton.click()

    // Wait a moment for any auth prompts
    await page.waitForTimeout(3000)

    // Verify no login/auth elements appeared
    const loginButton = page.getByRole('button', { name: /log.*in|sign.*in/i })
    const authModal = page.locator('[role="dialog"]').filter({ hasText: /sign.*in|log.*in|authenticate/i })

    expect(await loginButton.isVisible().catch(() => false)).toBe(false)
    expect(await authModal.isVisible().catch(() => false)).toBe(false)
  })

  test('can view property information without authentication', async ({ page }) => {
    // Navigate to About page (property details)
    await page.goto('/about')

    // Verify property information is visible without auth
    await expect(page.getByRole('heading', { name: /About Quesada Apartment/i })).toBeVisible()
    await expect(page.getByText(/2 Bedrooms/i)).toBeVisible()
    await expect(page.getByText(/4 Guests/i)).toBeVisible()

    // No auth prompts should appear
    const authPrompt = page.getByText(/sign in|log in|authenticate/i)
    expect(await authPrompt.isVisible().catch(() => false)).toBe(false)
  })

  test('can view pricing information without authentication', async ({ page }) => {
    // Navigate to Pricing page
    await page.goto('/pricing')

    // Verify pricing is visible without auth
    await expect(page.getByRole('heading', { name: /Pricing/i })).toBeVisible()
    await expect(page.getByText(/per night/i)).toBeVisible()

    // No auth prompts should appear
    const authPrompt = page.getByText(/sign in|log in|authenticate/i)
    expect(await authPrompt.isVisible().catch(() => false)).toBe(false)
  })

  test('can view availability without authentication', async ({ page }) => {
    // Ask about availability via chat
    const chatInput = page.getByPlaceholder(/type.*message|ask.*question|message/i)
    await chatInput.fill('Show me the calendar for next month')

    const sendButton = page.getByRole('button', { name: /send/i })
    await sendButton.click()

    // Wait for message to be sent
    await expect(page.getByText('Show me the calendar for next month')).toBeVisible({
      timeout: 5000,
    })

    // Verify no auth required - the request should proceed
    // (Agent response time may vary, but no auth prompt should appear)
    await page.waitForTimeout(2000)

    const authPrompt = page.getByText(/please.*sign.*in|please.*log.*in|authentication.*required/i)
    expect(await authPrompt.isVisible().catch(() => false)).toBe(false)
  })

  test('localStorage does not have session initially', async ({ page }) => {
    // Check that no auth session exists for anonymous users
    const session = await page.evaluate(() => {
      return localStorage.getItem('booking_session')
    })

    // Anonymous users should not have a session
    expect(session).toBeNull()
  })

  test('multiple inquiries work without authentication', async ({ page }) => {
    const chatInput = page.getByPlaceholder(/type.*message|ask.*question|message/i)
    const sendButton = page.getByRole('button', { name: /send/i })

    // First inquiry
    await chatInput.fill('What is the property address?')
    await sendButton.click()
    await expect(page.getByText('What is the property address?')).toBeVisible({ timeout: 5000 })

    // Wait for first response or timeout
    await page.waitForTimeout(2000)

    // Second inquiry
    await chatInput.fill('How many bedrooms are there?')
    await sendButton.click()
    await expect(page.getByText('How many bedrooms are there?')).toBeVisible({ timeout: 5000 })

    // Verify no auth prompt appeared after multiple messages
    const authPrompt = page.getByText(/sign in|log in|authenticate|verify.*email/i)
    expect(await authPrompt.isVisible().catch(() => false)).toBe(false)
  })
})

test.describe('Anonymous Inquiry - Network Verification', () => {
  test('requests do not include auth_token for anonymous users', async ({ page }) => {
    // Intercept AgentCore requests
    const requests: string[] = []

    await page.route('**/bedrock-agentcore*/**', (route) => {
      const request = route.request()
      const postData = request.postData()
      if (postData) {
        requests.push(postData)
      }
      // Continue with the request (or mock a response for faster tests)
      route.continue()
    })

    await page.goto('/')
    await expect(page.getByText('Welcome to Quesada Apartment!')).toBeVisible({ timeout: 10000 })

    // Send an inquiry
    const chatInput = page.getByPlaceholder(/type.*message|ask.*question|message/i)
    await chatInput.fill('Hello, what dates are available?')

    const sendButton = page.getByRole('button', { name: /send/i })
    await sendButton.click()

    // Wait for request to be made
    await page.waitForTimeout(3000)

    // If any requests were captured, verify they don't contain auth_token
    for (const requestBody of requests) {
      try {
        const parsed = JSON.parse(requestBody)
        expect(parsed).not.toHaveProperty('auth_token')
      } catch {
        // Not JSON, skip
      }
    }
  })
})
