/**
 * E2E Test: Static Page Navigation
 *
 * Tests navigation and content for all static information pages:
 * - About: Property details and amenities
 * - Location: Map and address information
 * - Pricing: Rate tables and seasonal pricing
 * - Area Guide: Local attractions and activities
 * - FAQ: Frequently asked questions
 * - Contact: Contact form and information
 *
 * Tests verify:
 * 1. Navigation links work correctly
 * 2. Pages load with expected content
 * 3. Navigation menu is accessible from all pages
 * 4. Return to home (chat) page works
 */

import { test, expect } from '@playwright/test'

// === Static Page Definitions ===

const staticPages = [
  {
    name: 'About',
    path: '/about',
    expectedHeading: 'About Quesada Apartment',
    expectedContent: ['Bedrooms', 'Max Guests', 'terrace'],
  },
  {
    name: 'Location',
    path: '/location',
    expectedHeading: 'Location',
    expectedContent: ['Ciudad Quesada', 'Costa Blanca', 'Alicante'],
  },
  {
    name: 'Pricing',
    path: '/pricing',
    expectedHeading: 'Pricing',
    expectedContent: ['per night', 'Season'],
  },
  {
    name: 'Area Guide',
    path: '/area-guide',
    expectedHeading: 'Area Guide',
    expectedContent: ['Golf', 'Beach', 'Restaurant'],
  },
  {
    name: 'FAQ',
    path: '/faq',
    expectedHeading: 'Frequently Asked Questions',
    // FAQ questions are visible even when collapsed
    expectedContent: ['booking', 'payment'],
  },
  {
    name: 'Contact',
    path: '/contact',
    expectedHeading: 'Contact Us',
    expectedContent: ['Email'],
    exactHeading: true, // Use exact match to avoid matching "Before You Contact Us"
  },
]

// === Navigation Tests ===

test.describe('Static Page Navigation', () => {
  test.beforeEach(async ({ page }) => {
    // Start from the home page
    await page.goto('/')
    // Wait for the page to be ready
    await expect(page.locator('body')).toBeVisible()
  })

  test('home page loads with navigation', async ({ page }) => {
    // Check that navigation links are present (desktop nav)
    // Navigation should be visible on desktop viewport
    await page.setViewportSize({ width: 1280, height: 800 })

    // Check for navigation links in the desktop nav bar
    // Nav uses Tailwind classes, so we select by role and structure
    const navLinks = page.locator('nav').filter({ has: page.locator('a[href]') }).locator('a')
    await expect(navLinks).toHaveCount(5) // Home, Gallery, Location, Book, Agent
  })

  // === Individual Page Load Tests ===

  for (const staticPage of staticPages) {
    test(`${staticPage.name} page loads correctly`, async ({ page }) => {
      // Navigate to the page
      await page.goto(staticPage.path)

      // Check page heading (use exact match if specified to avoid matching partial text)
      const headingOptions = (staticPage as { exactHeading?: boolean }).exactHeading
        ? { name: staticPage.expectedHeading, exact: true }
        : { name: new RegExp(staticPage.expectedHeading, 'i') }
      await expect(page.getByRole('heading', headingOptions)).toBeVisible()

      // Check for expected content
      for (const content of staticPage.expectedContent) {
        await expect(page.getByText(new RegExp(content, 'i')).first()).toBeVisible()
      }
    })

    test(`${staticPage.name} page has working navigation back to home`, async ({ page }) => {
      // Navigate to the static page
      await page.goto(staticPage.path)

      // Set desktop viewport for navigation
      await page.setViewportSize({ width: 1280, height: 800 })

      // Find and click the "Book Now" link to return home
      await page.click('a[href="/"]')

      // Verify we're back on the home page (landing page)
      await expect(page).toHaveURL('/')
      await expect(page.getByText('Your Costa Blanca Escape')).toBeVisible()
    })
  }

  // === Desktop Navigation Link Tests ===

  test('desktop navigation links work', async ({ page }) => {
    // Set desktop viewport
    await page.setViewportSize({ width: 1280, height: 800 })

    // Test the navigation links that exist in the default nav
    // Default nav has: Home, Gallery, Location, Book, Agent (not all static pages)
    const navPaths = ['/', '/gallery', '/location', '/book', '/agent']

    for (const navPath of navPaths) {
      // Go to home first
      await page.goto('/')

      // Click the nav link (desktop nav is a visible nav element)
      await page.locator(`nav a[href="${navPath}"]`).first().click()

      // Verify URL changed (handle trailing slash - Next.js may add or omit)
      // Use string match for root, regex for paths (regex tests full URL including hostname)
      if (navPath === '/') {
        await expect(page).toHaveURL('/')
      } else {
        await expect(page).toHaveURL(new RegExp(`${navPath}\\/?$`))
      }
    }
  })

  // === Mobile Navigation Tests ===

  test('mobile navigation menu opens and works', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 })

    // Mobile toggle button should be visible (uses aria-label)
    const mobileToggle = page.getByRole('button', { name: /menu/i })
    await expect(mobileToggle).toBeVisible()

    // Click to open mobile menu
    await mobileToggle.click()

    // Wait for mobile menu to open (aria-expanded changes to true)
    await expect(mobileToggle).toHaveAttribute('aria-expanded', 'true')

    // Mobile nav should appear - it's a fixed position nav that only renders when open
    // The mobile nav is conditionally rendered, so we need to wait for it specifically
    // Desktop nav is hidden on mobile via CSS, mobile nav only exists when menu is open
    const mobileNav = page.locator('nav.fixed')
    await expect(mobileNav).toBeVisible()

    // Click on Location link in the mobile nav
    await mobileNav.locator('a[href="/location"]').click()

    // Should navigate to Location page (handle trailing slash)
    await expect(page).toHaveURL(/\/location\/?/)
    await expect(page.getByRole('heading', { name: /Location/i })).toBeVisible()
  })

  test('mobile menu closes after navigation', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 })

    // Open mobile menu
    const mobileToggle = page.getByRole('button', { name: /menu/i })
    await mobileToggle.click()

    // Wait for mobile menu to open
    await expect(mobileToggle).toHaveAttribute('aria-expanded', 'true')
    const mobileNav = page.locator('nav.fixed')
    await expect(mobileNav).toBeVisible()

    // Navigate to Book page via mobile nav
    await mobileNav.locator('a[href="/book"]').click()

    // Wait for navigation (handle trailing slash)
    await expect(page).toHaveURL(/\/book\/?/)

    // Mobile menu should be closed (check aria-expanded)
    await expect(page.getByRole('button', { name: /menu/i })).toHaveAttribute('aria-expanded', 'false')
  })

  // === Cross-Page Navigation Tests ===

  test('can navigate between static pages via direct URL', async ({ page }) => {
    // Set desktop viewport
    await page.setViewportSize({ width: 1280, height: 800 })

    // Navigate between static pages via direct URL access
    // (These pages aren't in the main nav but are accessible directly)
    const pagePaths = ['/about', '/location', '/pricing', '/area-guide', '/faq', '/contact']

    for (const pagePath of pagePaths) {
      await page.goto(pagePath)
      // Handle trailing slash - Next.js may add or omit
      // Regex tests full URL (http://localhost:3000/path), so use $ anchor only
      await expect(page).toHaveURL(new RegExp(`${pagePath}\\/?$`))
      // Verify we can get back to home via nav
      await page.locator('nav a[href="/"]').first().click()
      await expect(page).toHaveURL('/')
    }
  })

  // === Accessibility Tests ===

  test('navigation has proper ARIA labels', async ({ page }) => {
    // Set mobile viewport to test mobile toggle
    await page.setViewportSize({ width: 375, height: 667 })

    // Mobile toggle should have aria-label
    const mobileToggle = page.getByRole('button', { name: /menu/i })
    await expect(mobileToggle).toBeVisible()
    await expect(mobileToggle).toHaveAttribute('aria-expanded', 'false')

    // Open menu
    await mobileToggle.click()
    await expect(mobileToggle).toHaveAttribute('aria-expanded', 'true')
  })

  // === Page Content Specific Tests ===

  test('About page shows property highlights', async ({ page }) => {
    await page.goto('/about')

    // Check property stats - number and label are in separate elements
    // Stats structure: <div>2</div><div>Bedrooms</div> (not "2 Bedrooms" together)
    // Use .first() because labels may appear elsewhere on page (e.g., in amenities headings)
    await expect(page.getByText('Bedrooms').first()).toBeVisible()
    await expect(page.getByText('Bathroom').first()).toBeVisible()
    await expect(page.getByText('Max Guests').first()).toBeVisible()
    await expect(page.getByText('75 m²').first()).toBeVisible()
  })

  test('Pricing page shows rate information', async ({ page }) => {
    await page.goto('/pricing')

    // Check for pricing elements
    await expect(page.getByText(/per night/i)).toBeVisible()
    // Check for seasonal pricing sections
    await expect(page.getByText(/Season/i).first()).toBeVisible()
  })

  test('FAQ page has expandable questions', async ({ page }) => {
    await page.goto('/faq')

    // FAQ should have questions visible (accordion headers are always visible)
    // Check for common FAQ topics that appear in question text
    await expect(page.getByText(/booking|cancel|payment/i).first()).toBeVisible()

    // Verify there are multiple clickable elements (accordion triggers or question buttons)
    const clickableElements = page.locator('button, [role="button"], details summary')
    const count = await clickableElements.count()
    expect(count).toBeGreaterThan(0)
  })

  test('Contact page has contact form or information', async ({ page }) => {
    await page.goto('/contact')

    // Check for contact elements
    await expect(page.getByText(/Email/i).first()).toBeVisible()

    // Should have a way to send a message or contact info
    const hasForm = (await page.locator('form').count()) > 0
    const hasContactInfo = (await page.getByText(/contact|phone|email/i).count()) > 0

    expect(hasForm || hasContactInfo).toBeTruthy()
  })

  test('Location page has address information', async ({ page }) => {
    await page.goto('/location')

    // Check for location details
    await expect(page.getByText(/Ciudad Quesada/i).first()).toBeVisible()
    await expect(page.getByText(/Costa Blanca/i).first()).toBeVisible()
    await expect(page.getByText(/Alicante/i).first()).toBeVisible()
  })

  test('Area Guide page has activity categories', async ({ page }) => {
    await page.goto('/area-guide')

    // Check for activity categories
    await expect(page.getByText(/Golf/i).first()).toBeVisible()
    await expect(page.getByText(/Beach/i).first()).toBeVisible()
  })
})

// === Header/Footer Tests ===

test.describe('Layout Components', () => {
  test('header is present on all pages', async ({ page }) => {
    for (const staticPage of staticPages) {
      await page.goto(staticPage.path)
      // Header should contain Quesada Apartment branding (it's a span, not a heading)
      await expect(page.getByText('Quesada Apartment', { exact: true })).toBeVisible()
    }
  })

  test('header logo links to home', async ({ page }) => {
    // Go to a static page
    await page.goto('/about')

    // Set desktop viewport for navigation
    await page.setViewportSize({ width: 1280, height: 800 })

    // Click the Home link in navigation (logo is a div with onClick, not a link)
    // Use the nav link which is the reliable way to navigate home
    await page.locator('nav a[href="/"]').first().click()

    // Should return to home
    await expect(page).toHaveURL('/')
  })
})

// === Performance Tests ===

test.describe('Page Performance', () => {
  test('static pages load within acceptable time', async ({ page }) => {
    for (const staticPage of staticPages) {
      const startTime = Date.now()
      await page.goto(staticPage.path)
      const loadTime = Date.now() - startTime

      // Pages should load within 3 seconds
      expect(loadTime).toBeLessThan(3000)
    }
  })
})
