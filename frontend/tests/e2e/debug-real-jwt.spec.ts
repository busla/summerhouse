import { test as authTest, expect } from './fixtures/auth.fixture'
import { test } from '@playwright/test'

/**
 * Debug test to compare direct fetch with REAL JWT token vs SDK behavior.
 *
 * Previous test confirmed: Fake token lengths (100-2000 chars) all return 401 (working).
 * This test checks: Does a REAL JWT token trigger 403 somehow?
 */
authTest('compare real JWT fetch via __MOCK_AUTH__', async ({ authenticatedPage }) => {
  // Navigate to the booking page first (same as real E2E tests)
  await authenticatedPage.goto('https://booking.levy.apro.work/book')
  await authenticatedPage.waitForTimeout(2000)

  // Test 1: Check what window.__MOCK_AUTH__ contains
  const mockAuthState = await authenticatedPage.evaluate(() => {
    const mock = (window as any).__MOCK_AUTH__
    if (!mock) return { exists: false }
    const idToken = mock.tokens?.idToken?.toString() ?? null
    return {
      exists: true,
      hasTokens: !!mock.tokens,
      hasIdToken: !!idToken,
      idTokenLength: idToken?.length ?? 0,
      idTokenStart: idToken?.substring(0, 80) ?? ''
    }
  })

  console.log(`\n=== window.__MOCK_AUTH__ State ===`)
  console.log(JSON.stringify(mockAuthState, null, 2))

  if (!mockAuthState.hasIdToken) {
    console.log('❌ No idToken in __MOCK_AUTH__ - cannot proceed')
    return
  }

  console.log(`\n=== Testing with REAL JWT Token ===`)
  console.log(`Token length: ${mockAuthState.idTokenLength} characters`)

  // Test 2: Make direct fetch with token from window.__MOCK_AUTH__
  const directResult = await authenticatedPage.evaluate(async () => {
    const mock = (window as any).__MOCK_AUTH__
    const token = mock?.tokens?.idToken?.toString()

    const response = await fetch('/api/reservations', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        check_in: '2026-06-16',
        check_out: '2026-06-30',
        num_adults: 2,
        num_children: 0,
      })
    })
    const text = await response.text()
    return {
      status: response.status,
      body: text.substring(0, 800),
      headers: Object.fromEntries(response.headers.entries())
    }
  })

  console.log(`\n=== Direct Fetch Result (with Bearer prefix) ===`)
  console.log(`Status: ${directResult.status}`)
  console.log(`Body: ${directResult.body}`)
  console.log(`Response headers: ${JSON.stringify(directResult.headers, null, 2)}`)

  // Summary
  console.log(`\n=== SUMMARY ===`)
  if (directResult.status === 401) {
    console.log('✓ Direct fetch with real JWT: 401 (API reached, auth rejected)')
  } else if (directResult.status === 403) {
    console.log('❌ Direct fetch with real JWT: 403 (blocked before API!)')
    if (directResult.body.includes('<!DOCTYPE') || directResult.body.includes('<html')) {
      console.log('   Response is HTML - CloudFront/WAF blocking')
    }
  } else if (directResult.status === 200 || directResult.status === 201) {
    console.log('✓ Direct fetch with real JWT: SUCCESS!')
  } else {
    console.log(`? Direct fetch with real JWT: ${directResult.status}`)
  }
})

/**
 * Test using Playwright's route interception to see exact request details
 */
authTest('capture exact request/response details', async ({ authenticatedPage }) => {
  // Set up request/response logging BEFORE navigation
  authenticatedPage.on('request', request => {
    if (request.url().includes('/api/reservations')) {
      console.log('\n=== INTERCEPTED REQUEST ===')
      console.log('URL:', request.url())
      console.log('Method:', request.method())
      console.log('Headers:', JSON.stringify(request.headers(), null, 2))
      console.log('PostData:', request.postData())
    }
  })

  authenticatedPage.on('response', response => {
    if (response.url().includes('/api/reservations')) {
      console.log('\n=== INTERCEPTED RESPONSE ===')
      console.log('Status:', response.status())
      console.log('Headers:', JSON.stringify(response.headers(), null, 2))
    }
  })

  await authenticatedPage.goto('https://booking.levy.apro.work/book')
  await authenticatedPage.waitForTimeout(2000)

  // Make the request
  const result = await authenticatedPage.evaluate(async () => {
    const mock = (window as any).__MOCK_AUTH__
    const token = mock?.tokens?.idToken?.toString()

    const response = await fetch('/api/reservations', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        check_in: '2026-06-16',
        check_out: '2026-06-30',
        num_adults: 2,
        num_children: 0,
      })
    })
    return {
      status: response.status,
      body: (await response.text()).substring(0, 500),
    }
  })

  console.log('\n=== EVALUATE RESULT ===')
  console.log(`Status: ${result.status}`)
  console.log(`Body: ${result.body}`)
})

/**
 * Test without Authorization header to see baseline behavior
 */
test('test without auth header (baseline)', async ({ page }) => {
  await page.goto('https://booking.levy.apro.work/book')
  await page.waitForTimeout(2000)

  console.log(`\n=== Testing WITHOUT Authorization Header (Baseline) ===`)

  const result = await page.evaluate(async () => {
    const response = await fetch('/api/reservations', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        check_in: '2026-06-16',
        check_out: '2026-06-30',
        num_adults: 2,
        num_children: 0,
      })
    })
    return {
      status: response.status,
      body: (await response.text()).substring(0, 500),
    }
  })

  console.log(`Status: ${result.status}`)
  console.log(`Body: ${result.body}`)

  if (result.body.includes('<!DOCTYPE') || result.body.includes('<html')) {
    console.log('❌ Got HTML response - CloudFront/WAF blocking')
  } else {
    console.log('✓ Got API response (JSON)')
  }
})
