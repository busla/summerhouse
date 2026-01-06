# Quickstart: E2E Test Support for Cognito Email OTP

**Feature**: 019-e2e-email-otp | **Date**: 2026-01-06

## Overview

This feature enables E2E tests to complete the real Cognito EMAIL_OTP authentication flow by intercepting OTP codes via a Custom Message Lambda Trigger.

## Architecture

```
┌──────────────┐    ┌─────────────────────┐    ┌──────────────────┐
│   E2E Test   │───→│  Cognito User Pool  │───→│  Custom Message  │
│  (Playwright)│    │    (EMAIL_OTP)      │    │     Lambda       │
└──────────────┘    └─────────────────────┘    └────────┬─────────┘
       │                                                 │
       │                                                 ▼
       │         ┌─────────────────────────────────────────────────┐
       │         │           verification_codes Table              │
       │         │  PK: email | code | expires_at (TTL: 5 min)     │
       │         └─────────────────────────────────────────────────┘
       │                                                 │
       └─────────────────────────────────────────────────┘
                    Poll for OTP via otp-helper.ts
```

## Quick Test

After deployment, verify OTP interception works:

```bash
# 1. Deploy infrastructure (dev only)
task tf:apply:dev

# 2. Run the OTP interception test
cd frontend && yarn test:e2e --grep "OTP retrieval"
```

## Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| OTP Interceptor Lambda | `backend/lambdas/otp-interceptor/` | Stores OTP codes from Cognito triggers |
| Terraform Module | `infrastructure/modules/otp-interceptor/` | Lambda + Cognito trigger wiring |
| E2E Helper | `frontend/tests/e2e/utils/otp-helper.ts` | Polls DynamoDB for OTP codes |
| Auth Fixture | `frontend/tests/e2e/fixtures/auth.fixture.ts` | Updated to use real OTP flow |

## Usage in Tests

```typescript
import { getOtpCode } from '../utils/otp-helper';

test('complete booking with real OTP', async ({ page }) => {
  const testEmail = `test+${crypto.randomUUID()}@summerhouse.com`;

  // 1. Enter email in auth flow
  await page.fill('[data-testid="email-input"]', testEmail);
  await page.click('[data-testid="submit-email"]');

  // 2. Wait for and retrieve OTP (intercepted by Lambda)
  const otpCode = await getOtpCode(testEmail);

  // 3. Enter OTP in UI
  await page.fill('[data-testid="otp-input"]', otpCode);
  await page.click('[data-testid="verify-otp"]');

  // 4. Continue with authenticated flow
  await expect(page.locator('[data-testid="guest-details"]')).toBeVisible();
});
```

## Environment Requirements

### CI/CD Environment Variables

```bash
# Required for E2E tests to retrieve OTP codes
AWS_REGION=eu-west-1
VERIFICATION_CODES_TABLE=booking-dev-verification-codes

# AWS credentials with DynamoDB read access (already configured in CI)
AWS_ACCESS_KEY_ID=***
AWS_SECRET_ACCESS_KEY=***
```

### Test Email Pattern

Tests MUST use emails matching one of these patterns:
- `test+{anything}@summerhouse.com` (recommended)
- `*@test.summerhouse.com`

Only these patterns trigger OTP interception.

## Security Safeguards

1. **Dev-Only Deployment**: Lambda module only instantiated in `environments/dev/`
2. **Environment Check**: Lambda verifies `ENVIRONMENT=dev` before storing
3. **Email Pattern Filter**: Only test email patterns are intercepted
4. **TTL Auto-Cleanup**: Codes expire after 5 minutes

## Removing Mock Auth

After this feature ships, remove the following:

1. Delete `window.__MOCK_AUTH__` injection from test setup
2. Remove `ALLOW_USER_PASSWORD_AUTH` from Cognito (if unused elsewhere)
3. Update auth fixture to remove mock token generation
4. Delete any skipped Guest Details step logic

## Troubleshooting

| Issue | Solution |
|-------|----------|
| OTP not found | Check email matches test pattern, verify Lambda logs in CloudWatch |
| Timeout retrieving OTP | Increase timeout in `getOtpCode()`, check DynamoDB permissions |
| Lambda not triggered | Verify Cognito Custom Message trigger is configured |
| Wrong trigger source | Ensure `CustomMessage_Authentication` events are handled |
