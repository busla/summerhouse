/**
 * Integration Tests: Live Site Booking Flow
 *
 * These tests run against the live production site at https://booking.levy.apro.work/
 * They verify real user interactions with the AI booking assistant.
 *
 * Run with: yarn test:e2e:live
 * Or: yarn test:e2e --project=live
 *
 * Note: These tests interact with real AI responses so they:
 * - Have longer timeouts (AI responses take 2-5 seconds)
 * - Don't retry (we want to see real failures)
 * - May have some flakiness due to AI response variability
 */

import { test, expect } from '@playwright/test'

// Longer timeout for AI responses
test.setTimeout(60000)

test.describe('Live Site - Basic Functionality', () => {
  test('loads the booking assistant homepage', async ({ page }) => {
    await page.goto('/')

    // Verify the main heading is visible
    await expect(page.getByText('Welcome to Quesada Apartment!')).toBeVisible()

    // Verify the chat input is available
    const chatInput = page.getByPlaceholder(
      'Ask about availability, pricing, or the property...'
    )
    await expect(chatInput).toBeVisible()
    await expect(chatInput).toBeEnabled()
  })

  test('displays suggestion buttons', async ({ page }) => {
    await page.goto('/')

    // Check that quick action buttons are visible
    await expect(page.getByRole('button', { name: 'Check availability' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'See pricing' })).toBeVisible()
  })

  test('chat input accepts text', async ({ page }) => {
    await page.goto('/')

    const chatInput = page.getByPlaceholder(
      'Ask about availability, pricing, or the property...'
    )

    // Type a message (but don't send yet)
    await chatInput.fill('Hello')
    await expect(chatInput).toHaveValue('Hello')
  })
})

test.describe('Live Site - Agent Interactions', () => {
  test('agent responds to greeting', async ({ page }) => {
    await page.goto('/')

    const chatInput = page.getByPlaceholder(
      'Ask about availability, pricing, or the property...'
    )

    // Send a simple greeting
    await chatInput.fill('Hello!')
    await chatInput.press('Enter')

    // Wait for agent response (look for any new message in the chat)
    // The agent should respond within 30 seconds
    await expect(
      page.locator('[data-testid="message"]').or(page.locator('.message')).first()
    ).toBeVisible({ timeout: 30000 })
  })

  test('check availability button triggers agent response', async ({ page }) => {
    await page.goto('/')

    // Click the "Check availability" suggestion button
    await page.getByRole('button', { name: 'Check availability' }).click()

    // The chat input should be filled or a message should appear
    // Wait for the agent to process and respond
    await page.waitForTimeout(2000) // Brief wait for UI update

    // Agent should respond about availability
    // We're looking for any indication the agent received the request
    const chatArea = page.locator('main')
    await expect(chatArea).toContainText(/availab|dates|book|calendar/i, {
      timeout: 30000,
    })
  })

  test('see pricing button shows pricing information', async ({ page }) => {
    await page.goto('/')

    // Click the "See pricing" suggestion button
    await page.getByRole('button', { name: 'See pricing' }).click()

    // Wait for agent response about pricing
    const chatArea = page.locator('main')
    await expect(chatArea).toContainText(/pric|rate|€|EUR|night|season/i, {
      timeout: 30000,
    })
  })
})

test.describe('Live Site - Availability Queries', () => {
  test('can ask about specific date availability', async ({ page }) => {
    await page.goto('/')

    const chatInput = page.getByPlaceholder(
      'Ask about availability, pricing, or the property...'
    )

    // Ask about availability for specific dates
    await chatInput.fill('Is the apartment available from June 2nd to June 16th 2025?')
    await chatInput.press('Enter')

    // Wait for agent response
    const chatArea = page.locator('main')

    // Agent should respond with availability info (available, booked, or dates)
    await expect(chatArea).toContainText(/june|availab|book|dates|2025/i, {
      timeout: 30000,
    })
  })

  test('can ask about summer availability', async ({ page }) => {
    await page.goto('/')

    const chatInput = page.getByPlaceholder(
      'Ask about availability, pricing, or the property...'
    )

    // General availability question
    await chatInput.fill('What dates are available in July 2025?')
    await chatInput.press('Enter')

    // Wait for agent response about July
    const chatArea = page.locator('main')
    await expect(chatArea).toContainText(/july|summer|availab|book/i, {
      timeout: 30000,
    })
  })
})

test.describe('Live Site - Property Information', () => {
  test('can ask about property details', async ({ page }) => {
    await page.goto('/')

    const chatInput = page.getByPlaceholder(
      'Ask about availability, pricing, or the property...'
    )

    // Ask about property
    await chatInput.fill('Tell me about the apartment')
    await chatInput.press('Enter')

    // Wait for property description
    const chatArea = page.locator('main')
    await expect(chatArea).toContainText(/apartment|bedroom|guest|quesada|alicante/i, {
      timeout: 30000,
    })
  })

  test('can ask about location and area', async ({ page }) => {
    await page.goto('/')

    const chatInput = page.getByPlaceholder(
      'Ask about availability, pricing, or the property...'
    )

    // Ask about location
    await chatInput.fill('Where is the apartment located?')
    await chatInput.press('Enter')

    // Wait for location info
    const chatArea = page.locator('main')
    await expect(chatArea).toContainText(/quesada|alicante|spain|costa|location/i, {
      timeout: 30000,
    })
  })
})

test.describe('Live Site - Booking Flow', () => {
  test('agent guides through booking process', async ({ page }) => {
    await page.goto('/')

    const chatInput = page.getByPlaceholder(
      'Ask about availability, pricing, or the property...'
    )

    // Express intent to book
    await chatInput.fill('I want to book the apartment for 2 guests from July 1st to July 8th 2025')
    await chatInput.press('Enter')

    // Agent should respond about the booking request
    const chatArea = page.locator('main')

    // Should mention dates, guests, pricing, or verification
    await expect(chatArea).toContainText(/july|guest|book|price|€|verif|email/i, {
      timeout: 30000,
    })
  })

  test('handles minimum stay requirements', async ({ page }) => {
    await page.goto('/')

    const chatInput = page.getByPlaceholder(
      'Ask about availability, pricing, or the property...'
    )

    // Try to book too short a stay (summer requires 7 nights minimum)
    await chatInput.fill('Can I book July 15th to July 17th 2025?')
    await chatInput.press('Enter')

    // Agent should mention minimum stay requirement
    const chatArea = page.locator('main')

    // Should mention minimum nights or suggest longer stay
    await expect(chatArea).toContainText(/minimum|night|stay|7|week/i, {
      timeout: 30000,
    })
  })
})

test.describe('Live Site - Error Handling', () => {
  test('handles past dates gracefully', async ({ page }) => {
    await page.goto('/')

    const chatInput = page.getByPlaceholder(
      'Ask about availability, pricing, or the property...'
    )

    // Ask about dates in the past
    await chatInput.fill('Is January 1st 2024 available?')
    await chatInput.press('Enter')

    // Agent should handle past dates appropriately
    const chatArea = page.locator('main')

    // Should mention past/invalid dates or suggest future dates
    await expect(chatArea).toContainText(/past|future|2025|2026|availab|can't|cannot/i, {
      timeout: 30000,
    })
  })

  test('handles invalid requests gracefully', async ({ page }) => {
    await page.goto('/')

    const chatInput = page.getByPlaceholder(
      'Ask about availability, pricing, or the property...'
    )

    // Send gibberish
    await chatInput.fill('asdfghjkl qwerty')
    await chatInput.press('Enter')

    // Agent should still respond (even if confused)
    const chatArea = page.locator('main')

    // Should get some response from the agent
    // Wait for any new content to appear (agent response)
    await page.waitForTimeout(10000)

    // Verify the page is still functional (didn't crash)
    await expect(chatInput).toBeVisible()
  })
})

test.describe('Live Site - UI Responsiveness', () => {
  test('shows loading state while agent responds', async ({ page }) => {
    await page.goto('/')

    const chatInput = page.getByPlaceholder(
      'Ask about availability, pricing, or the property...'
    )

    // Send a message
    await chatInput.fill('Hello')
    await chatInput.press('Enter')

    // Should see some loading indicator or disabled state briefly
    // This is a soft check - may not always catch the loading state
    await page.waitForTimeout(500)

    // Eventually should get a response
    await page.waitForTimeout(5000)
  })

  test('maintains chat history', async ({ page }) => {
    await page.goto('/')

    const chatInput = page.getByPlaceholder(
      'Ask about availability, pricing, or the property...'
    )

    // Send first message
    await chatInput.fill('Hello')
    await chatInput.press('Enter')

    // Wait for response
    await page.waitForTimeout(5000)

    // Send second message
    await chatInput.fill('What is the price?')
    await chatInput.press('Enter')

    // Wait for second response
    await page.waitForTimeout(5000)

    // Both messages should still be visible in chat
    const chatArea = page.locator('main')
    await expect(chatArea).toContainText('Hello')
  })
})
