import { test as authTest, expect } from './fixtures/auth.fixture'
import { test } from '@playwright/test'

/**
 * Debug test to check if Authorization header length causes 403 errors.
 *
 * Hypothesis: WAF or CloudFront is blocking requests with long Authorization headers.
 * - Short token: Works (401)
 * - Long token (like real JWT): May fail (403)
 */
test.skip('check if Authorization header length causes 403', async ({ page }) => {
  await page.goto('https://booking.levy.apro.work/book')
  await page.waitForTimeout(2000)

  // Generate a fake JWT-like token of similar length to real JWTs (~1500 chars)
  const longToken = 'eyJ' + 'a'.repeat(500) + '.' + 'b'.repeat(500) + '.' + 'c'.repeat(500)

  console.log(`\n=== Testing Authorization Header Length ===`)
  console.log(`Token length: ${longToken.length} characters`)

  // Test with long token
  const result = await page.evaluate(async (token) => {
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
      body: text.substring(0, 500),
      headers: Object.fromEntries(response.headers.entries())
    }
  }, longToken)

  console.log(`\n=== Long Token Test Result ===`)
  console.log(`Status: ${result.status}`)
  console.log(`Body: ${result.body}`)

  // If we get 403 with long token, that's the issue
  if (result.status === 403 && result.body.includes('403')) {
    console.log('\n❌ CONFIRMED: Long Authorization header triggers 403!')
  } else if (result.status === 401) {
    console.log('\n✓ Long token reaches API (401 - auth error from API)')
  }

  // Now test with real JWT from the auth fixture token
  // We'll check different token lengths
  const tokenLengths = [100, 500, 1000, 1500, 2000]

  console.log('\n=== Testing Various Token Lengths ===')

  for (const length of tokenLengths) {
    const testToken = 'eyJ' + 'x'.repeat(length)

    const testResult = await page.evaluate(async (token) => {
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
      return { status: response.status }
    }, testToken)

    console.log(`Token length ${length + 3}: Status ${testResult.status}`)
  }
})
