/**
 * OTP Helper for E2E Tests
 *
 * Retrieves OTP codes intercepted by the OTP Interceptor Lambda from DynamoDB.
 * Used to automate Cognito EMAIL_OTP authentication in E2E tests.
 *
 * @see specs/019-e2e-email-otp/spec.md
 * @see backend/lambdas/otp-interceptor/handler.py
 */

import { DynamoDBClient, GetItemCommand } from '@aws-sdk/client-dynamodb'

// Configuration from environment or defaults matching dev deployment
const AWS_REGION = process.env.NEXT_PUBLIC_AWS_REGION || 'eu-west-1'
const VERIFICATION_CODES_TABLE =
  process.env.VERIFICATION_CODES_TABLE || 'booking-dev-data-verification-codes'

// Polling configuration per spec FR-003 (5 second window)
const DEFAULT_TIMEOUT_MS = 5000
const POLL_INTERVAL_MS = 500
const MAX_RETRIES = Math.ceil(DEFAULT_TIMEOUT_MS / POLL_INTERVAL_MS)

// Test email patterns - must match Lambda's TEST_EMAIL_PATTERNS
const TEST_EMAIL_PATTERNS = [
  /^test\+.+@summerhouse\.com$/, // test+{anything}@summerhouse.com
  /^.+@test\.summerhouse\.com$/, // *@test.summerhouse.com
]

/**
 * Validates that an email matches the test email patterns.
 * Only test emails are intercepted by the OTP Interceptor Lambda.
 */
export function isTestEmail(email: string): boolean {
  return TEST_EMAIL_PATTERNS.some((pattern) => pattern.test(email))
}

/**
 * Generates a unique test email address for E2E tests.
 * Format: test+{timestamp}-{random}@summerhouse.com
 */
export function generateTestEmail(): string {
  const timestamp = Date.now()
  const random = Math.random().toString(36).substring(2, 8)
  return `test+${timestamp}-${random}@summerhouse.com`
}

interface OtpResult {
  code: string
  triggerSource: string
  createdAt: string
  expiresAt: number
}

/**
 * Retrieves the latest OTP code for a given email from DynamoDB.
 *
 * The OTP Interceptor Lambda stores intercepted codes with structure:
 * - email (S): Partition key
 * - code (S): 6-digit OTP code
 * - trigger_source (S): Cognito trigger type
 * - created_at (S): ISO timestamp
 * - expires_at (N): Unix timestamp TTL
 *
 * @param email - Email address to retrieve OTP for (must match test patterns)
 * @param timeoutMs - Maximum time to wait for OTP (default: 5000ms per spec)
 * @returns The 6-digit OTP code
 * @throws Error if email doesn't match test patterns or OTP not found within timeout
 */
export async function getOtpForEmail(
  email: string,
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<string> {
  // Validate test email pattern
  if (!isTestEmail(email)) {
    throw new Error(
      `Email "${email}" does not match test email patterns. ` +
        `Use test+*@summerhouse.com or *@test.summerhouse.com`
    )
  }

  const client = new DynamoDBClient({ region: AWS_REGION })
  const maxRetries = Math.ceil(timeoutMs / POLL_INTERVAL_MS)

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const result = await queryOtp(client, email)
      if (result) {
        // Verify OTP hasn't expired
        const now = Math.floor(Date.now() / 1000)
        if (result.expiresAt > now) {
          return result.code
        }
        // OTP expired, continue polling for a fresh one
        console.log(`[OTP Helper] Found expired OTP for ${email}, waiting for fresh code...`)
      }
    } catch (error) {
      // Log but continue polling - might be transient
      console.error(`[OTP Helper] Query error (attempt ${attempt}):`, error)
    }

    // Wait before next poll (except on last attempt)
    if (attempt < maxRetries) {
      await sleep(POLL_INTERVAL_MS)
    }
  }

  throw new Error(`OTP not found for ${email} within ${timeoutMs}ms timeout`)
}

/**
 * Queries DynamoDB for the OTP code associated with an email.
 */
async function queryOtp(client: DynamoDBClient, email: string): Promise<OtpResult | null> {
  const command = new GetItemCommand({
    TableName: VERIFICATION_CODES_TABLE,
    Key: {
      email: { S: email },
    },
  })

  const response = await client.send(command)

  if (!response.Item) {
    return null
  }

  return {
    code: response.Item.code?.S || '',
    triggerSource: response.Item.trigger_source?.S || '',
    createdAt: response.Item.created_at?.S || '',
    expiresAt: parseInt(response.Item.expires_at?.N || '0', 10),
  }
}

/**
 * Sleep helper for polling intervals.
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * Clears the OTP for a given email (useful for test cleanup).
 * Note: TTL auto-deletes after 5 minutes, so this is optional.
 */
export async function clearOtpForEmail(email: string): Promise<void> {
  const { DynamoDBClient, DeleteItemCommand } = await import('@aws-sdk/client-dynamodb')

  const client = new DynamoDBClient({ region: AWS_REGION })
  const command = new DeleteItemCommand({
    TableName: VERIFICATION_CODES_TABLE,
    Key: {
      email: { S: email },
    },
  })

  await client.send(command)
}
