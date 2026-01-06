/**
 * E2E Test: Payment Flow (Stripe Checkout Integration)
 *
 * Tests the complete payment flow with Stripe Checkout:
 * 1. Complete booking form → Payment step
 * 2. Redirect to Stripe Checkout (mocked URL)
 * 3. Return to success/cancel page
 *
 * @see specs/014-stripe-checkout-frontend/spec.md - FR-022 to FR-026
 *
 * Note: Uses mocked Stripe redirects for CI reliability. For full E2E with
 * real Stripe test pages, use the integration test suite.
 */

import { test, expect, Page } from '@playwright/test'
import { addDays, format } from 'date-fns'

// === Test Fixtures ===

const TEST_GUEST = {
  name: 'Payment Test User',
  email: 'payment.test@example.com',
  phone: '+34 612 345 678',
  guestCount: 2,
}

const MOCK_RESERVATION_ID = 'RES-2025-PAY123'
const MOCK_SESSION_ID = 'cs_test_mockSessionId123'
const MOCK_CHECKOUT_URL = 'https://checkout.stripe.com/c/pay/cs_test_mock'

/**
 * Helper to select a date in the shadcn calendar.
 */
async function selectDate(page: Page, date: Date) {
  const dateStr = date.toLocaleDateString()
  const dayButton = page.locator(`button[data-day="${dateStr}"]`)

  let attempts = 0
  while (!(await dayButton.isVisible()) && attempts < 3) {
    await page.getByRole('button', { name: /next month/i }).click()
    await page.waitForTimeout(100)
    attempts++
  }

  await dayButton.click()
}

/**
 * Helper to complete booking form up to payment step.
 * Pre-populates form state to start at guest step directly, bypassing date selection and auth.
 *
 * Note: Auth step is tested separately in auth-step.spec.ts.
 * This helper focuses on testing the payment flow from guest details onward.
 *
 * Flow: (Pre-populated to Guest step) → Guest Details form → Payment
 */
async function completeBookingFormToPayment(page: Page) {
  const checkIn = addDays(new Date(), 14)
  const checkOut = addDays(checkIn, 3)

  // Pre-populate form state directly at 'guest' step with all required data
  // This bypasses the date and auth steps entirely for reliable payment flow testing
  // IMPORTANT: Only set if no existing state (allows persistence tests to work after reload)
  await page.addInitScript(
    ({ name, email, phone, checkInStr, checkOutStr }) => {
      // Check if state already exists (from previous navigation in same test)
      const existingState = sessionStorage.getItem('booking-form-state')
      if (!existingState) {
        const formState = {
          currentStep: 'guest', // Start directly at guest step
          selectedRange: {
            from: checkInStr,
            to: checkOutStr,
          },
          // Auth fields (pre-filled as if user completed auth)
          customerName: name,
          customerEmail: email,
          customerPhone: phone,
          authStep: 'authenticated',
          customerId: 'cust-test-123',
          // Guest details (null - will be filled in guest step)
          guestDetails: null,
          // Payment fields
          reservationId: null,
          paymentAttempts: 0,
          lastPaymentError: null,
          stripeSessionId: null,
        }
        sessionStorage.setItem('booking-form-state', JSON.stringify(formState))
      }

      // @ts-expect-error - global mock for E2E tests
      window.__MOCK_AUTH__ = {
        tokens: {
          idToken: { toString: () => 'mock-id-token-for-e2e-test' },
        },
      }
    },
    {
      name: TEST_GUEST.name,
      email: TEST_GUEST.email,
      phone: TEST_GUEST.phone,
      checkInStr: checkIn.toISOString(),
      checkOutStr: checkOut.toISOString(),
    }
  )

  // Mock customer profile API
  await page.route('**/api/customers/me', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          customer_id: 'cust-test-123',
          email: TEST_GUEST.email,
          name: TEST_GUEST.name,
          phone: TEST_GUEST.phone,
        }),
      })
    } else {
      await route.continue()
    }
  })

  // Mock reservation creation API
  await page.route('**/api/reservations', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          reservation_id: MOCK_RESERVATION_ID,
          check_in: format(checkIn, 'yyyy-MM-dd'),
          check_out: format(checkOut, 'yyyy-MM-dd'),
          num_adults: TEST_GUEST.guestCount,
          num_children: 0,
          nights: 3,
          nightly_rate: 12000,
          cleaning_fee: 5000,
          total_amount: 41000,
          status: 'pending_payment',
        }),
      })
    } else {
      await route.continue()
    }
  })

  await page.goto('/book')

  // Should start directly at Guest Details step (from pre-populated state)
  await expect(page.getByText('Guest Details')).toBeVisible({ timeout: 10000 })

  // Guest count select (default is 2, which matches TEST_GUEST.guestCount)
  await page.getByRole('button', { name: /continue to payment/i }).click()
}

// === Payment Step Display Tests ===

test.describe('Payment Step - Display', () => {
  test.beforeEach(async ({ page }) => {
    await completeBookingFormToPayment(page)
  })

  test('displays payment step with booking summary', async ({ page }) => {
    // Should show payment step header
    await expect(page.getByText('Complete Payment')).toBeVisible()

    // Should show booking summary
    await expect(page.getByText('Booking Summary')).toBeVisible()
    await expect(page.getByText(TEST_GUEST.name)).toBeVisible()

    // Should show total amount
    await expect(page.getByText(/total/i)).toBeVisible()
  })

  test('shows proceed to payment button', async ({ page }) => {
    const payButton = page.getByRole('button', { name: /proceed to payment/i })
    await expect(payButton).toBeVisible()
    await expect(payButton).toBeEnabled()
  })

  test('shows back button to return to guest details', async ({ page }) => {
    const backButton = page.getByRole('button', { name: /back/i })
    await expect(backButton).toBeVisible()

    await backButton.click()

    // Should be back on guest details (simplified form - only guest count + special requests)
    await expect(page.getByText('Guest Details')).toBeVisible()
    // Guest count selector should be visible
    await expect(page.getByText(/number of guests/i)).toBeVisible()
  })

  test('displays info about Stripe redirect', async ({ page }) => {
    // Should show info text about Stripe redirect
    await expect(page.getByText(/stripe/i)).toBeVisible()
    await expect(page.getByText(/secure checkout/i)).toBeVisible()
  })
})

// === Checkout Session Creation Tests ===

test.describe('Payment Step - Checkout Session', () => {
  test('creates checkout session and redirects to Stripe', async ({ page }) => {
    // Track if checkout session API was called with correct data
    let checkoutSessionCalled = false
    let requestBody: { reservation_id?: string } | null = null

    // Mock checkout session API
    await page.route('**/api/payments/checkout-session', async (route) => {
      if (route.request().method() === 'POST') {
        checkoutSessionCalled = true
        requestBody = route.request().postDataJSON()
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            checkout_url: MOCK_CHECKOUT_URL,
            session_id: MOCK_SESSION_ID,
            reservation_id: MOCK_RESERVATION_ID,
            expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
          }),
        })
      } else {
        await route.continue()
      }
    })

    await completeBookingFormToPayment(page)

    // Wait for payment step
    await expect(page.getByText('Complete Payment')).toBeVisible()

    // Set up navigation listener to verify redirect URL
    const navigationPromise = page.waitForURL(/checkout\.stripe\.com/, {
      timeout: 10000,
      waitUntil: 'commit', // Don't wait for full load - mock URL won't load
    })

    // Click proceed to payment
    await page.getByRole('button', { name: /proceed to payment/i }).click()

    // Wait for navigation to Stripe URL (proves redirect happened)
    // Using try/catch because the page won't fully load (mock URL)
    try {
      await navigationPromise
    } catch {
      // Navigation started but mock URL won't load - that's expected
    }

    // Verify the API was called correctly
    expect(checkoutSessionCalled).toBe(true)
    expect(requestBody?.reservation_id).toBe(MOCK_RESERVATION_ID)

    // Verify we navigated to Stripe (URL starts with mock checkout URL)
    expect(page.url()).toContain('checkout.stripe.com')
  })

  test('shows loading state during session creation', async ({ page }) => {
    // Mock slow checkout session API
    await page.route('**/api/payments/checkout-session', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1000)) // 1s delay
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          checkout_url: MOCK_CHECKOUT_URL,
          session_id: MOCK_SESSION_ID,
          reservation_id: MOCK_RESERVATION_ID,
          expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
        }),
      })
    })

    await completeBookingFormToPayment(page)

    await expect(page.getByText('Complete Payment')).toBeVisible()

    // Click proceed to payment
    await page.getByRole('button', { name: /proceed to payment/i }).click()

    // Should show loading state
    await expect(page.getByText(/creating session/i)).toBeVisible()
  })

  test('handles checkout session API error', async ({ page }) => {
    // Mock checkout session API error
    await page.route('**/api/payments/checkout-session', async (route) => {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({
          error_code: 'RESERVATION_NOT_FOUND',
          message: 'Reservation not found or already paid',
        }),
      })
    })

    await completeBookingFormToPayment(page)

    await expect(page.getByText('Complete Payment')).toBeVisible()

    // Click proceed to payment
    await page.getByRole('button', { name: /proceed to payment/i }).click()

    // Should show error message
    await expect(page.getByText(/not found|already paid|error/i)).toBeVisible({ timeout: 5000 })

    // Should still be on payment step (can retry)
    await expect(page.getByRole('button', { name: /proceed to payment/i })).toBeVisible()
  })
})

// === Success Page Tests ===

test.describe('Payment Success Page', () => {
  test('displays success confirmation with valid session', async ({ page }) => {
    // First set up form state in sessionStorage
    await page.addInitScript(
      ({ reservationId, sessionId }) => {
        const formState = {
          currentStep: 'payment',
          selectedRange: {
            from: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
            to: new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString(),
          },
          guestDetails: {
            name: 'Test User',
            email: 'test@example.com',
            phone: '+34 600 000 000',
            guestCount: 2,
          },
          reservationId: reservationId,
          paymentAttempts: 0,
          lastPaymentError: null,
          stripeSessionId: sessionId,
        }
        sessionStorage.setItem('booking-form-state', JSON.stringify(formState))
      },
      { reservationId: MOCK_RESERVATION_ID, sessionId: MOCK_SESSION_ID }
    )

    // Mock auth
    await page.addInitScript(() => {
      // @ts-expect-error - global mock for E2E tests
      window.__MOCK_AUTH__ = {
        tokens: { idToken: { toString: () => 'mock-id-token' } },
      }
    })

    // Mock payment status API
    await page.route(`**/api/payments/${MOCK_RESERVATION_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          payment_id: 'PAY-123',
          reservation_id: MOCK_RESERVATION_ID,
          amount: 41000,
          currency: 'EUR',
          status: 'completed',
          provider: 'stripe',
          created_at: new Date().toISOString(),
        }),
      })
    })

    // Navigate to success page with session_id
    await page.goto(`/booking/success?session_id=${MOCK_SESSION_ID}`)

    // Should show success message
    await expect(page.getByText(/booking confirmed/i)).toBeVisible({ timeout: 10000 })

    // Should show reservation ID
    await expect(page.getByText(MOCK_RESERVATION_ID)).toBeVisible()

    // Should show paid status badge
    await expect(page.getByText('Paid', { exact: true })).toBeVisible()
  })

  test('shows error for invalid session_id format', async ({ page }) => {
    await page.goto('/booking/success?session_id=invalid')

    await expect(page.getByText(/invalid session/i)).toBeVisible({ timeout: 5000 })
  })

  test('shows error when no session_id provided', async ({ page }) => {
    await page.goto('/booking/success')

    await expect(page.getByText(/no session/i)).toBeVisible({ timeout: 5000 })
  })

  test('shows error when no booking found in storage', async ({ page }) => {
    // Clear any existing storage
    await page.addInitScript(() => {
      sessionStorage.clear()
    })

    await page.goto(`/booking/success?session_id=${MOCK_SESSION_ID}`)

    await expect(page.getByText(/no booking found/i)).toBeVisible({ timeout: 5000 })
  })

  test('clears form state after displaying confirmation', async ({ page }) => {
    // Set up form state
    await page.addInitScript(
      ({ reservationId, sessionId }) => {
        const formState = {
          currentStep: 'payment',
          selectedRange: {
            from: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
            to: new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString(),
          },
          guestDetails: {
            name: 'Test User',
            email: 'test@example.com',
            phone: '+34 600 000 000',
            guestCount: 2,
          },
          reservationId: reservationId,
          paymentAttempts: 0,
          lastPaymentError: null,
          stripeSessionId: sessionId,
        }
        sessionStorage.setItem('booking-form-state', JSON.stringify(formState))
      },
      { reservationId: MOCK_RESERVATION_ID, sessionId: MOCK_SESSION_ID }
    )

    // Mock auth
    await page.addInitScript(() => {
      // @ts-expect-error - global mock for E2E tests
      window.__MOCK_AUTH__ = {
        tokens: { idToken: { toString: () => 'mock-id-token' } },
      }
    })

    // Mock payment status API
    await page.route(`**/api/payments/${MOCK_RESERVATION_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          payment_id: 'PAY-123',
          reservation_id: MOCK_RESERVATION_ID,
          amount: 41000,
          currency: 'EUR',
          status: 'completed',
          provider: 'stripe',
        }),
      })
    })

    await page.goto(`/booking/success?session_id=${MOCK_SESSION_ID}`)

    // Wait for confirmation
    await expect(page.getByText(/booking confirmed/i)).toBeVisible({ timeout: 10000 })

    // Check that form state was reset to initial state
    // Note: useFormPersistence.clear() sets state to initialValue, which syncs back to storage
    // So storage won't be null - it will contain the initial form state
    const storageState = await page.evaluate(() => {
      return sessionStorage.getItem('booking-form-state')
    })

    // Verify storage exists and contains reset state (currentStep: 'dates', no reservationId)
    expect(storageState).not.toBeNull()
    const parsedState = JSON.parse(storageState!)
    expect(parsedState.currentStep).toBe('dates')
    expect(parsedState.reservationId).toBeNull()
    expect(parsedState.stripeSessionId).toBeNull()
  })

  test('shows home button to return to main page', async ({ page }) => {
    // Set up valid state
    await page.addInitScript(
      ({ reservationId, sessionId }) => {
        const formState = {
          currentStep: 'payment',
          selectedRange: {
            from: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
            to: new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString(),
          },
          guestDetails: {
            name: 'Test User',
            email: 'test@example.com',
            phone: '+34 600 000 000',
            guestCount: 2,
          },
          reservationId: reservationId,
          paymentAttempts: 0,
          lastPaymentError: null,
          stripeSessionId: sessionId,
        }
        sessionStorage.setItem('booking-form-state', JSON.stringify(formState))
      },
      { reservationId: MOCK_RESERVATION_ID, sessionId: MOCK_SESSION_ID }
    )

    await page.addInitScript(() => {
      // @ts-expect-error - mock
      window.__MOCK_AUTH__ = {
        tokens: { idToken: { toString: () => 'mock-id-token' } },
      }
    })

    await page.route(`**/api/payments/${MOCK_RESERVATION_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          payment_id: 'PAY-123',
          reservation_id: MOCK_RESERVATION_ID,
          amount: 41000,
          currency: 'EUR',
          status: 'completed',
          provider: 'stripe',
        }),
      })
    })

    await page.goto(`/booking/success?session_id=${MOCK_SESSION_ID}`)

    await expect(page.getByText(/booking confirmed/i)).toBeVisible({ timeout: 10000 })

    // Should have home button
    const homeLink = page.getByRole('link', { name: /back to home/i })
    await expect(homeLink).toBeVisible()
    await expect(homeLink).toHaveAttribute('href', '/')
  })
})

// === Cancel Page Tests ===

test.describe('Payment Cancel Page', () => {
  test('displays cancellation message with saved booking', async ({ page }) => {
    // Set up form state
    await page.addInitScript(() => {
      const formState = {
        currentStep: 'payment',
        selectedRange: {
          from: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
          to: new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString(),
        },
        guestDetails: {
          name: 'Test User',
          email: 'test@example.com',
          phone: '+34 600 000 000',
          guestCount: 2,
        },
        reservationId: 'RES-2025-CANCEL',
        paymentAttempts: 0,
        lastPaymentError: null,
        stripeSessionId: null,
      }
      sessionStorage.setItem('booking-form-state', JSON.stringify(formState))
    })

    await page.goto('/booking/cancel')

    // Should show cancellation message
    await expect(page.getByText(/payment not completed/i)).toBeVisible({ timeout: 5000 })

    // Should show saved booking details
    await expect(page.getByText('Test User')).toBeVisible()
  })

  test('shows try again button', async ({ page }) => {
    // Set up form state
    await page.addInitScript(() => {
      const formState = {
        currentStep: 'payment',
        selectedRange: {
          from: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
          to: new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString(),
        },
        guestDetails: {
          name: 'Test User',
          email: 'test@example.com',
          phone: '+34 600 000 000',
          guestCount: 2,
        },
        reservationId: 'RES-2025-CANCEL',
        paymentAttempts: 0,
        lastPaymentError: null,
        stripeSessionId: null,
      }
      sessionStorage.setItem('booking-form-state', JSON.stringify(formState))
    })

    await page.goto('/booking/cancel')

    const tryAgainButton = page.getByRole('button', { name: /try again/i })
    await expect(tryAgainButton).toBeVisible()
  })

  test('try again navigates back to booking page', async ({ page }) => {
    // Set up form state
    await page.addInitScript(() => {
      const formState = {
        currentStep: 'payment',
        selectedRange: {
          from: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
          to: new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString(),
        },
        guestDetails: {
          name: 'Test User',
          email: 'test@example.com',
          phone: '+34 600 000 000',
          guestCount: 2,
        },
        reservationId: 'RES-2025-CANCEL',
        paymentAttempts: 0,
        lastPaymentError: null,
        stripeSessionId: null,
      }
      sessionStorage.setItem('booking-form-state', JSON.stringify(formState))
    })

    await page.goto('/booking/cancel')

    await page.getByRole('button', { name: /try again/i }).click()

    // Should navigate to /book (with optional trailing slash due to Next.js config)
    await expect(page).toHaveURL(/\/book\/?$/)

    // Should show payment step (form state preserved)
    await expect(page.getByText(/complete payment/i)).toBeVisible({ timeout: 10000 })
  })

  test('preserves form data after cancellation', async ({ page }) => {
    const testName = 'Preserved User'
    const testEmail = 'preserved@example.com'

    // Set up form state
    await page.addInitScript(
      ({ name, email }) => {
        const formState = {
          currentStep: 'payment',
          selectedRange: {
            from: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
            to: new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString(),
          },
          guestDetails: {
            name: name,
            email: email,
            phone: '+34 600 000 000',
            guestCount: 2,
          },
          reservationId: 'RES-2025-CANCEL',
          paymentAttempts: 0,
          lastPaymentError: null,
          stripeSessionId: null,
        }
        sessionStorage.setItem('booking-form-state', JSON.stringify(formState))
      },
      { name: testName, email: testEmail }
    )

    await page.goto('/booking/cancel')

    // Should show preserved name
    await expect(page.getByText(testName)).toBeVisible()
  })

  test('shows no booking found when storage empty', async ({ page }) => {
    // Clear storage
    await page.addInitScript(() => {
      sessionStorage.clear()
    })

    await page.goto('/booking/cancel')

    await expect(page.getByText(/no booking found/i)).toBeVisible({ timeout: 5000 })
  })

  test('increments payment attempt counter', async ({ page }) => {
    // Set up form state with 1 attempt already
    await page.addInitScript(() => {
      const formState = {
        currentStep: 'payment',
        selectedRange: {
          from: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
          to: new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString(),
        },
        guestDetails: {
          name: 'Test User',
          email: 'test@example.com',
          phone: '+34 600 000 000',
          guestCount: 2,
        },
        reservationId: 'RES-2025-CANCEL',
        paymentAttempts: 1, // Already 1 attempt
        lastPaymentError: null,
        stripeSessionId: null,
      }
      sessionStorage.setItem('booking-form-state', JSON.stringify(formState))
    })

    await page.goto('/booking/cancel')

    // Should show attempt counter (2 of 3)
    await expect(page.getByText(/attempt 2 of 3/i)).toBeVisible()
  })

  test('shows max attempts message after 3 failures', async ({ page }) => {
    // Set up form state with 2 attempts (will become 3 on cancel page load)
    await page.addInitScript(() => {
      const formState = {
        currentStep: 'payment',
        selectedRange: {
          from: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
          to: new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString(),
        },
        guestDetails: {
          name: 'Test User',
          email: 'test@example.com',
          phone: '+34 600 000 000',
          guestCount: 2,
        },
        reservationId: 'RES-2025-CANCEL',
        paymentAttempts: 2, // Will become 3 on page load
        lastPaymentError: null,
        stripeSessionId: null,
      }
      sessionStorage.setItem('booking-form-state', JSON.stringify(formState))
    })

    await page.goto('/booking/cancel')

    // Should show max attempts exceeded heading
    await expect(
      page.getByRole('heading', { name: /payment attempts exceeded/i })
    ).toBeVisible()

    // Should NOT show try again button
    await expect(page.getByRole('button', { name: /try again/i })).not.toBeVisible()
  })
})

// === Form State Persistence Tests ===

test.describe('Payment Flow - State Persistence', () => {
  test('form state survives page reload on payment step', async ({ page }) => {
    await completeBookingFormToPayment(page)

    // Should be on payment step
    await expect(page.getByText('Complete Payment')).toBeVisible()

    // Reload page
    await page.reload()

    // Should still be on payment step with data preserved
    await expect(page.getByText('Complete Payment')).toBeVisible()
    await expect(page.getByText(TEST_GUEST.name)).toBeVisible()
  })
})

// === Failed Payment Tests (Success Page with PaymentRetryButton) ===

test.describe('Payment Success Page - Failed Payment State', () => {
  const MOCK_FAILED_RESERVATION_ID = 'RES-2025-FAILED123'

  test('displays failed payment state with retry button', async ({ page }) => {
    // Set up form state with no payment attempts
    await page.addInitScript(
      ({ reservationId, sessionId }) => {
        const formState = {
          currentStep: 'payment',
          selectedRange: {
            from: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
            to: new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString(),
          },
          guestDetails: {
            name: 'Failed Payment User',
            email: 'failed@example.com',
            phone: '+34 600 000 000',
            guestCount: 2,
          },
          reservationId: reservationId,
          paymentAttempts: 0, // First attempt
          lastPaymentError: null,
          stripeSessionId: sessionId,
        }
        sessionStorage.setItem('booking-form-state', JSON.stringify(formState))
      },
      { reservationId: MOCK_FAILED_RESERVATION_ID, sessionId: 'cs_test_failed123' }
    )

    // Mock auth
    await page.addInitScript(() => {
      // @ts-expect-error - global mock for E2E tests
      window.__MOCK_AUTH__ = {
        tokens: { idToken: { toString: () => 'mock-id-token' } },
      }
    })

    // Mock payment status API returning failed status
    await page.route(`**/api/payments/${MOCK_FAILED_RESERVATION_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          payment_id: 'PAY-FAILED',
          reservation_id: MOCK_FAILED_RESERVATION_ID,
          amount: 41000,
          currency: 'EUR',
          status: 'failed', // Payment failed
          provider: 'stripe',
          created_at: new Date().toISOString(),
        }),
      })
    })

    await page.goto(`/booking/success?session_id=cs_test_failed123`)

    // Should show payment failed message
    await expect(page.getByText(/payment failed/i)).toBeVisible({ timeout: 10000 })

    // Should show retry button
    await expect(page.getByRole('button', { name: /try again/i })).toBeVisible()

    // Should show attempts remaining (3 - 0 = 3 remaining)
    await expect(page.getByText(/attempts remaining/i)).toBeVisible()
  })

  test('shows max attempts reached when attempts exhausted', async ({ page }) => {
    // Set up form state with max attempts reached
    await page.addInitScript(
      ({ reservationId, sessionId }) => {
        const formState = {
          currentStep: 'payment',
          selectedRange: {
            from: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
            to: new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString(),
          },
          guestDetails: {
            name: 'Max Attempts User',
            email: 'maxattempts@example.com',
            phone: '+34 600 000 000',
            guestCount: 2,
          },
          reservationId: reservationId,
          paymentAttempts: 3, // MAX_PAYMENT_ATTEMPTS reached
          lastPaymentError: null,
          stripeSessionId: sessionId,
        }
        sessionStorage.setItem('booking-form-state', JSON.stringify(formState))
      },
      { reservationId: MOCK_FAILED_RESERVATION_ID, sessionId: 'cs_test_maxattempts' }
    )

    // Mock auth
    await page.addInitScript(() => {
      // @ts-expect-error - global mock for E2E tests
      window.__MOCK_AUTH__ = {
        tokens: { idToken: { toString: () => 'mock-id-token' } },
      }
    })

    // Mock payment status API returning failed status
    await page.route(`**/api/payments/${MOCK_FAILED_RESERVATION_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          payment_id: 'PAY-MAXATTEMPTS',
          reservation_id: MOCK_FAILED_RESERVATION_ID,
          amount: 41000,
          currency: 'EUR',
          status: 'failed',
          provider: 'stripe',
          created_at: new Date().toISOString(),
        }),
      })
    })

    await page.goto(`/booking/success?session_id=cs_test_maxattempts`)

    // Should show payment failed message
    await expect(page.getByText(/payment failed/i)).toBeVisible({ timeout: 10000 })

    // Should NOT show retry button (max attempts reached)
    await expect(page.getByRole('button', { name: /try again/i })).not.toBeVisible()

    // Should show max attempts reached message (use heading for specificity)
    await expect(page.getByRole('heading', { name: /maximum payment attempts/i })).toBeVisible()

    // Should show contact support option
    await expect(page.getByRole('link', { name: /contact support/i })).toBeVisible()
  })

  test('retry button navigates to booking page', async ({ page }) => {
    // Set up form state
    await page.addInitScript(
      ({ reservationId, sessionId }) => {
        const formState = {
          currentStep: 'payment',
          selectedRange: {
            from: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
            to: new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString(),
          },
          guestDetails: {
            name: 'Retry User',
            email: 'retry@example.com',
            phone: '+34 600 000 000',
            guestCount: 2,
          },
          reservationId: reservationId,
          paymentAttempts: 1, // 1 attempt, 2 remaining
          lastPaymentError: null,
          stripeSessionId: sessionId,
        }
        sessionStorage.setItem('booking-form-state', JSON.stringify(formState))
      },
      { reservationId: MOCK_FAILED_RESERVATION_ID, sessionId: 'cs_test_retry' }
    )

    await page.addInitScript(() => {
      // @ts-expect-error - mock
      window.__MOCK_AUTH__ = {
        tokens: { idToken: { toString: () => 'mock-id-token' } },
      }
    })

    await page.route(`**/api/payments/${MOCK_FAILED_RESERVATION_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          payment_id: 'PAY-RETRY',
          reservation_id: MOCK_FAILED_RESERVATION_ID,
          amount: 41000,
          currency: 'EUR',
          status: 'failed',
          provider: 'stripe',
        }),
      })
    })

    await page.goto(`/booking/success?session_id=cs_test_retry`)

    await expect(page.getByText(/payment failed/i)).toBeVisible({ timeout: 10000 })

    // Click retry button
    await page.getByRole('button', { name: /try again/i }).click()

    // Should navigate to booking page
    await expect(page).toHaveURL(/\/book\/?$/)
  })

  test('shows failed status badge', async ({ page }) => {
    // Set up form state
    await page.addInitScript(
      ({ reservationId, sessionId }) => {
        const formState = {
          currentStep: 'payment',
          selectedRange: {
            from: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
            to: new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString(),
          },
          guestDetails: {
            name: 'Badge Test User',
            email: 'badge@example.com',
            phone: '+34 600 000 000',
            guestCount: 2,
          },
          reservationId: reservationId,
          paymentAttempts: 0,
          lastPaymentError: null,
          stripeSessionId: sessionId,
        }
        sessionStorage.setItem('booking-form-state', JSON.stringify(formState))
      },
      { reservationId: MOCK_FAILED_RESERVATION_ID, sessionId: 'cs_test_badge' }
    )

    await page.addInitScript(() => {
      // @ts-expect-error - mock
      window.__MOCK_AUTH__ = {
        tokens: { idToken: { toString: () => 'mock-id-token' } },
      }
    })

    await page.route(`**/api/payments/${MOCK_FAILED_RESERVATION_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          payment_id: 'PAY-BADGE',
          reservation_id: MOCK_FAILED_RESERVATION_ID,
          amount: 41000,
          currency: 'EUR',
          status: 'failed',
          provider: 'stripe',
        }),
      })
    })

    await page.goto(`/booking/success?session_id=cs_test_badge`)

    // Should show failed status badge
    await expect(page.getByText('Failed', { exact: true })).toBeVisible({ timeout: 10000 })
  })
})

// === Error Handling Tests ===

test.describe('Payment Flow - Error Handling', () => {
  const MOCK_ERROR_RESERVATION_ID = 'RES-2025-ERROR123'

  test('handles API timeout gracefully', async ({ page }) => {
    // Set up form state
    await page.addInitScript(
      ({ reservationId, sessionId }) => {
        const formState = {
          currentStep: 'payment',
          selectedRange: {
            from: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
            to: new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString(),
          },
          guestDetails: {
            name: 'Timeout User',
            email: 'timeout@example.com',
            phone: '+34 600 000 000',
            guestCount: 2,
          },
          reservationId: reservationId,
          paymentAttempts: 0,
          lastPaymentError: null,
          stripeSessionId: sessionId,
        }
        sessionStorage.setItem('booking-form-state', JSON.stringify(formState))
      },
      { reservationId: MOCK_ERROR_RESERVATION_ID, sessionId: 'cs_test_timeout' }
    )

    await page.addInitScript(() => {
      // @ts-expect-error - mock
      window.__MOCK_AUTH__ = {
        tokens: { idToken: { toString: () => 'mock-id-token' } },
      }
    })

    // Mock payment status API with very slow response (simulates timeout)
    let requestCount = 0
    await page.route(`**/api/payments/${MOCK_ERROR_RESERVATION_ID}`, async (route) => {
      requestCount++
      // Let first few requests timeout, then succeed
      if (requestCount <= 2) {
        // Don't respond at all - simulate timeout
        await new Promise((resolve) => setTimeout(resolve, 10000))
      }
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Service unavailable' }),
      })
    })

    await page.goto(`/booking/success?session_id=cs_test_timeout`)

    // Should eventually show an error state or loading state
    // The page should handle the timeout gracefully
    await expect(page.getByText(/verifying|error|loading/i)).toBeVisible({ timeout: 15000 })
  })

  test('handles authentication error', async ({ page }) => {
    // Set up form state
    await page.addInitScript(
      ({ reservationId, sessionId }) => {
        const formState = {
          currentStep: 'payment',
          selectedRange: {
            from: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
            to: new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString(),
          },
          guestDetails: {
            name: 'Auth Error User',
            email: 'autherror@example.com',
            phone: '+34 600 000 000',
            guestCount: 2,
          },
          reservationId: reservationId,
          paymentAttempts: 0,
          lastPaymentError: null,
          stripeSessionId: sessionId,
        }
        sessionStorage.setItem('booking-form-state', JSON.stringify(formState))
      },
      { reservationId: MOCK_ERROR_RESERVATION_ID, sessionId: 'cs_test_auth' }
    )

    // No auth mock - should cause authentication error

    // Mock payment status API that returns 401
    await page.route(`**/api/payments/${MOCK_ERROR_RESERVATION_ID}`, async (route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Authentication required' }),
      })
    })

    await page.goto(`/booking/success?session_id=cs_test_auth`)

    // Should show error state (use heading for specificity)
    await expect(page.getByRole('heading', { name: /verification error/i })).toBeVisible({ timeout: 10000 })
  })

  test('handles pending state with polling indicator', async ({ page }) => {
    // Set up form state
    await page.addInitScript(
      ({ reservationId, sessionId }) => {
        const formState = {
          currentStep: 'payment',
          selectedRange: {
            from: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
            to: new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString(),
          },
          guestDetails: {
            name: 'Pending User',
            email: 'pending@example.com',
            phone: '+34 600 000 000',
            guestCount: 2,
          },
          reservationId: reservationId,
          paymentAttempts: 0,
          lastPaymentError: null,
          stripeSessionId: sessionId,
        }
        sessionStorage.setItem('booking-form-state', JSON.stringify(formState))
      },
      { reservationId: MOCK_ERROR_RESERVATION_ID, sessionId: 'cs_test_pending' }
    )

    await page.addInitScript(() => {
      // @ts-expect-error - mock
      window.__MOCK_AUTH__ = {
        tokens: { idToken: { toString: () => 'mock-id-token' } },
      }
    })

    // Mock payment status API that keeps returning pending
    await page.route(`**/api/payments/${MOCK_ERROR_RESERVATION_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          payment_id: 'PAY-PENDING',
          reservation_id: MOCK_ERROR_RESERVATION_ID,
          amount: 41000,
          currency: 'EUR',
          status: 'pending', // Still pending
          provider: 'stripe',
        }),
      })
    })

    await page.goto(`/booking/success?session_id=cs_test_pending`)

    // Should show pending/processing state (use exact text for specificity)
    await expect(page.getByText('Payment Processing...')).toBeVisible({ timeout: 10000 })

    // Should show pending status badge (use role for badge element)
    await expect(page.locator('[class*="bg-yellow"]').filter({ hasText: 'Pending' })).toBeVisible()
  })

  test('transitions from pending to completed', async ({ page }) => {
    // Set up form state
    await page.addInitScript(
      ({ reservationId, sessionId }) => {
        const formState = {
          currentStep: 'payment',
          selectedRange: {
            from: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
            to: new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString(),
          },
          guestDetails: {
            name: 'Transition User',
            email: 'transition@example.com',
            phone: '+34 600 000 000',
            guestCount: 2,
          },
          reservationId: reservationId,
          paymentAttempts: 0,
          lastPaymentError: null,
          stripeSessionId: sessionId,
        }
        sessionStorage.setItem('booking-form-state', JSON.stringify(formState))
      },
      { reservationId: MOCK_ERROR_RESERVATION_ID, sessionId: 'cs_test_transition' }
    )

    await page.addInitScript(() => {
      // @ts-expect-error - mock
      window.__MOCK_AUTH__ = {
        tokens: { idToken: { toString: () => 'mock-id-token' } },
      }
    })

    // Mock payment status API that returns pending first, then completed
    let requestCount = 0
    await page.route(`**/api/payments/${MOCK_ERROR_RESERVATION_ID}`, async (route) => {
      requestCount++
      const status = requestCount <= 2 ? 'pending' : 'completed'
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          payment_id: 'PAY-TRANSITION',
          reservation_id: MOCK_ERROR_RESERVATION_ID,
          amount: 41000,
          currency: 'EUR',
          status: status,
          provider: 'stripe',
        }),
      })
    })

    await page.goto(`/booking/success?session_id=cs_test_transition`)

    // Should eventually show success
    await expect(page.getByText(/booking confirmed/i)).toBeVisible({ timeout: 15000 })

    // Should show paid badge
    await expect(page.getByText('Paid', { exact: true })).toBeVisible()
  })

  test('shows refunded state message', async ({ page }) => {
    // Set up form state
    await page.addInitScript(
      ({ reservationId, sessionId }) => {
        const formState = {
          currentStep: 'payment',
          selectedRange: {
            from: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
            to: new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString(),
          },
          guestDetails: {
            name: 'Refund User',
            email: 'refund@example.com',
            phone: '+34 600 000 000',
            guestCount: 2,
          },
          reservationId: reservationId,
          paymentAttempts: 0,
          lastPaymentError: null,
          stripeSessionId: sessionId,
        }
        sessionStorage.setItem('booking-form-state', JSON.stringify(formState))
      },
      { reservationId: MOCK_ERROR_RESERVATION_ID, sessionId: 'cs_test_refund' }
    )

    await page.addInitScript(() => {
      // @ts-expect-error - mock
      window.__MOCK_AUTH__ = {
        tokens: { idToken: { toString: () => 'mock-id-token' } },
      }
    })

    // Mock payment status API returning refunded
    await page.route(`**/api/payments/${MOCK_ERROR_RESERVATION_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          payment_id: 'PAY-REFUND',
          reservation_id: MOCK_ERROR_RESERVATION_ID,
          amount: 41000,
          currency: 'EUR',
          status: 'refunded',
          provider: 'stripe',
        }),
      })
    })

    await page.goto(`/booking/success?session_id=cs_test_refund`)

    // Should show refunded/error message
    await expect(page.getByText(/refunded|contact support/i)).toBeVisible({ timeout: 10000 })
  })
})

// === Responsive Design Tests ===

test.describe('Payment Flow - Responsive Design', () => {
  test('payment step works on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })

    await completeBookingFormToPayment(page)

    await expect(page.getByText('Complete Payment')).toBeVisible()
    await expect(page.getByRole('button', { name: /proceed to payment/i })).toBeVisible()
  })

  test('success page works on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })

    // Set up valid state
    await page.addInitScript(() => {
      const formState = {
        currentStep: 'payment',
        selectedRange: {
          from: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
          to: new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString(),
        },
        guestDetails: {
          name: 'Mobile User',
          email: 'mobile@example.com',
          phone: '+34 600 000 000',
          guestCount: 2,
        },
        reservationId: 'RES-MOBILE',
        paymentAttempts: 0,
        lastPaymentError: null,
        stripeSessionId: 'cs_test_mobile',
      }
      sessionStorage.setItem('booking-form-state', JSON.stringify(formState))

      // @ts-expect-error - mock
      window.__MOCK_AUTH__ = {
        tokens: { idToken: { toString: () => 'mock-id-token' } },
      }
    })

    await page.route('**/api/payments/RES-MOBILE', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          payment_id: 'PAY-MOBILE',
          reservation_id: 'RES-MOBILE',
          amount: 41000,
          currency: 'EUR',
          status: 'completed',
          provider: 'stripe',
        }),
      })
    })

    await page.goto('/booking/success?session_id=cs_test_mobile')

    await expect(page.getByText(/booking confirmed/i)).toBeVisible({ timeout: 10000 })
  })

  test('cancel page works on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })

    await page.addInitScript(() => {
      const formState = {
        currentStep: 'payment',
        selectedRange: {
          from: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
          to: new Date(Date.now() + 17 * 24 * 60 * 60 * 1000).toISOString(),
        },
        guestDetails: {
          name: 'Mobile Cancel User',
          email: 'mobilecancel@example.com',
          phone: '+34 600 000 000',
          guestCount: 2,
        },
        reservationId: 'RES-MOBILE-CANCEL',
        paymentAttempts: 0,
        lastPaymentError: null,
        stripeSessionId: null,
      }
      sessionStorage.setItem('booking-form-state', JSON.stringify(formState))
    })

    await page.goto('/booking/cancel')

    await expect(page.getByText(/payment not completed/i)).toBeVisible()
    await expect(page.getByRole('button', { name: /try again/i })).toBeVisible()
  })
})
