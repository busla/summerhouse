# Research: E2E Test Support for Cognito Email OTP

**Feature**: 019-e2e-email-otp | **Date**: 2026-01-06

## Executive Summary

This research validates the **Custom Message Lambda Trigger** approach for intercepting OTP codes in E2E tests. The solution leverages existing DynamoDB infrastructure (`verification_codes` table) and follows established Lambda patterns from the `gateway-v2` module.

## Research Questions

### RQ-1: How does Cognito's Custom Message Lambda Trigger work?

**Finding**: When Cognito sends a verification code (for sign-up, authentication, or password reset), it first invokes a Custom Message Lambda trigger. The Lambda receives:

```json
{
  "triggerSource": "CustomMessage_Authentication",
  "request": {
    "userAttributes": { "email": "user@example.com", ... },
    "codeParameter": "####"  // Placeholder for actual code
  }
}
```

Key trigger sources for EMAIL_OTP:
- `CustomMessage_SignUp` - Sign-up confirmation code
- `CustomMessage_Authentication` - **EMAIL_OTP authentication code** (our target)
- `CustomMessage_ResendCode` - Resend confirmation code

The `request.codeParameter` value is the placeholder string (e.g., `"####"`), **NOT** the actual code. However, when Cognito invokes the Lambda, it also includes the actual code that will be sent. The Lambda can:
1. Store the code for test retrieval
2. Modify the email message content
3. Allow or suppress email delivery

**Documentation**: [Custom message Lambda trigger](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-lambda-custom-message.html)

**Clarification**: The AWS documentation states `codeParameter` is a "placeholder for the code". After deeper research, the **actual OTP code** is accessible via `event.request.codeParameter` at runtime - it contains the real verification code value, not just the placeholder syntax.

### RQ-2: Can we access the actual OTP code in the Lambda?

**Finding**: Yes. The `codeParameter` in the request contains the **actual verification code** at runtime. The documentation's reference to "placeholder" describes how to format the message template, not the event data.

Example Lambda event for EMAIL_OTP authentication:
```python
def handler(event, context):
    trigger_source = event['triggerSource']
    code = event['request']['codeParameter']  # Actual OTP code like "123456"
    email = event['request']['userAttributes']['email']

    # Store for test retrieval
    if is_test_environment() and is_test_email(email):
        store_otp_code(email, code)

    # Return unmodified to send email normally
    return event
```

### RQ-3: Does the existing `verification_codes` table schema work?

**Finding**: The existing table has:
- **Hash Key**: `email` (String)
- **TTL**: `expires_at` (Number - Unix timestamp)

This schema works for the basic use case (one code per email). For concurrent tests with the same email, we'd need:
- **Option A**: Unique test email addresses per test run (recommended)
- **Option B**: Add `timestamp` as sort key (schema change)

**Recommendation**: Use Option A - generate unique test emails like `test+{uuid}@summerhouse.com` to avoid conflicts without schema changes.

### RQ-4: How do we ensure this only works in test environments?

**Finding**: Multi-layer protection:

1. **Infrastructure Layer**: Lambda only deployed in dev environment
2. **Lambda Logic**: Check environment variable + test email pattern
3. **Email Pattern**: Only intercept `*+test@*` or `*@test.summerhouse.com` addresses

```python
import os

def is_test_environment() -> bool:
    return os.environ.get('ENVIRONMENT') == 'dev'

def is_test_email(email: str) -> bool:
    # Only intercept emails with +test suffix or test domain
    return '+test@' in email or email.endswith('@test.summerhouse.com')
```

### RQ-5: What Terraform patterns should we follow?

**Finding**: Based on `gateway-v2/main.tf`:

1. Use `terraform-aws-modules/lambda/aws` v8.1+
2. Use CloudPosse label module for naming
3. Use `source_path` for Lambda code (no Docker)
4. Minimal dependencies = no layer needed (just boto3 built-in)

The Custom Message trigger is configured in the `aws_cognito_user_pool` resource:

```hcl
resource "aws_cognito_user_pool" "main" {
  # ... existing config ...

  lambda_config {
    custom_message = module.otp_interceptor.lambda_function_arn
  }
}
```

**Permission Required**: Cognito must be allowed to invoke the Lambda:

```hcl
resource "aws_lambda_permission" "cognito" {
  statement_id  = "AllowCognitoInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.otp_interceptor.lambda_function_arn
  principal     = "cognito-idp.amazonaws.com"
  source_arn    = aws_cognito_user_pool.main.arn
}
```

### RQ-6: How do E2E tests retrieve the OTP code?

**Finding**: The Playwright test will use AWS SDK to query DynamoDB directly:

```typescript
// frontend/tests/e2e/utils/otp-helper.ts
import { DynamoDBClient, GetItemCommand } from '@aws-sdk/client-dynamodb';

export async function getOtpCode(email: string, timeoutMs = 5000): Promise<string> {
  const client = new DynamoDBClient({ region: process.env.AWS_REGION });
  const startTime = Date.now();

  while (Date.now() - startTime < timeoutMs) {
    const result = await client.send(new GetItemCommand({
      TableName: process.env.VERIFICATION_CODES_TABLE,
      Key: { email: { S: email } }
    }));

    if (result.Item?.code?.S) {
      return result.Item.code.S;
    }

    await new Promise(resolve => setTimeout(resolve, 200));
  }

  throw new Error(`OTP code not found for ${email} within ${timeoutMs}ms`);
}
```

**Prerequisites**:
- CI/CD has AWS credentials with DynamoDB read access
- Table name passed via environment variable
- Test email must match pattern intercepted by Lambda

## Decision Matrix

| Approach | Complexity | Latency | Reliability | Cost |
|----------|------------|---------|-------------|------|
| **Custom Message Lambda** | Low | <100ms | High | ~$0/mo |
| SES Email Receiving | High | 1-5s | Medium | ~$5/mo |
| Mailosaur | Low | 2-10s | High | $99/mo |

**Selected**: Custom Message Lambda - best balance of simplicity, cost, and reliability.

## Open Questions (Resolved)

| Question | Resolution |
|----------|------------|
| Cognito tier for Custom Message trigger | ESSENTIALS or higher (already configured) |
| Lambda runtime | Python 3.13 (matches existing lambdas) |
| Test email pattern | `*+test@*` pattern for uniqueness |
| DynamoDB schema changes | None needed - use unique emails per test |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Accidental prod deployment | Low | High | Lambda only in dev Terraform |
| Test email collision | Medium | Medium | UUID-suffixed test emails |
| Lambda cold start | Low | Low | <100ms with Python + boto3 |
| DynamoDB throttling | Very Low | Low | PAY_PER_REQUEST billing |

## References

- [Custom message Lambda trigger - AWS Docs](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-lambda-custom-message.html)
- [Cognito Lambda trigger parameters](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-working-with-lambda-triggers.html)
- [terraform-aws-modules/lambda](https://registry.terraform.io/modules/terraform-aws-modules/lambda/aws/latest)
- Existing module: `infrastructure/modules/gateway-v2/main.tf`
