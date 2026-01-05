#!/usr/bin/env npx tsx
/**
 * Test User Setup Script
 *
 * Creates or updates a test user in Cognito with password authentication
 * enabled for E2E test automation.
 *
 * Credentials are loaded from AWS SSM Parameter Store:
 *   /booking/e2e/test-user-email    - Email address for the test user
 *   /booking/e2e/test-user-password - Password for the test user (SecureString)
 *
 * Environment variables can override SSM values:
 *   E2E_TEST_USER_EMAIL    - Email address for the test user
 *   E2E_TEST_USER_PASSWORD - Password for the test user (min 8 chars)
 *
 * Other Configuration:
 *   NEXT_PUBLIC_COGNITO_USER_POOL_ID - Cognito User Pool ID (optional, has default)
 *   NEXT_PUBLIC_AWS_REGION - AWS region (optional, defaults to eu-west-1)
 *
 * Usage:
 *   npx tsx tests/e2e/scripts/setup-test-user.ts
 *
 * Prerequisites:
 *   - AWS credentials with cognito-idp:Admin* and ssm:GetParameter permissions
 *   - The Cognito User Pool must have ALLOW_USER_PASSWORD_AUTH enabled
 */

import {
  CognitoIdentityProviderClient,
  AdminCreateUserCommand,
  AdminSetUserPasswordCommand,
  AdminGetUserCommand,
  AdminUpdateUserAttributesCommand,
  UsernameExistsException,
} from '@aws-sdk/client-cognito-identity-provider'
import { SSMClient, GetParameterCommand } from '@aws-sdk/client-ssm'

// ============================================================================
// Configuration
// ============================================================================

const USER_POOL_ID = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID || 'eu-west-1_VEgg3Z7oI'
const AWS_REGION = process.env.NEXT_PUBLIC_AWS_REGION || 'eu-west-1'

// SSM Parameter paths
const SSM_EMAIL_PARAM = '/booking/e2e/test-user-email'
const SSM_PASSWORD_PARAM = '/booking/e2e/test-user-password'

// Credentials will be loaded from SSM or environment
let TEST_USER_EMAIL: string | undefined
let TEST_USER_PASSWORD: string | undefined

// ============================================================================
// SSM Helper
// ============================================================================

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
  } catch (error) {
    // Parameter not found is not fatal - we'll try env vars
    return undefined
  }
}

async function loadCredentials(): Promise<void> {
  console.log('🔑 Loading credentials...')

  // Try environment variables first (allows local override)
  TEST_USER_EMAIL = process.env.E2E_TEST_USER_EMAIL
  TEST_USER_PASSWORD = process.env.E2E_TEST_USER_PASSWORD

  // If not in env, try SSM
  if (!TEST_USER_EMAIL) {
    console.log('   Fetching email from SSM...')
    TEST_USER_EMAIL = await getSSMParameter(SSM_EMAIL_PARAM)
  }

  if (!TEST_USER_PASSWORD) {
    console.log('   Fetching password from SSM (SecureString)...')
    TEST_USER_PASSWORD = await getSSMParameter(SSM_PASSWORD_PARAM, true)
  }

  if (TEST_USER_EMAIL) {
    console.log(`   ✅ Email loaded: ${TEST_USER_EMAIL}`)
  }
  if (TEST_USER_PASSWORD) {
    console.log('   ✅ Password loaded')
  }
}

// ============================================================================
// Validation
// ============================================================================

function validateConfig(): void {
  if (!TEST_USER_EMAIL) {
    console.error('❌ Could not load E2E_TEST_USER_EMAIL from SSM or environment')
    console.error('   SSM path: ' + SSM_EMAIL_PARAM)
    console.error('   Or set: E2E_TEST_USER_EMAIL=test@example.com')
    process.exit(1)
  }

  if (!TEST_USER_PASSWORD) {
    console.error('❌ Could not load E2E_TEST_USER_PASSWORD from SSM or environment')
    console.error('   SSM path: ' + SSM_PASSWORD_PARAM)
    console.error('   Or set: E2E_TEST_USER_PASSWORD=YourPassword123!')
    process.exit(1)
  }

  if (TEST_USER_PASSWORD.length < 8) {
    console.error('❌ Password must be at least 8 characters')
    process.exit(1)
  }

  // Validate email format
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(TEST_USER_EMAIL)) {
    console.error('❌ Invalid email format')
    process.exit(1)
  }
}

// ============================================================================
// Main Setup Function
// ============================================================================

async function setupTestUser(): Promise<void> {
  console.log('🚀 Setting up E2E test user in Cognito\n')
  console.log(`   User Pool: ${USER_POOL_ID}`)
  console.log(`   Region: ${AWS_REGION}`)
  console.log(`   Email: ${TEST_USER_EMAIL}`)
  console.log('')

  const client = new CognitoIdentityProviderClient({ region: AWS_REGION })

  // Check if user already exists
  let userExists = false
  try {
    await client.send(
      new AdminGetUserCommand({
        UserPoolId: USER_POOL_ID,
        Username: TEST_USER_EMAIL,
      })
    )
    userExists = true
    console.log('📋 User already exists, updating password...')
  } catch (error) {
    if (error instanceof Error && error.name === 'UserNotFoundException') {
      console.log('📋 User does not exist, creating...')
    } else {
      throw error
    }
  }

  if (!userExists) {
    // Create the user
    try {
      await client.send(
        new AdminCreateUserCommand({
          UserPoolId: USER_POOL_ID,
          Username: TEST_USER_EMAIL,
          UserAttributes: [
            { Name: 'email', Value: TEST_USER_EMAIL },
            { Name: 'email_verified', Value: 'true' },
            { Name: 'name', Value: 'Automated Test User' },
          ],
          // Suppress welcome email since this is a test user
          MessageAction: 'SUPPRESS',
        })
      )
      console.log('✅ User created successfully')
    } catch (error) {
      if (error instanceof UsernameExistsException) {
        console.log('📋 User already exists (race condition), continuing...')
        userExists = true
      } else {
        throw error
      }
    }
  }

  // Set the password (works for both new and existing users)
  await client.send(
    new AdminSetUserPasswordCommand({
      UserPoolId: USER_POOL_ID,
      Username: TEST_USER_EMAIL!,
      Password: TEST_USER_PASSWORD!,
      Permanent: true, // Don't force password change
    })
  )
  console.log('✅ Password set successfully')

  // Update user attributes (for existing users that might have outdated values)
  await client.send(
    new AdminUpdateUserAttributesCommand({
      UserPoolId: USER_POOL_ID,
      Username: TEST_USER_EMAIL!,
      UserAttributes: [
        { Name: 'email_verified', Value: 'true' },
        { Name: 'name', Value: 'Automated Test User' },
      ],
    })
  )
  console.log('✅ User attributes updated (email_verified, name)')

  console.log('\n🎉 Test user setup complete!')
  console.log('\n   You can now run E2E tests with:')
  console.log(`   E2E_TEST_USER_EMAIL=${TEST_USER_EMAIL} E2E_TEST_USER_PASSWORD=*** yarn test:e2e:live`)
}

// ============================================================================
// Entry Point
// ============================================================================

async function main(): Promise<void> {
  await loadCredentials()
  validateConfig()
  await setupTestUser()
}

main()
  .then(() => {
    process.exit(0)
  })
  .catch((error) => {
    console.error('\n❌ Setup failed:', error)
    process.exit(1)
  })
