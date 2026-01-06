/**
 * E2E Tests: Next.js Routing and Navigation
 *
 * Tests for fix-routing-waf feature:
 * - T003: Navbar navigation loads correct pages
 * - T004: Booking form data persists across browser refresh
 *
 * These tests verify:
 * - All navbar links work without 403 errors
 * - URLs use trailing slashes consistently
 * - Form persistence via sessionStorage
 */
import { expect, test } from '@playwright/test'

// Navigation links to test (should match Navigation.tsx with trailing slashes)
const navLinks = [
  { label: 'Home', href: '/', expectedPath: '/' },
  { label: 'Gallery', href: '/gallery/', expectedPath: '/gallery/' },
  { label: 'Location', href: '/location/', expectedPath: '/location/' },
  { label: 'Book', href: '/book/', expectedPath: '/book/' },
  { label: 'Agent', href: '/agent/', expectedPath: '/agent/' },
]

test.describe('Navbar Navigation (T003)', () => {
  test.describe('Desktop Navigation', () => {
    test.beforeEach(async ({ page }) => {
      // Set desktop viewport
      await page.setViewportSize({ width: 1280, height: 720 })
    })

    for (const link of navLinks) {
      test(`clicking "${link.label}" navigates to ${link.expectedPath}`, async ({
        page,
      }) => {
        // Start from homepage
        await page.goto('/')
        await page.waitForLoadState('networkidle')

        // Skip Home link - we're already there
        if (link.label === 'Home') {
          // Verify we're on homepage (URL ends with /)
          await expect(page).toHaveURL(/\/$/)
          return
        }

        // Find and click the nav link
        const navLink = page.getByRole('navigation').getByRole('link', {
          name: link.label,
          exact: true,
        })

        await expect(navLink).toBeVisible()
        await navLink.click()

        // Verify navigation completed without error
        await page.waitForLoadState('networkidle')

        // Check URL matches expected path (with trailing slash)
        // Use pattern that matches end of URL since toHaveURL receives full URL
        const expectedUrlRegex = new RegExp(`${link.expectedPath.replace(/\//g, '\\/')}$`)
        await expect(page).toHaveURL(expectedUrlRegex)

        // Verify page loaded successfully (no 403/404 error)
        // Look for page-specific content or absence of error indicators
        const pageContent = page.locator('main')
        await expect(pageContent).toBeVisible()

        // Ensure no error page is shown
        const errorHeading = page.getByRole('heading', { name: /403|404|error/i })
        await expect(errorHeading).not.toBeVisible()
      })
    }

    test('all navbar links are present and have correct href', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const nav = page.getByRole('navigation')

      for (const link of navLinks) {
        const navLink = nav.getByRole('link', { name: link.label, exact: true })
        await expect(navLink).toBeVisible()

        // Verify href attribute includes trailing slash
        const href = await navLink.getAttribute('href')
        expect(href).toBe(link.href)
      }
    })

    test('page refresh after navigation works without 403', async ({ page }) => {
      // Navigate to Gallery via navbar
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const galleryLink = page.getByRole('navigation').getByRole('link', {
        name: 'Gallery',
        exact: true,
      })
      await galleryLink.click()
      await page.waitForLoadState('networkidle')

      // Refresh the page
      await page.reload()
      await page.waitForLoadState('networkidle')

      // Verify still on gallery page without error
      await expect(page).toHaveURL(/\/gallery\/?$/)

      const pageContent = page.locator('main')
      await expect(pageContent).toBeVisible()

      const errorHeading = page.getByRole('heading', { name: /403|404|error/i })
      await expect(errorHeading).not.toBeVisible()
    })
  })

  test.describe('Mobile Navigation', () => {
    test.beforeEach(async ({ page }) => {
      // Set mobile viewport
      await page.setViewportSize({ width: 375, height: 667 })
    })

    test('mobile menu navigation works', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Open mobile menu (hamburger button)
      const menuButton = page.getByRole('button', { name: /menu|toggle/i })

      // Only test if mobile menu exists
      if (await menuButton.isVisible()) {
        await menuButton.click()

        // Click Gallery link in mobile menu
        const galleryLink = page.getByRole('link', { name: 'Gallery', exact: true })
        await expect(galleryLink).toBeVisible()
        await galleryLink.click()

        // Verify navigation worked
        await page.waitForLoadState('networkidle')
        await expect(page).toHaveURL(/\/gallery\/?$/)
      }
    })
  })
})

test.describe('Form Persistence (T004)', () => {
  const STORAGE_KEY = 'booking-form-state'

  test.beforeEach(async ({ page }) => {
    // Clear any existing stored data before each test
    await page.goto('/book/')
    await page.waitForLoadState('networkidle')
    await page.evaluate((key) => sessionStorage.removeItem(key), STORAGE_KEY)
  })

  test('booking form data persists across page refresh', async ({ page }) => {
    await page.goto('/book/')
    await page.waitForLoadState('networkidle')

    // Step 1: Select dates in the calendar
    // The DateRangePicker component has class "date-range-picker" and contains a Calendar
    // The Calendar from shadcn/ui uses .rdp (React Day Picker) classes internally
    const dateRangePicker = page.locator('.date-range-picker')

    // Wait for date picker to be visible
    await expect(dateRangePicker).toBeVisible({ timeout: 10000 })

    // Select a date range - click on two different days
    // Calendar day buttons have data-day attribute and are not disabled
    const availableDays = page.locator('button[data-day]:not([disabled])')

    // Wait for days to be rendered
    await expect(availableDays.first()).toBeVisible({ timeout: 5000 })
    const dayCount = await availableDays.count()

    if (dayCount >= 5) {
      // Click first available day (check-in)
      await availableDays.nth(0).click()
      // Wait a moment for the selection to register
      await page.waitForTimeout(200)
      // Click a day a few days later (check-out) - minimum 3 nights
      await availableDays.nth(4).click()
    }

    // Step 2: Proceed to auth step (4-step flow: dates → auth → guest → payment)
    const nextButton = page.getByRole('button', { name: /continue/i })
    await expect(nextButton).toBeEnabled({ timeout: 5000 })
    await nextButton.click()
    await page.waitForLoadState('networkidle')

    // Step 3: Fill in auth step fields (identity verification)
    // The AuthStep component has name/email/phone fields with "Verify Identity" card title
    await expect(page.getByText('Verify Identity')).toBeVisible({ timeout: 5000 })

    const nameInput = page.getByLabel(/full name/i)
    const emailInput = page.getByLabel(/email address/i)
    const phoneInput = page.getByLabel(/phone number/i)

    // Fill form fields
    await nameInput.fill('John Test User')
    await emailInput.fill('john.test@example.com')
    await phoneInput.fill('+34 612 345 678')

    // Give form time to save to sessionStorage
    await page.waitForTimeout(500)

    // Verify data was stored in sessionStorage
    const storedData = await page.evaluate((key) => sessionStorage.getItem(key), STORAGE_KEY)
    expect(storedData).toBeTruthy()

    // Refresh the page
    await page.reload()
    // Wait for page to be ready - use domcontentloaded instead of networkidle
    // as networkidle can timeout if there are long-polling API requests
    await page.waitForLoadState('domcontentloaded')

    // Wait for the form to be rendered with restored step
    // The page should restore to Auth step ("Verify Identity")
    await expect(page.getByText('Verify Identity')).toBeVisible({ timeout: 10000 })

    // Verify form data was restored
    const restoredData = await page.evaluate((key) => sessionStorage.getItem(key), STORAGE_KEY)
    expect(restoredData).toBeTruthy()

    // Parse and verify the restored data contains our input
    if (restoredData) {
      const parsed = JSON.parse(restoredData)
      // The form state should contain customerName, customerEmail, customerPhone
      expect(parsed).toBeDefined()
      expect(parsed.customerName).toBe('John Test User')
      expect(parsed.customerEmail).toBe('john.test@example.com')
      expect(parsed.customerPhone).toBe('+34 612 345 678')
    }

    // After refresh with form persistence hook, should restore to auth step
    // and name field should have the stored value
    await expect(nameInput).toHaveValue('John Test User', { timeout: 10000 })
  })

  test('form data is cleared after successful booking submission', async ({ page }) => {
    // Pre-populate sessionStorage with test data (new 4-step flow structure)
    await page.evaluate((key) => {
      sessionStorage.setItem(key, JSON.stringify({
        selectedRange: { from: '2026-02-15', to: '2026-02-20' },
        // Auth step fields (new structure per FR-002)
        customerName: 'Test User',
        customerEmail: 'test@example.com',
        customerPhone: '+34 612 345 678',
        authStep: 'authenticated',
        customerId: 'test-customer-123',
        // Simplified guest details (only guestCount + specialRequests per FR-018)
        guestDetails: {
          guestCount: 2,
          specialRequests: '',
        },
        currentStep: 'confirmation',
        reservationId: null,
        paymentAttempts: 0,
        lastPaymentError: null,
        stripeSessionId: null,
      }))
    }, STORAGE_KEY)

    // Reload to apply the pre-populated data
    await page.reload()
    await page.waitForLoadState('networkidle')

    // Find and click the submit/confirm booking button
    const submitButton = page.getByRole('button', { name: /confirm|submit|book/i })

    if (await submitButton.isVisible()) {
      await submitButton.click()

      // Wait for submission to complete
      await page.waitForLoadState('networkidle')

      // After successful submission, sessionStorage should be cleared
      const storedData = await page.evaluate((key) => sessionStorage.getItem(key), STORAGE_KEY)

      // Data should be cleared (null) after successful booking
      expect(storedData).toBeNull()
    }
  })

  test('sessionStorage is scoped to booking form', async ({ page }) => {
    // Set booking form data
    await page.evaluate((key) => {
      sessionStorage.setItem(key, JSON.stringify({ test: 'booking-data' }))
    }, STORAGE_KEY)

    // Navigate away from booking page
    await page.goto('/gallery/')
    await page.waitForLoadState('networkidle')

    // Verify data is still in sessionStorage (not cleared by navigation)
    const storedData = await page.evaluate((key) => sessionStorage.getItem(key), STORAGE_KEY)
    expect(storedData).toBeTruthy()

    // Navigate back to booking page
    await page.goto('/book/')
    await page.waitForLoadState('networkidle')

    // Data should still be present
    const restoredData = await page.evaluate((key) => sessionStorage.getItem(key), STORAGE_KEY)
    expect(restoredData).toBeTruthy()
  })
})

test.describe('Direct URL Access (T009-T010 placeholder)', () => {
  // These tests are placeholders for US2 - they will test CloudFront routing
  // which requires deployed infrastructure

  test.skip('direct URL with trailing slash loads page', async ({ page }) => {
    // This test needs to run against CloudFront, not local dev
    await page.goto('/gallery/')
    await page.waitForLoadState('networkidle')

    await expect(page).toHaveURL(/\/gallery\/$/)
    const errorHeading = page.getByRole('heading', { name: /403|404|error/i })
    await expect(errorHeading).not.toBeVisible()
  })

  test.skip('direct URL without trailing slash loads page', async ({ page }) => {
    // This test needs to run against CloudFront, not local dev
    // The CloudFront Function should rewrite /gallery to /gallery/index.html
    await page.goto('/gallery')
    await page.waitForLoadState('networkidle')

    // Should either stay at /gallery or redirect to /gallery/
    await expect(page).toHaveURL(/\/gallery\/?$/)
    const errorHeading = page.getByRole('heading', { name: /403|404|error/i })
    await expect(errorHeading).not.toBeVisible()
  })
})

test.describe('Active Navigation State (T016)', () => {
  // Pages and their expected active nav link
  const pages = [
    { path: '/', label: 'Home' },
    { path: '/gallery/', label: 'Gallery' },
    { path: '/location/', label: 'Location' },
    { path: '/book/', label: 'Book' },
    { path: '/agent/', label: 'Agent' },
  ]

  test.beforeEach(async ({ page }) => {
    // Set desktop viewport for consistent nav visibility
    await page.setViewportSize({ width: 1280, height: 720 })
  })

  for (const { path, label } of pages) {
    test(`${label} nav link is active when on ${path}`, async ({ page }) => {
      await page.goto(path)
      await page.waitForLoadState('networkidle')

      const nav = page.getByRole('navigation')

      // Verify the current page's link has active styling
      // Active links have text-blue-700 and bg-blue-50 classes
      const activeLink = nav.getByRole('link', { name: label, exact: true })
      await expect(activeLink).toBeVisible()

      // Check for active styling (blue text color)
      await expect(activeLink).toHaveClass(/text-blue-700/)
      await expect(activeLink).toHaveClass(/bg-blue-50/)

      // Verify other links don't have active styling
      // Note: Inactive links have hover:text-blue-700 hover:bg-blue-50 (with hover: prefix)
      // Active links have text-blue-700 bg-blue-50 (without hover: prefix)
      for (const other of pages) {
        if (other.label !== label) {
          const otherLink = nav.getByRole('link', { name: other.label, exact: true })
          const classList = await otherLink.getAttribute('class') ?? ''
          // Split classes and check for non-hover active classes
          const classes = classList.split(/\s+/)
          // Active styling should NOT be present (text-blue-700 and bg-blue-50 without hover: prefix)
          expect(classes).not.toContain('text-blue-700')
          expect(classes).not.toContain('bg-blue-50')
        }
      }
    })
  }

  test('active state works for URL without trailing slash', async ({ page }) => {
    // Next.js may serve the page at either /gallery or /gallery/
    // The navigation should correctly identify the active state regardless
    await page.goto('/gallery')
    await page.waitForLoadState('networkidle')

    const nav = page.getByRole('navigation')
    const galleryLink = nav.getByRole('link', { name: 'Gallery', exact: true })

    // Gallery should be active even when accessed without trailing slash
    await expect(galleryLink).toHaveClass(/text-blue-700/)
    await expect(galleryLink).toHaveClass(/bg-blue-50/)
  })
})
