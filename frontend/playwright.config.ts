import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright configuration with support for local and live environments.
 *
 * Usage:
 *   yarn test:e2e                    # Run against localhost:3000
 *   yarn test:e2e --project=live     # Run against live site
 *   yarn test:e2e:live               # Shortcut for live site tests
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    trace: 'on-first-retry',
  },
  projects: [
    // Local development tests (default)
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        baseURL: 'http://localhost:3000',
      },
    },
    // Live site integration tests
    {
      name: 'live',
      testMatch: /integration\/.+\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        baseURL: 'https://booking.levy.apro.work',
        // Longer timeouts for live site (network latency + AI responses)
        actionTimeout: 10000,
        navigationTimeout: 30000,
      },
      // No retries for integration tests - we want to see real failures
      retries: 0,
    },
  ],
  webServer: {
    command: 'yarn dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    // Don't start webserver for live tests
    ignoreHTTPSErrors: true,
  },
})
