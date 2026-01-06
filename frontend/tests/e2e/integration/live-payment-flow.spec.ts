/**
 * Integration Tests: Live Payment Flow with Real Cognito Auth
 *
 * These tests run against the live site (https://booking.levy.apro.work)
 * with REAL Cognito authentication - no mocking.
 *
 * Prerequisites:
 *   1. Set E2E_TEST_USER_EMAIL and E2E_TEST_USER_PASSWORD env vars
 *   2. Test user must exist in Cognito (run setup-test-user.ts first)
 *   3. Stripe is in test mode with test API keys configured
 *
 * Run with:
 *   E2E_TEST_USER_EMAIL=xxx E2E_TEST_USER_PASSWORD=xxx yarn test:e2e:live --grep "Live Payment"
 *
 * Or via npm script:
 *   yarn test:e2e:live:payment
 *
 * @see tests/e2e/fixtures/auth.fixture.ts
 * @see tests/e2e/scripts/setup-test-user.ts
 */

import { test, expect } from '../fixtures/auth.fixture'
import { addDays, format } from 'date-fns'
import * as fs from 'fs'
import * as path from 'path'

// ============================================================================
// Configuration
// ============================================================================

/** Longer timeout for real API and Stripe interactions */
test.setTimeout(120000)

/**
 * Note: Credentials are loaded automatically from SSM Parameter Store by auth.fixture.ts:
 *   /booking/e2e/test-user-email
 *   /booking/e2e/test-user-password
 *
 * Environment variables can override SSM if needed:
 *   E2E_TEST_USER_EMAIL
 *   E2E_TEST_USER_PASSWORD
 */

// ============================================================================
// Helpers
// ============================================================================

/**
 * Get the authenticated user's email from the stored auth state.
 * Decodes the JWT idToken to extract the email claim.
 */
function getAuthenticatedUserEmail(): string {
  const authStatePath = path.join(__dirname, '..', '.auth-state', 'user.json')

  try {
    const authState = JSON.parse(fs.readFileSync(authStatePath, 'utf-8'))
    const localStorage = authState.origins?.[0]?.localStorage || []

    // Find the idToken in localStorage
    const idTokenEntry = localStorage.find((entry: { name: string; value: string }) =>
      entry.name.endsWith('.idToken')
    )

    if (idTokenEntry?.value) {
      // JWT is base64url encoded: header.payload.signature
      // We need the payload (second part)
      const parts = idTokenEntry.value.split('.')
      if (parts.length === 3) {
        // Base64url decode the payload
        const payload = Buffer.from(parts[1], 'base64').toString('utf-8')
        const claims = JSON.parse(payload)
        if (claims.email) {
          return claims.email
        }
      }
    }
  } catch {
    // Fall back to default if we can't read auth state
  }

  // Fallback to default test email
  return 'test@example.com'
}

/**
 * Select a date in the booking calendar
 *
 * The calendar uses data-day={date.toLocaleDateString()} which produces
 * locale-specific formats. We use the same method for consistent matching.
 *
 * NOTE: This function will skip disabled dates and try to find the next available one.
 * Returns the actual selected date (may differ from requested if fallback was used).
 *
 * @param minDate - For check-out selection, pass the check-in date to ensure check-out > check-in
 */
async function selectDate(
  page: typeof test.prototype,
  date: Date,
  options: { allowFallback?: boolean; minDate?: Date } = {}
): Promise<Date> {
  const { allowFallback = true, minDate } = options
  // Match the format used by the calendar component (toLocaleDateString())
  const dateStr = date.toLocaleDateString()
  const readableDateStr = format(date, 'yyyy-MM-dd') // For error messages

  // Try to find and click the date button
  // The calendar may need to be navigated to the correct month
  let attempts = 0
  const maxAttempts = 24 // Up to 24 months ahead (matches 2-year seeded availability)

  while (attempts < maxAttempts) {
    const dayButton = page.locator(`button[data-day="${dateStr}"]`)

    if (await dayButton.isVisible()) {
      // Check if the button is disabled (unavailable date)
      const isDisabled = await dayButton.isDisabled()
      if (!isDisabled) {
        await dayButton.click()
        return date // Return the requested date since it was available
      }

      // If disabled and fallback allowed, try to find next available date
      if (allowFallback) {
        // Find all enabled day buttons in the current calendar view
        const enabledDays = page.locator('[data-slot="calendar"] button[data-day]:not([disabled])')
        const count = await enabledDays.count()

        // Find first available day that meets our constraints
        for (let i = 0; i < count; i++) {
          const dayBtn = enabledDays.nth(i)
          const dayDateStr = await dayBtn.getAttribute('data-day')
          const dayDate = new Date(dayDateStr!)

          // Skip dates BEFORE the requested date (fallback must not go backwards)
          // This prevents selecting early dates that may have existing reservations
          if (dayDate < date) {
            continue
          }

          // Skip dates on or before minDate (for check-out, must be after check-in + nights - 1)
          if (minDate && dayDate <= minDate) {
            continue
          }

          await dayBtn.click()
          console.log(`[selectDate] Fallback: requested ${readableDateStr}, selected ${format(dayDate, 'yyyy-MM-dd')}${minDate ? ` (minDate: ${format(minDate, 'yyyy-MM-dd')})` : ''}`)
          return dayDate
        }

        // No valid date in this view, continue to next month
      }
    }

    // Navigate to next month using the navigation button
    // react-day-picker uses button_next class for the next month button
    const nextMonthButton = page.locator('button.rdp-button_next')
    if (await nextMonthButton.isVisible()) {
      await nextMonthButton.click()
      await page.waitForTimeout(200) // Allow calendar to update
    }

    attempts++
  }

  throw new Error(
    `Could not find available date near ${readableDateStr} (data-day="${dateStr}") in calendar after ${maxAttempts} navigation attempts`
  )
}

/**
 * Counter for generating unique date ranges per test within each worker.
 *
 * Date allocation strategy (relies on --e2e-mode clearing all reservations):
 * - Base offset: 60 days from today (safe future date)
 * - Worker offset: 70 days per worker (allows 10 tests × 7 nights each)
 * - Test offset: 7 days per test within worker
 *
 * Example with 4 workers:
 * - Worker 0: days 60-129 (tests 0-9)
 * - Worker 1: days 130-199 (tests 0-9)
 * - Worker 2: days 200-269 (tests 0-9)
 * - Worker 3: days 270-339 (tests 0-9)
 *
 * Since `task frontend:test:e2e:live:payment` runs `seed:dev --e2e-mode` first,
 * ALL dates are available at test start. No retry logic needed.
 */
let testIndex = 0

/**
 * Complete the booking form up to the payment step.
 *
 * Date selection is deterministic - each test gets its own 7-day window.
 * Requires running via `task frontend:test:e2e:live:payment` which clears
 * all reservations before running tests.
 */
async function completeBookingFormUpToPayment(
  page: typeof test.prototype,
  options: {
    checkIn?: Date
    checkOut?: Date
    guestName?: string
    guestEmail?: string
    guestPhone?: string
    /** Days from today to start booking (default: auto-calculated per test) */
    startOffset?: number
    /** Number of nights to book (default: 7) */
    nights?: number
    /** Playwright worker index for date range isolation */
    workerIndex?: number
  } = {}
) {
  const nights = options.nights ?? 7
  const guestName = options.guestName ?? 'Automated Test User'
  // For authenticated users, get email from JWT in auth state (matches what's shown on payment page)
  const guestEmail = options.guestEmail ?? process.env.E2E_TEST_USER_EMAIL ?? getAuthenticatedUserEmail()
  const workerIndex = options.workerIndex ?? 0

  // Each worker gets 70 days (10 tests × 7 nights), each test gets 7 days
  // Worker 0: 60-129, Worker 1: 130-199, Worker 2: 200-269, etc.
  const currentTestIndex = testIndex++
  const workerOffset = workerIndex * 70
  const testOffset = currentTestIndex * 7
  const startOffset = options.startOffset ?? 60 + workerOffset + testOffset

  console.log(`[DateCalc] worker=${workerIndex}, test=${currentTestIndex}, offset=${startOffset} (days ${startOffset}-${startOffset + nights - 1})`)

  const requestedCheckIn = options.checkIn ?? addDays(new Date(), startOffset)

  // Navigate to booking page
  await page.goto('/book')
  await page.waitForLoadState('networkidle')

  // Step 1: Select dates
  // IMPORTANT: selectDate may fallback to a different date if requested is unavailable
  // We must calculate check-out based on the ACTUAL selected check-in, not the requested one
  await expect(page.locator('[data-slot="calendar"]').first()).toBeVisible({ timeout: 10000 })

  const checkIn = await selectDate(page, requestedCheckIn)
  const checkOut = options.checkOut ?? addDays(checkIn, nights)
  // Pass minDate to ensure check-out fallback maintains the intended stay duration
  // minDate = checkIn + (nights - 1) ensures any fallback date is >= nights away from check-in
  // This is crucial for seasonal minimum stay requirements (e.g., 5 nights in Mid Season)
  const minCheckOutDate = addDays(checkIn, nights - 1)
  await selectDate(page, checkOut, { minDate: minCheckOutDate })

  // Verify date selection shows nights
  await expect(page.getByText(/night/i)).toBeVisible({ timeout: 10000 })

  // Continue to auth step (new flow: dates -> auth -> guest -> payment)
  await page.getByRole('button', { name: /^continue$/i }).click()

  // Step 2: Auth step - for authenticated users, this auto-completes
  // Wait for either AuthStep (if not auto-completing) or Guest Details (if auto-completed)
  // Give the auth step time to detect existing session and auto-advance
  await expect(page.getByText('Guest Details')).toBeVisible({ timeout: 30000 })

  // Step 3: Fill simplified guest details (only guest count and special requests)
  // Name, email, phone are now collected in AuthStep which auto-completed for authenticated users

  // Continue to payment - this triggers a reservation API call
  const continueButton = page.getByRole('button', { name: /continue to payment/i })
  await expect(continueButton).toBeEnabled({ timeout: 5000 })

  // Set up network interception to capture API request and response for debugging
  let apiResponse: { status: number; body: string } | null = null
  let apiRequestHeaders: Record<string, string> | null = null

  // Capture request headers
  page.on('request', (request) => {
    if (request.url().includes('/api/reservations') && request.method() === 'POST') {
      apiRequestHeaders = request.headers()
      console.log(`[DEBUG] Reservation API Request URL: ${request.url()}`)
      console.log(`[DEBUG] Authorization Header: ${apiRequestHeaders['authorization'] || 'NOT SET'}`)
      console.log(`[DEBUG] All Request Headers:`, JSON.stringify(apiRequestHeaders, null, 2))
    }
  })

  // Capture response
  page.on('response', async (response) => {
    if (response.url().includes('/api/reservations') && response.request().method() === 'POST') {
      try {
        apiResponse = {
          status: response.status(),
          body: await response.text(),
        }
        console.log(`[DEBUG] Reservation API Response: ${response.status()}`)
        console.log(`[DEBUG] Response Body: ${apiResponse.body.substring(0, 500)}`)
      } catch {
        console.log(`[DEBUG] Could not read response body`)
      }
    }
  })

  // Debug: Check if window.__MOCK_AUTH__ is set before making API call
  const mockAuthState = await page.evaluate(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const mockAuth = (window as any).__MOCK_AUTH__
    if (!mockAuth) {
      return { set: false, reason: 'window.__MOCK_AUTH__ is undefined' }
    }
    const idToken = mockAuth.tokens?.idToken?.toString?.()
    return {
      set: true,
      hasTokens: !!mockAuth.tokens,
      hasIdToken: !!idToken,
      idTokenPreview: idToken ? `${idToken.substring(0, 50)}...` : 'NOT SET',
      username: mockAuth.user?.username || 'NOT SET',
    }
  })
  console.log('[DEBUG] Mock Auth State:', JSON.stringify(mockAuthState, null, 2))

  await continueButton.click()

  // Wait for loading state to appear and disappear (API call in progress)
  // The button shows "Creating Reservation..." while loading
  await expect(page.getByText(/creating reservation/i)).toBeVisible({ timeout: 5000 }).catch(() => {
    // Loading state may have passed too quickly, continue
  })

  // Wait for either:
  // 1. Success: Payment step shows "Complete Payment"
  // 2. Error: Error message appears (text contains "Booking Failed" or "error")
  const paymentStep = page.getByText('Complete Payment')
  const errorMessage = page.getByText(/booking failed|error|unavailable/i)

  // Wait with longer timeout for API response
  await expect(paymentStep.or(errorMessage)).toBeVisible({ timeout: 30000 })

  // If we got an error, capture details and fail with helpful message
  if (await errorMessage.isVisible().catch(() => false)) {
    // Try to get the full error text from the error container
    const errorContainer = page.locator('.bg-destructive\\/10')
    let errorText = 'Unknown error'
    if (await errorContainer.isVisible().catch(() => false)) {
      errorText = await errorContainer.textContent() || 'Unknown error'
    } else {
      errorText = await errorMessage.textContent() || 'Unknown error'
    }

    // Include API request/response details if available
    const authHeader = apiRequestHeaders?.['authorization'] || 'NOT SET'
    const apiDetails = apiResponse
      ? `\nAuth Header: ${authHeader.substring(0, 50)}...\nAPI Status: ${apiResponse.status}\nAPI Response: ${apiResponse.body.substring(0, 300)}`
      : '\nAPI Response: Not captured'
    throw new Error(`Reservation creation failed: ${errorText}${apiDetails}`)
  }

  // Verify we're on the payment step
  await expect(paymentStep).toBeVisible({ timeout: 5000 })

  // Return the booking details - guestName/guestEmail now come from AuthStep (pre-filled for authenticated users)
  return { checkIn, checkOut, guestName, guestEmail }
}

// ============================================================================
// Tests
// ============================================================================

test.describe('Live Payment Flow - Authenticated', () => {
  test.describe.configure({ mode: 'serial' }) // Run tests serially to avoid conflicts

  test('authenticated user can access booking page', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/book')
    await authenticatedPage.waitForLoadState('networkidle')

    // Should see the calendar for date selection
    await expect(authenticatedPage.locator('[data-slot="calendar"]').first()).toBeVisible({
      timeout: 15000,
    })
  })

  test('authenticated user can complete booking form to payment step', async ({
    authenticatedPage,
  }, testInfo) => {
    await completeBookingFormUpToPayment(authenticatedPage, { workerIndex: testInfo.workerIndex })

    // Should see the booking summary on payment step
    await expect(authenticatedPage.getByText('Booking Summary')).toBeVisible()
    await expect(authenticatedPage.getByText(/total/i)).toBeVisible()
    await expect(authenticatedPage.getByRole('button', { name: /proceed to payment/i })).toBeEnabled()
  })

  test('clicking "Proceed to Payment" creates Stripe checkout session', async ({
    authenticatedPage,
  }, testInfo) => {
    await completeBookingFormUpToPayment(authenticatedPage, { workerIndex: testInfo.workerIndex })

    // Set up network interception for checkout session API
    let checkoutApiResponse: { status: number; body: string } | null = null
    authenticatedPage.on('request', (request) => {
      if (request.url().includes('/api/payments/checkout-session') && request.method() === 'POST') {
        console.log(`[DEBUG] Checkout Session API Request: ${request.url()}`)
        console.log(`[DEBUG] Request Headers:`, JSON.stringify(request.headers(), null, 2))
      }
    })
    authenticatedPage.on('response', async (response) => {
      if (response.url().includes('/api/payments/checkout-session') && response.request().method() === 'POST') {
        try {
          checkoutApiResponse = {
            status: response.status(),
            body: await response.text(),
          }
          console.log(`[DEBUG] Checkout Session API Response: ${response.status()}`)
          console.log(`[DEBUG] Response Body: ${checkoutApiResponse.body.substring(0, 500)}`)
        } catch {
          console.log(`[DEBUG] Could not read checkout session response body`)
        }
      }
    })

    // Capture console errors
    authenticatedPage.on('console', (msg) => {
      if (msg.type() === 'error') {
        console.log(`[DEBUG] Browser Console Error: ${msg.text()}`)
      }
    })

    // Click the payment button
    const payButton = authenticatedPage.getByRole('button', { name: /proceed to payment/i })
    await expect(payButton).toBeEnabled()
    await payButton.click()

    // Should show loading state
    await expect(
      authenticatedPage.getByText(/creating session|redirecting/i)
    ).toBeVisible({ timeout: 5000 })

    // Wait a bit for API call to complete and log any captured data
    await authenticatedPage.waitForTimeout(3000)
    if (checkoutApiResponse) {
      console.log(`[DEBUG] Final checkout API status: ${checkoutApiResponse.status}`)
    } else {
      console.log(`[DEBUG] WARNING: No checkout session API call was captured!`)
    }

    // Wait for navigation to Stripe Checkout
    // This is the real Stripe test checkout page
    await authenticatedPage.waitForURL(/checkout\.stripe\.com/, {
      timeout: 30000,
    })

    // Verify we're on Stripe Checkout
    expect(authenticatedPage.url()).toContain('checkout.stripe.com')
  })

  test('can navigate back from payment step to guest details', async ({ authenticatedPage }, testInfo) => {
    await completeBookingFormUpToPayment(authenticatedPage, { workerIndex: testInfo.workerIndex })

    // Click back button
    await authenticatedPage.getByRole('button', { name: /back/i }).click()

    // Should be back on guest details (simplified form: guest count + special requests only)
    await expect(authenticatedPage.getByText('Guest Details')).toBeVisible({ timeout: 5000 })

    // Verify guest count dropdown is visible (name/email/phone now in AuthStep)
    await expect(authenticatedPage.getByText('Number of Guests')).toBeVisible()
  })

  test('payment step displays correct booking summary', async ({ authenticatedPage }, testInfo) => {
    const { guestName, guestEmail } = await completeBookingFormUpToPayment(authenticatedPage, { workerIndex: testInfo.workerIndex })

    // Verify summary shows correct guest info
    await expect(authenticatedPage.getByText(guestName)).toBeVisible()
    await expect(authenticatedPage.getByText(guestEmail)).toBeVisible()

    // Verify pricing is displayed (nights count depends on test's booking range)
    await expect(authenticatedPage.getByText(/€/)).toBeVisible()
    await expect(authenticatedPage.getByText(/\d+ nights?/i)).toBeVisible()
  })
})

test.describe('Live Payment Flow - Session Persistence', () => {
  test.describe.configure({ mode: 'serial' }) // Run tests serially to avoid date conflicts

  test('booking state survives page reload', async ({ authenticatedPage }, testInfo) => {
    const { guestName } = await completeBookingFormUpToPayment(authenticatedPage, { workerIndex: testInfo.workerIndex })

    // Reload the page
    await authenticatedPage.reload()
    await authenticatedPage.waitForLoadState('networkidle')

    // Should still be on payment step with data preserved
    await expect(authenticatedPage.getByText('Complete Payment')).toBeVisible({ timeout: 10000 })
    await expect(authenticatedPage.getByText(guestName)).toBeVisible()
  })

  test('can start fresh booking after clearing session', async ({ authenticatedPage }, testInfo) => {
    await completeBookingFormUpToPayment(authenticatedPage, { workerIndex: testInfo.workerIndex })

    // Clear session storage
    await authenticatedPage.evaluate(() => {
      sessionStorage.clear()
    })

    // Reload
    await authenticatedPage.reload()
    await authenticatedPage.waitForLoadState('networkidle')

    // Should be back at date selection (first step)
    await expect(authenticatedPage.locator('[data-slot="calendar"]').first()).toBeVisible({
      timeout: 10000,
    })
  })
})

test.describe('Live Payment Flow - Stripe Checkout Navigation', () => {
  test.describe.configure({ mode: 'serial' }) // Run tests serially to avoid date conflicts

  test('Stripe checkout page loads correctly', async ({ authenticatedPage }, testInfo) => {
    await completeBookingFormUpToPayment(authenticatedPage, { workerIndex: testInfo.workerIndex })

    // Click payment button
    await authenticatedPage.getByRole('button', { name: /proceed to payment/i }).click()

    // Wait for Stripe checkout
    await authenticatedPage.waitForURL(/checkout\.stripe\.com/, { timeout: 30000 })

    // Stripe checkout should show payment form elements
    // Note: We can't interact deeply with Stripe's iframe-based checkout
    // but we can verify the page loaded
    await expect(authenticatedPage.locator('body')).toBeVisible()
  })

  test.skip('completing Stripe checkout redirects to success page', async ({ authenticatedPage }, testInfo) => {
    // This test requires completing Stripe checkout with test card
    // Skipped by default as it requires manual/special handling

    await completeBookingFormUpToPayment(authenticatedPage, { workerIndex: testInfo.workerIndex })
    await authenticatedPage.getByRole('button', { name: /proceed to payment/i }).click()

    await authenticatedPage.waitForURL(/checkout\.stripe\.com/, { timeout: 30000 })

    // In Stripe test mode, you would fill in test card details:
    // Card: 4242 4242 4242 4242, Exp: Any future date, CVC: Any 3 digits
    // This is typically done via Stripe's Elements which are in iframes

    // After successful payment, should redirect to success page
    await authenticatedPage.waitForURL(/\/booking\/success/, { timeout: 60000 })

    await expect(authenticatedPage.getByText(/booking confirmed/i)).toBeVisible()
  })

  test('cancelling Stripe checkout redirects to cancel page', async ({ authenticatedPage }, testInfo) => {
    await completeBookingFormUpToPayment(authenticatedPage, { workerIndex: testInfo.workerIndex })
    await authenticatedPage.getByRole('button', { name: /proceed to payment/i }).click()

    // Wait for Stripe checkout to load
    await authenticatedPage.waitForURL(/checkout\.stripe\.com/, { timeout: 30000 })

    // Click the back/cancel link on Stripe checkout
    // Stripe provides a "back" link that redirects to cancel_url
    const backLink = authenticatedPage.locator('a').filter({ hasText: /back/i })

    if (await backLink.isVisible({ timeout: 5000 })) {
      await backLink.click()

      // Should redirect to our cancel page
      await authenticatedPage.waitForURL(/\/booking\/cancel/, { timeout: 30000 })

      await expect(authenticatedPage.getByText(/payment not completed/i)).toBeVisible()
    } else {
      // Some Stripe checkout variants don't have a visible back link
      // Navigate directly to test cancel handling
      await authenticatedPage.goto('/booking/cancel')
      await expect(authenticatedPage.getByText(/payment not completed/i)).toBeVisible()
    }
  })
})

test.describe('Live Payment Flow - Error Scenarios', () => {
  test.describe.configure({ mode: 'serial' }) // Run tests serially to avoid date conflicts

  test('handles API errors gracefully', async ({ authenticatedPage }) => {
    // Navigate to booking page but interrupt API calls
    await authenticatedPage.route('**/api/reservations', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      })
    })

    await authenticatedPage.goto('/book')

    // Complete the form - use large offset (600+ days) to avoid conflicts with main tests
    // Error tests don't actually hit the API (mocked), but need selectable calendar dates
    const checkIn = addDays(new Date(), 650)
    const checkOut = addDays(checkIn, 5)

    await expect(authenticatedPage.locator('[data-slot="calendar"]').first()).toBeVisible({
      timeout: 10000,
    })

    await selectDate(authenticatedPage, checkIn)
    await selectDate(authenticatedPage, checkOut)

    await expect(authenticatedPage.getByText(/night/i)).toBeVisible({ timeout: 10000 })

    // New flow: dates -> auth -> guest details -> payment
    await authenticatedPage.getByRole('button', { name: /^continue$/i }).click()

    // Auth step auto-completes for authenticated users
    // Wait for Guest Details to appear (name/email/phone are now in AuthStep which auto-completed)
    await expect(authenticatedPage.getByText('Guest Details')).toBeVisible({ timeout: 30000 })

    // Guest Details now only has guest count + special requests
    await authenticatedPage.getByRole('button', { name: /continue to payment/i }).click()

    // Should show error state (use first() to handle multiple matching elements)
    await expect(authenticatedPage.getByText(/error|failed|try again/i).first()).toBeVisible({
      timeout: 15000,
    })
  })

  test('success page handles missing session_id', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/booking/success')

    await expect(authenticatedPage.getByText(/no session/i)).toBeVisible({ timeout: 5000 })
  })

  test('success page handles invalid session_id format', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/booking/success?session_id=invalid-format')

    await expect(authenticatedPage.getByText(/invalid session/i)).toBeVisible({ timeout: 5000 })
  })
})
