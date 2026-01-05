/**
 * Cognito Authentication Fixture for E2E Tests
 *
 * Provides authenticated Playwright contexts for tests that need real
 * Cognito authentication. Credentials are automatically loaded from
 * AWS SSM Parameter Store:
 *
 *   /booking/e2e/test-user-email    - Email address for the test user
 *   /booking/e2e/test-user-password - Password for the test user (SecureString)
 *
 * Environment variables can override SSM values:
 *   E2E_TEST_USER_EMAIL    - Email address for the test user
 *   E2E_TEST_USER_PASSWORD - Password for the test user
 *
 * Usage:
 *   import { test } from '../fixtures/auth.fixture'
 *
 *   test('authenticated test', async ({ authenticatedPage }) => {
 *     // authenticatedPage has valid Cognito session
 *   })
 */

import { test as base, expect, type Page, type BrowserContext } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'
import {
  CognitoIdentityProviderClient,
  InitiateAuthCommand,
  type InitiateAuthCommandOutput,
} from '@aws-sdk/client-cognito-identity-provider'
import { SSMClient, GetParameterCommand } from '@aws-sdk/client-ssm'

// ============================================================================
// Types
// ============================================================================

export interface AuthFixtures {
  /** Page with authenticated Cognito session */
  authenticatedPage: Page
  /** Browser context with authenticated session */
  authenticatedContext: BrowserContext
}

// ============================================================================
// Constants
// ============================================================================

/** Path to store authentication state */
const AUTH_STATE_PATH = path.join(__dirname, '..', '.auth-state', 'user.json')

/** SSM Parameter paths for credentials */
const SSM_EMAIL_PARAM = '/booking/e2e/test-user-email'
const SSM_PASSWORD_PARAM = '/booking/e2e/test-user-password'

/** Test user credentials - loaded from SSM or environment */
let TEST_USER_EMAIL = ''
let TEST_USER_PASSWORD = ''
let credentialsLoaded = false

/** Cognito configuration (must match frontend .env.local) */
const COGNITO_USER_POOL_ID = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID || 'eu-west-1_VEgg3Z7oI'
const COGNITO_CLIENT_ID = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID || '7n7e6gq90rcr6dlg7pn1jrd15l'
const AWS_REGION = process.env.NEXT_PUBLIC_AWS_REGION || 'eu-west-1'

/** Base URL for the live site */
const LIVE_SITE_URL = process.env.E2E_BASE_URL || 'https://booking.levy.apro.work'

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get a parameter from SSM Parameter Store
 */
async function getSSMParameter(name: string, withDecryption = false): Promise<string | undefined> {
  const ssmClient = new SSMClient({ region: AWS_REGION })
  try {
    const response = await ssmClient.send(
      new GetParameterCommand({
        Name: name,
        WithDecryption: withDecryption,
      })
    )
    return response.Parameter?.Value
  } catch {
    // Parameter not found is not fatal - we'll try env vars
    return undefined
  }
}

/**
 * Load credentials from SSM Parameter Store or environment variables.
 * Environment variables take precedence over SSM.
 */
async function loadCredentials(): Promise<void> {
  if (credentialsLoaded) {
    return
  }

  console.log('🔑 Loading credentials...')

  // Try environment variables first (allows local override)
  TEST_USER_EMAIL = process.env.E2E_TEST_USER_EMAIL || ''
  TEST_USER_PASSWORD = process.env.E2E_TEST_USER_PASSWORD || ''

  // If not in env, try SSM
  if (!TEST_USER_EMAIL) {
    console.log('   Fetching email from SSM...')
    TEST_USER_EMAIL = (await getSSMParameter(SSM_EMAIL_PARAM)) || ''
  }

  if (!TEST_USER_PASSWORD) {
    console.log('   Fetching password from SSM (SecureString)...')
    TEST_USER_PASSWORD = (await getSSMParameter(SSM_PASSWORD_PARAM, true)) || ''
  }

  if (TEST_USER_EMAIL) {
    console.log(`   ✅ Email loaded: ${TEST_USER_EMAIL}`)
  } else {
    console.log('   ⚠️ No email found in env or SSM')
  }

  if (TEST_USER_PASSWORD) {
    console.log('   ✅ Password loaded')
  } else {
    console.log('   ⚠️ No password found in env or SSM')
  }

  credentialsLoaded = true
}

/**
 * Check if a JWT token is expired.
 * JWTs have an `exp` claim with Unix timestamp of expiration.
 * Returns true if expired or invalid.
 */
function isTokenExpired(token: string, bufferSeconds = 60): boolean {
  try {
    // JWT format: header.payload.signature
    const parts = token.split('.')
    if (parts.length !== 3) {
      return true // Invalid JWT format
    }

    const payload = JSON.parse(Buffer.from(parts[1], 'base64').toString())
    const exp = payload.exp

    if (!exp || typeof exp !== 'number') {
      return true // No expiration claim
    }

    // Check if token expires within bufferSeconds (default 60s buffer)
    const nowSeconds = Math.floor(Date.now() / 1000)
    const isExpired = exp <= nowSeconds + bufferSeconds

    if (isExpired) {
      const expDate = new Date(exp * 1000)
      console.log(`   ⚠️  Token expired at: ${expDate.toISOString()}`)
    }

    return isExpired
  } catch {
    return true // Any parsing error = treat as expired
  }
}

/**
 * Check if we have a valid stored auth state with non-expired tokens
 */
function hasStoredAuthState(): boolean {
  if (!fs.existsSync(AUTH_STATE_PATH)) {
    return false
  }

  try {
    const state = JSON.parse(fs.readFileSync(AUTH_STATE_PATH, 'utf-8'))
    // Check if the state has the required Amplify storage keys
    // Amplify stores tokens in localStorage with specific key patterns
    const hasAmplifyTokens = state.origins?.some((origin: { localStorage?: Array<{ name: string }> }) =>
      origin.localStorage?.some((item: { name: string }) =>
        item.name.includes('CognitoIdentityServiceProvider') &&
        item.name.includes('idToken')
      )
    )

    if (!hasAmplifyTokens) {
      return false
    }

    // Also check if tokens are expired
    const tokens = extractTokensFromStoredState()
    if (tokens && isTokenExpired(tokens.idToken)) {
      console.log('📂 Stored auth state has expired tokens, will re-authenticate')
      return false
    }

    return true
  } catch {
    return false
  }
}

/**
 * Extract tokens from stored auth state file.
 * Returns tokens that can be passed directly to addInitScript.
 */
function extractTokensFromStoredState(): { idToken: string; accessToken: string; username: string } | null {
  if (!fs.existsSync(AUTH_STATE_PATH)) {
    return null
  }

  try {
    const state = JSON.parse(fs.readFileSync(AUTH_STATE_PATH, 'utf-8'))
    const keyPrefix = `CognitoIdentityServiceProvider.${COGNITO_CLIENT_ID}`

    // Find the origin with our localStorage data
    for (const origin of state.origins || []) {
      const localStorage = origin.localStorage || []

      // Find LastAuthUser
      const lastAuthUserItem = localStorage.find(
        (item: { name: string }) => item.name === `${keyPrefix}.LastAuthUser`
      )
      if (!lastAuthUserItem) continue

      const username = lastAuthUserItem.value

      // Find idToken and accessToken
      const idTokenItem = localStorage.find(
        (item: { name: string }) => item.name === `${keyPrefix}.${username}.idToken`
      )
      const accessTokenItem = localStorage.find(
        (item: { name: string }) => item.name === `${keyPrefix}.${username}.accessToken`
      )

      if (idTokenItem) {
        return {
          idToken: idTokenItem.value,
          accessToken: accessTokenItem?.value || '',
          username,
        }
      }
    }

    return null
  } catch {
    return null
  }
}

/**
 * Authenticate programmatically using username/password.
 * Uses USER_PASSWORD_AUTH flow with Cognito directly.
 *
 * Returns tokens in Amplify localStorage format for injection into browser.
 */
async function authenticateWithPassword(): Promise<{
  idToken: string
  accessToken: string
  refreshToken: string
  username: string
}> {
  if (!TEST_USER_EMAIL || !TEST_USER_PASSWORD) {
    throw new Error(
      'Password authentication requires credentials. Set E2E_TEST_USER_EMAIL and E2E_TEST_USER_PASSWORD env vars, ' +
      'or configure SSM parameters at /booking/e2e/test-user-email and /booking/e2e/test-user-password'
    )
  }

  console.log(`🔐 Authenticating via password for: ${TEST_USER_EMAIL}`)

  const client = new CognitoIdentityProviderClient({ region: AWS_REGION })

  const response: InitiateAuthCommandOutput = await client.send(
    new InitiateAuthCommand({
      AuthFlow: 'USER_PASSWORD_AUTH',
      ClientId: COGNITO_CLIENT_ID,
      AuthParameters: {
        USERNAME: TEST_USER_EMAIL,
        PASSWORD: TEST_USER_PASSWORD,
      },
    })
  )

  if (!response.AuthenticationResult) {
    throw new Error('Authentication failed - no tokens returned')
  }

  const { IdToken, AccessToken, RefreshToken } = response.AuthenticationResult

  if (!IdToken || !AccessToken) {
    throw new Error('Authentication failed - missing required tokens')
  }

  console.log('✅ Password authentication successful')

  return {
    idToken: IdToken,
    accessToken: AccessToken,
    refreshToken: RefreshToken || '',
    username: TEST_USER_EMAIL,
  }
}

/**
 * Inject Cognito tokens into browser for E2E testing.
 *
 * Uses two mechanisms:
 * 1. window.__MOCK_AUTH__ - Bypasses Amplify fetchAuthSession() entirely
 *    (This is the primary mechanism used by ensureValidIdToken() in auth.ts)
 * 2. localStorage - For Amplify's internal storage (backup)
 *
 * The mock mechanism is more reliable because it doesn't depend on
 * Amplify v6 storage format compatibility.
 */
async function injectAmplifyTokens(
  page: Page,
  tokens: {
    idToken: string
    accessToken: string
    refreshToken: string
    username: string
  }
): Promise<void> {
  // Parse idToken to get the 'sub' (Cognito user ID)
  const idTokenPayload = JSON.parse(
    Buffer.from(tokens.idToken.split('.')[1], 'base64').toString()
  )
  const cognitoUsername = idTokenPayload.sub || tokens.username

  // Amplify v6 localStorage key format (for backup)
  const keyPrefix = `CognitoIdentityServiceProvider.${COGNITO_CLIENT_ID}`

  await page.evaluate(
    ({ keyPrefix, cognitoUsername, tokens }) => {
      // PRIMARY: Set window.__MOCK_AUTH__ for ensureValidIdToken() to use
      // This bypasses Amplify's fetchAuthSession() entirely
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (window as any).__MOCK_AUTH__ = {
        tokens: {
          idToken: {
            toString: () => tokens.idToken,
          },
          accessToken: {
            toString: () => tokens.accessToken,
          },
        },
        user: {
          username: cognitoUsername,
        },
      }

      // BACKUP: Also set localStorage for Amplify (if needed elsewhere)
      localStorage.setItem(`${keyPrefix}.${cognitoUsername}.idToken`, tokens.idToken)
      localStorage.setItem(`${keyPrefix}.${cognitoUsername}.accessToken`, tokens.accessToken)
      localStorage.setItem(`${keyPrefix}.${cognitoUsername}.refreshToken`, tokens.refreshToken)
      localStorage.setItem(`${keyPrefix}.${cognitoUsername}.clockDrift`, '0')
      localStorage.setItem(`${keyPrefix}.LastAuthUser`, cognitoUsername)
    },
    { keyPrefix, cognitoUsername, tokens }
  )

  console.log('💉 Tokens injected (window.__MOCK_AUTH__ + localStorage)')
}

/**
 * Perform EMAIL_OTP authentication flow via UI.
 * This requires manual OTP entry during test execution.
 */
async function authenticateViaUI(page: Page): Promise<void> {
  if (!TEST_USER_EMAIL) {
    throw new Error(
      'E2E_TEST_USER_EMAIL environment variable not set. ' +
      'Set it to a valid test user email in Cognito.'
    )
  }

  console.log(`\n🔐 Starting EMAIL_OTP authentication for: ${TEST_USER_EMAIL}`)

  // Navigate to the profile page which shows the auth form
  await page.goto(`${LIVE_SITE_URL}/profile`)

  // Wait for the auth form to load
  await page.waitForLoadState('networkidle')

  // Look for email input (the sign-in form)
  const emailInput = page.getByLabel(/email/i).or(page.getByPlaceholder(/email/i))

  // If already authenticated, we might see the profile page
  const profileHeading = page.getByRole('heading', { name: /profile/i })
  if (await profileHeading.isVisible({ timeout: 2000 }).catch(() => false)) {
    console.log('✅ Already authenticated')
    return
  }

  // Fill in email and submit
  await emailInput.fill(TEST_USER_EMAIL)

  // Click sign in / send code button
  const signInButton = page.getByRole('button', { name: /sign in|send code|continue/i })
  await signInButton.click()

  // Wait for OTP input to appear
  console.log('📧 OTP code sent to email. Waiting for code entry...')
  console.log('   Enter the code in the browser within 60 seconds')

  // Wait for either OTP input or authenticated state
  const otpInput = page.getByLabel(/code|otp|verification/i).or(
    page.getByPlaceholder(/code|otp/i)
  )

  // Wait for OTP input to be visible (user needs to enter code manually)
  await expect(otpInput).toBeVisible({ timeout: 10000 })

  // Wait for authentication to complete (user enters OTP manually)
  // This gives the user 60 seconds to check email and enter the code
  await expect(async () => {
    const isAuthenticated = await page.evaluate(() => {
      // Check for Amplify auth tokens in localStorage
      const keys = Object.keys(localStorage)
      return keys.some(key =>
        key.includes('CognitoIdentityServiceProvider') &&
        key.includes('idToken')
      )
    })
    expect(isAuthenticated).toBe(true)
  }).toPass({ timeout: 60000, intervals: [1000] })

  console.log('✅ Authentication successful')
}

/**
 * Save current authentication state to file
 */
async function saveAuthState(context: BrowserContext): Promise<void> {
  const dir = path.dirname(AUTH_STATE_PATH)
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true })
  }

  const state = await context.storageState()
  fs.writeFileSync(AUTH_STATE_PATH, JSON.stringify(state, null, 2))
  console.log(`💾 Auth state saved to: ${AUTH_STATE_PATH}`)
}

// ============================================================================
// Fixture Definition
// ============================================================================

/**
 * Extended test with authentication fixtures.
 *
 * @example
 * ```ts
 * import { test } from '../fixtures/auth.fixture'
 *
 * test('test with auth', async ({ authenticatedPage }) => {
 *   await authenticatedPage.goto('/profile')
 *   // Page is already authenticated
 * })
 * ```
 */
export const test = base.extend<AuthFixtures>({
  // Create authenticated context
  authenticatedContext: async ({ browser }, use) => {
    // Load credentials from SSM or environment
    await loadCredentials()

    let context: BrowserContext

    // Try to reuse stored state first
    const storedTokens = extractTokensFromStoredState()
    if (hasStoredAuthState() && storedTokens) {
      console.log('📂 Using stored auth state')
      console.log(`   Token username: ${storedTokens.username}`)
      context = await browser.newContext({
        storageState: AUTH_STATE_PATH,
        baseURL: LIVE_SITE_URL,
      })

      // Add init script to set window.__MOCK_AUTH__ on every page load
      // CRITICAL: Pass tokens directly instead of reading from localStorage
      // because init scripts run before localStorage is fully populated
      await context.addInitScript(
        ({ idToken, accessToken, username }) => {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          ;(window as any).__MOCK_AUTH__ = {
            tokens: {
              idToken: { toString: () => idToken },
              accessToken: { toString: () => accessToken },
            },
            user: { username },
          }
        },
        storedTokens
      )
    } else if (TEST_USER_PASSWORD) {
      // CI mode: Use password authentication (no manual intervention)
      console.log('🔄 Using password authentication (CI mode)')

      // First, authenticate via Cognito API to get tokens
      const tokens = await authenticateWithPassword()

      // Parse idToken to get the 'sub' (Cognito user ID)
      const idTokenPayload = JSON.parse(
        Buffer.from(tokens.idToken.split('.')[1], 'base64').toString()
      )
      const cognitoUsername = idTokenPayload.sub || tokens.username

      // Create context with init script that has tokens embedded
      context = await browser.newContext({
        baseURL: LIVE_SITE_URL,
      })

      // Add init script with tokens passed directly (not from localStorage)
      // This ensures window.__MOCK_AUTH__ is set on every page load
      await context.addInitScript(
        ({ idToken, accessToken, username }) => {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          ;(window as any).__MOCK_AUTH__ = {
            tokens: {
              idToken: { toString: () => idToken },
              accessToken: { toString: () => accessToken },
            },
            user: { username },
          }
        },
        { idToken: tokens.idToken, accessToken: tokens.accessToken, username: cognitoUsername }
      )

      // Now create a page, inject localStorage, and save state
      const page = await context.newPage()
      await page.goto(LIVE_SITE_URL)
      await page.waitForLoadState('domcontentloaded')

      // Inject localStorage for Amplify (backup) and to persist to auth state file
      await injectAmplifyTokens(page, tokens)

      // Save auth state (includes localStorage which we can reuse later)
      await saveAuthState(context)
      await page.close()
    } else {
      // Manual mode: Use EMAIL_OTP flow (requires manual code entry)
      console.log('🔄 No stored auth state, performing fresh login (EMAIL_OTP)')
      context = await browser.newContext({
        baseURL: LIVE_SITE_URL,
      })

      const page = await context.newPage()
      await authenticateViaUI(page)
      await saveAuthState(context)
      await page.close()
    }

    await use(context)
    await context.close()
  },

  // Create authenticated page from context
  authenticatedPage: async ({ authenticatedContext }, use) => {
    const page = await authenticatedContext.newPage()
    await use(page)
    await page.close()
  },
})

export { expect }

// ============================================================================
// Standalone Auth Setup Script
// ============================================================================

/**
 * Run this script standalone to set up authentication state:
 *
 *   npx ts-node tests/e2e/fixtures/auth.fixture.ts
 *
 * Or via test:
 *
 *   yarn test:e2e --project=live --grep "setup auth"
 */
if (require.main === module) {
  const { chromium } = require('@playwright/test')

  async function setup() {
    console.log('🚀 Setting up authentication state for E2E tests\n')

    // Load credentials from SSM or environment
    await loadCredentials()

    if (!TEST_USER_EMAIL) {
      console.error('❌ Could not load E2E_TEST_USER_EMAIL from SSM or environment')
      console.error('   SSM path: ' + SSM_EMAIL_PARAM)
      console.error('   Or set: E2E_TEST_USER_EMAIL=test@example.com')
      process.exit(1)
    }

    // Use headless for password auth, visible for OTP
    const headless = !!TEST_USER_PASSWORD
    console.log(`   Mode: ${TEST_USER_PASSWORD ? 'Password (CI)' : 'EMAIL_OTP (manual)'}`)
    console.log(`   Headless: ${headless}\n`)

    const browser = await chromium.launch({ headless })
    const context = await browser.newContext({
      baseURL: LIVE_SITE_URL,
    })
    const page = await context.newPage()

    try {
      if (TEST_USER_PASSWORD) {
        // Password auth mode - fully automated
        await page.goto(LIVE_SITE_URL)
        await page.waitForLoadState('domcontentloaded')
        const tokens = await authenticateWithPassword()
        await injectAmplifyTokens(page, tokens)
        await page.reload()
        await page.waitForLoadState('networkidle')
      } else {
        // EMAIL_OTP mode - requires manual code entry
        await authenticateViaUI(page)
      }

      await saveAuthState(context)
      console.log('\n✅ Auth setup complete! You can now run tests with stored state.')
    } catch (error) {
      console.error('\n❌ Auth setup failed:', error)
      process.exit(1)
    } finally {
      await browser.close()
    }
  }

  setup()
}
