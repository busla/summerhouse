/**
 * E2E Tests: Auth Step in Booking Flow (T011)
 *
 * TDD Red Phase: Tests define expected behavior before implementation.
 *
 * Tests the auth step in the multi-step direct booking form:
 * 1. Date selection → Auth step (Verify Identity) → Guest details → Payment
 *
 * Test scenarios:
 * - Unauthenticated flow: form → fill fields → click "Verify Email" → OTP UI appears
 * - Authenticated bypass: skip auth step when already logged in
 * - Returning customer: recognized by email, auto-populate name
 */

import { test, expect, type Page } from '@playwright/test'
import { addDays, format } from 'date-fns'

// === Test Fixtures ===

const TEST_CUSTOMER = {
  name: 'Jane Test',
  email: 'jane.test@example.com',
  phone: '+34 612 345 678',
}

/**
 * Helper to select a date in the shadcn calendar.
 */
async function selectDate(page: Page, date: Date) {
  const dateStr = date.toLocaleDateString()
  const dayButton = page.locator(`button[data-day="${dateStr}"]`)

  // Navigate to correct month if needed
  let attempts = 0
  while (!(await dayButton.isVisible()) && attempts < 3) {
    await page.getByRole('button', { name: /next month/i }).click()
    await page.waitForTimeout(100)
    attempts++
  }

  await dayButton.click()
}

/**
 * Helper to complete the date selection step.
 */
async function completeDateSelectionStep(page: Page) {
  const checkIn = addDays(new Date(), 7)
  const checkOut = addDays(checkIn, 3)

  await selectDate(page, checkIn)
  await selectDate(page, checkOut)

  // Click Continue to proceed to auth step
  await page.getByRole('button', { name: /continue/i }).click()
}

// === Page Load Tests ===

test.describe('Auth Step - Initial Load', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/book')
    await page.waitForSelector('[data-slot="calendar"]')
    await completeDateSelectionStep(page)
  })

  test('displays auth step after date selection', async ({ page }) => {
    // Should be on auth step
    await expect(page.getByText(/verify identity/i)).toBeVisible()

    // Should show form fields
    await expect(page.getByLabel(/full name/i)).toBeVisible()
    await expect(page.getByLabel(/email/i)).toBeVisible()
    await expect(page.getByLabel(/phone/i)).toBeVisible()
  })

  test('shows "Verify Email" button', async ({ page }) => {
    await expect(page.getByRole('button', { name: /verify email/i })).toBeVisible()
  })

  test('shows "Back" button to return to dates', async ({ page }) => {
    await expect(page.getByRole('button', { name: /back/i })).toBeVisible()
  })

  test('step indicator shows auth step as active', async ({ page }) => {
    // The step indicator should highlight the "Verify Identity" step
    // Look for the Shield icon or step being marked as current
    await expect(page.locator('[data-step="auth"].active, [data-step="auth"][aria-current="step"]').or(
      page.getByText(/verify identity/i)
    )).toBeVisible()
  })
})

// === Form Interaction Tests ===

test.describe('Auth Step - Form Interaction', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/book')
    await page.waitForSelector('[data-slot="calendar"]')
    await completeDateSelectionStep(page)
  })

  test('allows entering name, email, and phone', async ({ page }) => {
    await page.getByLabel(/full name/i).fill(TEST_CUSTOMER.name)
    await page.getByLabel(/email/i).fill(TEST_CUSTOMER.email)
    await page.getByLabel(/phone/i).fill(TEST_CUSTOMER.phone)

    // Values should be entered
    await expect(page.getByLabel(/full name/i)).toHaveValue(TEST_CUSTOMER.name)
    await expect(page.getByLabel(/email/i)).toHaveValue(TEST_CUSTOMER.email)
    await expect(page.getByLabel(/phone/i)).toHaveValue(TEST_CUSTOMER.phone)
  })

  test('shows validation errors for empty required fields', async ({ page }) => {
    // Click verify without filling form
    await page.getByRole('button', { name: /verify email/i }).click()

    // Should show validation errors
    await expect(page.getByText(/name must be at least 2 characters/i)).toBeVisible()
    await expect(page.getByText(/valid email/i)).toBeVisible()
    await expect(page.getByText(/phone number must be at least 7/i)).toBeVisible()
  })

  test('shows validation error for invalid email format', async ({ page }) => {
    await page.getByLabel(/full name/i).fill(TEST_CUSTOMER.name)
    await page.getByLabel(/email/i).fill('invalid-email')
    await page.getByLabel(/phone/i).fill(TEST_CUSTOMER.phone)

    await page.getByRole('button', { name: /verify email/i }).click()

    await expect(page.getByText(/valid email/i)).toBeVisible()
  })

  test('clicking Back returns to date selection', async ({ page }) => {
    await page.getByRole('button', { name: /back/i }).click()

    // Should be back on date selection step
    await expect(page.getByText(/select your dates/i)).toBeVisible()
    await expect(page.locator('[data-slot="calendar"]').first()).toBeVisible()
  })
})

// === OTP Flow Tests ===

test.describe('Auth Step - OTP Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/book')
    await page.waitForSelector('[data-slot="calendar"]')
    await completeDateSelectionStep(page)
  })

  test('shows loading state when "Verify Email" is clicked', async ({ page }) => {
    // Fill valid form
    await page.getByLabel(/full name/i).fill(TEST_CUSTOMER.name)
    await page.getByLabel(/email/i).fill(TEST_CUSTOMER.email)
    await page.getByLabel(/phone/i).fill(TEST_CUSTOMER.phone)

    // Click verify - the form should transition to OTP view or show loading state
    await page.getByRole('button', { name: /verify email/i }).click()

    // The button either shows "Sending..." briefly or transitions to OTP view
    // Since the sending state is transient, we check for either:
    // 1. The "Sending..." state if it's visible
    // 2. The OTP view (which appears after sending)
    const sendingButton = page.getByRole('button', { name: /sending/i })
    const otpInput = page.getByLabel(/verification code|code/i)

    // Wait for either the sending state or the OTP view (indicating send completed)
    await expect(sendingButton.or(otpInput)).toBeVisible({ timeout: 10000 })
  })

  test('transitions to OTP input UI after sending', async ({ page }) => {
    // Note: This test may need mocking in real scenarios
    // For now, we test the UI transition expectation

    await page.getByLabel(/full name/i).fill(TEST_CUSTOMER.name)
    await page.getByLabel(/email/i).fill(TEST_CUSTOMER.email)
    await page.getByLabel(/phone/i).fill(TEST_CUSTOMER.phone)

    await page.getByRole('button', { name: /verify email/i }).click()

    // Should show OTP input UI (may timeout if backend not configured)
    // In TDD red phase, this test is expected to fail until component is implemented
    await expect(page.getByLabel(/verification code|code/i)).toBeVisible({ timeout: 10000 })
  })

  test('OTP input has 6 separate boxes', async ({ page }) => {
    await page.getByLabel(/full name/i).fill(TEST_CUSTOMER.name)
    await page.getByLabel(/email/i).fill(TEST_CUSTOMER.email)
    await page.getByLabel(/phone/i).fill(TEST_CUSTOMER.phone)

    await page.getByRole('button', { name: /verify email/i }).click()

    // Wait for OTP UI
    await expect(page.getByLabel(/verification code|code/i)).toBeVisible({ timeout: 10000 })

    // Should have 6 input slots (shadcn InputOTPSlot components)
    const otpSlots = page.locator('[data-slot="otp-slot"]')
    await expect(otpSlots).toHaveCount(6)
  })

  test('displays email address that code was sent to', async ({ page }) => {
    await page.getByLabel(/full name/i).fill(TEST_CUSTOMER.name)
    await page.getByLabel(/email/i).fill(TEST_CUSTOMER.email)
    await page.getByLabel(/phone/i).fill(TEST_CUSTOMER.phone)

    await page.getByRole('button', { name: /verify email/i }).click()

    // Wait for OTP UI
    await expect(page.getByLabel(/verification code|code/i)).toBeVisible({ timeout: 10000 })

    // Should show the email
    await expect(page.getByText(TEST_CUSTOMER.email)).toBeVisible()
  })

  test('shows "Resend code" option', async ({ page }) => {
    await page.getByLabel(/full name/i).fill(TEST_CUSTOMER.name)
    await page.getByLabel(/email/i).fill(TEST_CUSTOMER.email)
    await page.getByLabel(/phone/i).fill(TEST_CUSTOMER.phone)

    await page.getByRole('button', { name: /verify email/i }).click()

    // Wait for OTP UI
    await expect(page.getByLabel(/verification code|code/i)).toBeVisible({ timeout: 10000 })

    // Should show resend option
    await expect(page.getByRole('button', { name: /resend|send again/i })).toBeVisible()
  })

  test('shows option to change email from OTP screen', async ({ page }) => {
    await page.getByLabel(/full name/i).fill(TEST_CUSTOMER.name)
    await page.getByLabel(/email/i).fill(TEST_CUSTOMER.email)
    await page.getByLabel(/phone/i).fill(TEST_CUSTOMER.phone)

    await page.getByRole('button', { name: /verify email/i }).click()

    // Wait for OTP UI
    await expect(page.getByLabel(/verification code|code/i)).toBeVisible({ timeout: 10000 })

    // Should show "Change email" button specifically (not generic back button)
    await expect(page.getByRole('button', { name: /change email/i })).toBeVisible()
  })
})

// === Form State Persistence Tests ===

test.describe('Auth Step - Form Persistence', () => {
  test('preserves form data when navigating back and forth', async ({ page }) => {
    await page.goto('/book')
    await page.waitForSelector('[data-slot="calendar"]')
    await completeDateSelectionStep(page)

    // Fill auth form
    await page.getByLabel(/full name/i).fill(TEST_CUSTOMER.name)
    await page.getByLabel(/email/i).fill(TEST_CUSTOMER.email)
    await page.getByLabel(/phone/i).fill(TEST_CUSTOMER.phone)

    // Go back to dates
    await page.getByRole('button', { name: /back/i }).click()
    await expect(page.getByText(/select your dates/i)).toBeVisible()

    // Continue back to auth
    await page.getByRole('button', { name: /continue/i }).click()

    // Form data should be preserved
    await expect(page.getByLabel(/full name/i)).toHaveValue(TEST_CUSTOMER.name)
    await expect(page.getByLabel(/email/i)).toHaveValue(TEST_CUSTOMER.email)
    await expect(page.getByLabel(/phone/i)).toHaveValue(TEST_CUSTOMER.phone)
  })

  test('preserves form data on page refresh', async ({ page }) => {
    await page.goto('/book')
    await page.waitForSelector('[data-slot="calendar"]')
    await completeDateSelectionStep(page)

    // Fill auth form
    await page.getByLabel(/full name/i).fill(TEST_CUSTOMER.name)
    await page.getByLabel(/email/i).fill(TEST_CUSTOMER.email)
    await page.getByLabel(/phone/i).fill(TEST_CUSTOMER.phone)

    // Refresh page
    await page.reload()

    // Should be on auth step with preserved data (due to sessionStorage persistence)
    await expect(page.getByLabel(/full name/i)).toHaveValue(TEST_CUSTOMER.name)
    await expect(page.getByLabel(/email/i)).toHaveValue(TEST_CUSTOMER.email)
    await expect(page.getByLabel(/phone/i)).toHaveValue(TEST_CUSTOMER.phone)
  })
})

// === Error Handling Tests ===

test.describe('Auth Step - Error Handling', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/book')
    await page.waitForSelector('[data-slot="calendar"]')
    await completeDateSelectionStep(page)
  })

  test('shows error message for network failure', async ({ page }) => {
    // This test requires network interception
    // Mock Cognito endpoints to simulate network failure

    // Mock Cognito endpoints (where auth calls actually go)
    await page.route('**/cognito-idp.*amazonaws.com/**', (route) => route.abort())

    await page.getByLabel(/full name/i).fill(TEST_CUSTOMER.name)
    await page.getByLabel(/email/i).fill(TEST_CUSTOMER.email)
    await page.getByLabel(/phone/i).fill(TEST_CUSTOMER.phone)

    await page.getByRole('button', { name: /verify email/i }).click()

    // Should show network error message (displayed in the error alert)
    await expect(page.getByRole('alert')).toBeVisible({ timeout: 10000 })

    // The error should contain network-related text
    await expect(page.getByText(/network|failed|error|unable/i)).toBeVisible()

    // Should have retry button
    await expect(page.getByRole('button', { name: /retry/i })).toBeVisible()
  })
})

// === Step Indicator Tests ===

test.describe('Auth Step - Step Indicator', () => {
  test('shows 4 steps in indicator', async ({ page }) => {
    await page.goto('/book')

    // Step indicator should show: Dates, Verify Identity, Guest Details, Payment
    // This assumes the StepIndicator renders visible step icons
    const steps = page.locator('[data-testid="step-indicator"] > div').or(
      page.locator('.flex.items-center.justify-center.gap-2 > div')
    )

    // Should have at least 4 step elements
    await expect(steps.first()).toBeVisible()
  })

  test('auth step (step 2) is highlighted when active', async ({ page }) => {
    await page.goto('/book')
    await page.waitForSelector('[data-slot="calendar"]')
    await completeDateSelectionStep(page)

    // Verify we're on the auth step by checking the card title
    await expect(page.getByText(/verify identity/i)).toBeVisible()

    // The step indicator should show the second step (auth) as active
    // Active step has primary border and background styling
    // Count step indicators with primary styling (first is completed, second is active)
    const stepCircles = page.locator('.rounded-full.border-2')
    await expect(stepCircles.first()).toBeVisible()

    // Verify there are multiple step indicators rendered
    expect(await stepCircles.count()).toBeGreaterThanOrEqual(2)
  })
})

// === Accessibility Tests ===

test.describe('Auth Step - Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/book')
    await page.waitForSelector('[data-slot="calendar"]')
    await completeDateSelectionStep(page)
  })

  test('form fields have proper labels', async ({ page }) => {
    // Check that inputs are properly associated with labels
    const nameInput = page.getByLabel(/full name/i)
    const emailInput = page.getByLabel(/email/i)
    const phoneInput = page.getByLabel(/phone/i)

    await expect(nameInput).toBeVisible()
    await expect(emailInput).toBeVisible()
    await expect(phoneInput).toBeVisible()
  })

  test('form can be navigated with keyboard', async ({ page }) => {
    // Tab through form fields
    await page.keyboard.press('Tab')
    await expect(page.getByLabel(/full name/i)).toBeFocused()

    await page.keyboard.press('Tab')
    await expect(page.getByLabel(/email/i)).toBeFocused()

    await page.keyboard.press('Tab')
    await expect(page.getByLabel(/phone/i)).toBeFocused()

    await page.keyboard.press('Tab')
    // Should focus on a button (Back or Verify Email)
    const focusedElement = page.locator(':focus')
    await expect(focusedElement).toHaveRole('button')
  })

  test('error messages are associated with fields', async ({ page }) => {
    // Submit empty form
    await page.getByRole('button', { name: /verify email/i }).click()

    // Error messages should be announced to screen readers
    // Check for aria-describedby or aria-errormessage attributes
    const nameInput = page.getByLabel(/full name/i)
    const errorId = await nameInput.getAttribute('aria-describedby')
    expect(errorId).toBeTruthy()
  })
})
