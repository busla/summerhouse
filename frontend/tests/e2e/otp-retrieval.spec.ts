/**
 * OTP Retrieval E2E Test
 *
 * Tests the OTP Interceptor Lambda + DynamoDB flow for E2E test automation.
 * This validates US1 (P1) from specs/019-e2e-email-otp/spec.md:
 * "E2E test retrieves OTP code"
 *
 * Prerequisites:
 * - enable_otp_interceptor = true in dev terraform.tfvars.json
 * - OTP Interceptor Lambda deployed and wired to Cognito Custom Message trigger
 * - DynamoDB verification_codes table exists
 */

import { test, expect } from '@playwright/test'
import {
  CognitoIdentityProviderClient,
  InitiateAuthCommand,
  SignUpCommand,
  AdminDeleteUserCommand,
} from '@aws-sdk/client-cognito-identity-provider'
import { getOtpForEmail, generateTestEmail, isTestEmail } from './utils/otp-helper'

// Cognito configuration matching dev deployment
const AWS_REGION = process.env.NEXT_PUBLIC_AWS_REGION || 'eu-west-1'
const COGNITO_USER_POOL_ID = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID || 'eu-west-1_VEgg3Z7oI'
const COGNITO_CLIENT_ID = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID || '7n7e6gq90rcr6dlg7pn1jrd15l'

test.describe('OTP Interceptor', () => {
  let cognitoClient: CognitoIdentityProviderClient
  let testEmail: string

  test.beforeAll(() => {
    cognitoClient = new CognitoIdentityProviderClient({ region: AWS_REGION })
  })

  test.beforeEach(() => {
    // Generate unique test email for each test
    testEmail = generateTestEmail()
  })

  test.afterEach(async () => {
    // Cleanup: Delete test user from Cognito if created
    try {
      await cognitoClient.send(
        new AdminDeleteUserCommand({
          UserPoolId: COGNITO_USER_POOL_ID,
          Username: testEmail,
        })
      )
    } catch {
      // User might not exist, ignore cleanup errors
    }
  })

  test('test email pattern validation', () => {
    // Valid test email patterns
    expect(isTestEmail('test+abc123@summerhouse.com')).toBe(true)
    expect(isTestEmail('test+1234567890-xyz@summerhouse.com')).toBe(true)
    expect(isTestEmail('anything@test.summerhouse.com')).toBe(true)
    expect(isTestEmail('user+tag@test.summerhouse.com')).toBe(true)

    // Invalid patterns - should not be intercepted
    expect(isTestEmail('user@summerhouse.com')).toBe(false)
    expect(isTestEmail('test@summerhouse.com')).toBe(false) // No + suffix
    expect(isTestEmail('user@gmail.com')).toBe(false)
    expect(isTestEmail('test+abc@otherdomain.com')).toBe(false)
  })

  test('generates unique test emails', () => {
    const email1 = generateTestEmail()
    const email2 = generateTestEmail()

    expect(email1).not.toBe(email2)
    expect(isTestEmail(email1)).toBe(true)
    expect(isTestEmail(email2)).toBe(true)
  })

  test('retrieves OTP code after Cognito EMAIL_OTP initiation', async () => {
    // Skip if running against live environment without interceptor
    test.skip(
      process.env.CI === 'true' && !process.env.ENABLE_OTP_TESTS,
      'OTP tests require interceptor Lambda'
    )

    // Step 1: Create user in Cognito (triggers confirmation email with OTP)
    // Note: We use SignUp which auto-triggers email verification
    const tempPassword = `TempPass123!${Date.now()}`

    try {
      await cognitoClient.send(
        new SignUpCommand({
          ClientId: COGNITO_CLIENT_ID,
          Username: testEmail,
          Password: tempPassword,
          UserAttributes: [{ Name: 'email', Value: testEmail }],
        })
      )
    } catch (error: unknown) {
      // If user already exists from a failed test, that's OK
      if ((error as Error).name !== 'UsernameExistsException') {
        throw error
      }
    }

    // Step 2: Initiate USER_AUTH flow to trigger EMAIL_OTP
    // This should trigger Custom Message Lambda which intercepts the OTP
    const authResponse = await cognitoClient.send(
      new InitiateAuthCommand({
        AuthFlow: 'USER_AUTH',
        ClientId: COGNITO_CLIENT_ID,
        AuthParameters: {
          USERNAME: testEmail,
          PREFERRED_CHALLENGE: 'EMAIL_OTP',
        },
      })
    )

    // Verify we got EMAIL_OTP challenge
    expect(authResponse.ChallengeName).toBe('EMAIL_OTP')

    // Step 3: Retrieve OTP from DynamoDB via our helper
    // The OTP Interceptor Lambda should have stored it
    const otp = await getOtpForEmail(testEmail)

    // Step 4: Verify OTP format (6 digits)
    expect(otp).toMatch(/^\d{6}$/)

    console.log(`✅ Successfully retrieved OTP for ${testEmail}: ${otp}`)
  })

  test('fails gracefully for non-test emails', async () => {
    const nonTestEmail = 'user@example.com'

    await expect(getOtpForEmail(nonTestEmail)).rejects.toThrow(
      /does not match test email patterns/
    )
  })

  test('times out when OTP not available', async () => {
    // Use a test email that won't have an OTP (never triggered auth)
    const unusedEmail = generateTestEmail()

    // Use short timeout for faster test
    await expect(getOtpForEmail(unusedEmail, 1000)).rejects.toThrow(/OTP not found.*within.*timeout/)
  })
})
