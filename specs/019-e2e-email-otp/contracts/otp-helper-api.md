# Contract: OTP Helper API (E2E Test Utility)

**Feature**: 019-e2e-email-otp | **Version**: 1.0.0

## Overview

This contract defines the TypeScript API for the E2E test helper that retrieves OTP codes from DynamoDB.

## Module Location

```
frontend/tests/e2e/utils/otp-helper.ts
```

## API Specification

### getOtpCode

Retrieves the OTP code for a given email address with polling and timeout.

```typescript
/**
 * Retrieves the OTP code for a test email from DynamoDB.
 *
 * Polls the verification_codes table until the OTP is found or timeout is reached.
 *
 * @param email - The test email address (must match test pattern)
 * @param options - Configuration options
 * @returns The 6-digit OTP code
 * @throws OtpNotFoundError if code not found within timeout
 * @throws OtpExpiredError if code found but already expired
 *
 * @example
 * ```typescript
 * const code = await getOtpCode('test+abc123@summerhouse.com');
 * console.log(code); // "123456"
 * ```
 */
export async function getOtpCode(
  email: string,
  options?: GetOtpOptions
): Promise<string>;

interface GetOtpOptions {
  /**
   * Maximum time to wait for OTP in milliseconds.
   * @default 5000
   */
  timeoutMs?: number;

  /**
   * Polling interval in milliseconds.
   * @default 200
   */
  pollIntervalMs?: number;

  /**
   * Minimum age of OTP to accept (prevents stale codes).
   * ISO 8601 timestamp or Date object.
   * @default undefined (accepts any code)
   */
  createdAfter?: string | Date;
}
```

### clearOtpCode

Deletes an OTP code from DynamoDB (cleanup utility).

```typescript
/**
 * Deletes the OTP code for a test email from DynamoDB.
 *
 * Use for test cleanup to ensure subsequent tests get fresh codes.
 *
 * @param email - The test email address
 * @returns true if deleted, false if not found
 *
 * @example
 * ```typescript
 * await clearOtpCode('test+abc123@summerhouse.com');
 * ```
 */
export async function clearOtpCode(email: string): Promise<boolean>;
```

### generateTestEmail

Generates a unique test email address.

```typescript
/**
 * Generates a unique test email address for E2E tests.
 *
 * @param prefix - Optional prefix for identification (default: "e2e")
 * @returns Unique test email address
 *
 * @example
 * ```typescript
 * const email = generateTestEmail('booking-flow');
 * // "test+booking-flow-550e8400-e29b-41d4-a716-446655440000@summerhouse.com"
 * ```
 */
export function generateTestEmail(prefix?: string): string;
```

## Error Types

```typescript
/**
 * Thrown when OTP code is not found within the timeout period.
 */
export class OtpNotFoundError extends Error {
  constructor(
    public readonly email: string,
    public readonly timeoutMs: number
  ) {
    super(`OTP code not found for ${email} within ${timeoutMs}ms`);
    this.name = 'OtpNotFoundError';
  }
}

/**
 * Thrown when OTP code is found but has already expired.
 */
export class OtpExpiredError extends Error {
  constructor(
    public readonly email: string,
    public readonly expiresAt: Date
  ) {
    super(`OTP code for ${email} expired at ${expiresAt.toISOString()}`);
    this.name = 'OtpExpiredError';
  }
}
```

## Configuration

The helper reads configuration from environment variables:

```typescript
interface OtpHelperConfig {
  /**
   * DynamoDB table name for verification codes.
   * @env VERIFICATION_CODES_TABLE
   */
  tableName: string;

  /**
   * AWS region for DynamoDB client.
   * @env AWS_REGION
   */
  region: string;
}
```

## Usage Examples

### Basic Usage

```typescript
import { getOtpCode, generateTestEmail } from '../utils/otp-helper';

test('authenticate with real OTP', async ({ page }) => {
  const email = generateTestEmail();

  // Trigger OTP generation
  await page.fill('[data-testid="email-input"]', email);
  await page.click('[data-testid="submit-email"]');

  // Retrieve OTP (polls with default timeout)
  const code = await getOtpCode(email);

  // Enter OTP
  await page.fill('[data-testid="otp-input"]', code);
  await page.click('[data-testid="verify-otp"]');
});
```

### With Custom Options

```typescript
import { getOtpCode, generateTestEmail } from '../utils/otp-helper';

test('OTP resend flow', async ({ page }) => {
  const email = generateTestEmail('resend-test');
  const testStartTime = new Date();

  // Get first OTP
  await triggerOtp(page, email);
  const firstCode = await getOtpCode(email);

  // Click resend
  await page.click('[data-testid="resend-code"]');

  // Get new OTP (ignore the old one)
  const secondCode = await getOtpCode(email, {
    createdAfter: testStartTime,
    timeoutMs: 10000
  });

  expect(secondCode).not.toBe(firstCode);
});
```

### Error Handling

```typescript
import { getOtpCode, OtpNotFoundError, OtpExpiredError } from '../utils/otp-helper';

test('handles missing OTP gracefully', async ({ page }) => {
  try {
    await getOtpCode('test+nonexistent@summerhouse.com', {
      timeoutMs: 1000
    });
  } catch (error) {
    if (error instanceof OtpNotFoundError) {
      console.log(`Email: ${error.email}, Timeout: ${error.timeoutMs}ms`);
    }
    throw error;
  }
});
```

## Implementation Notes

1. **DynamoDB Client**: Use `@aws-sdk/client-dynamodb` with singleton pattern
2. **Polling**: Use exponential backoff or fixed interval (200ms default)
3. **Credentials**: Rely on AWS SDK credential chain (CI provides via env vars)
4. **Logging**: Log attempts in debug mode for troubleshooting
