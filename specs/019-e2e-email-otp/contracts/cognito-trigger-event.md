# Contract: Cognito Custom Message Trigger Event

**Feature**: 019-e2e-email-otp | **Version**: 1.0.0

## Overview

This contract defines the event structure received by the OTP Interceptor Lambda from Cognito's Custom Message trigger.

## Event Schema

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class CognitoCustomMessageEvent:
    """
    Event received from Cognito Custom Message Lambda Trigger.

    Reference: https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-lambda-custom-message.html
    """
    version: str                    # e.g., "1"
    region: str                     # e.g., "eu-west-1"
    userPoolId: str                 # e.g., "eu-west-1_XXXXXXXXX"
    userName: str                   # Cognito username (UUID or email)
    callerContext: CallerContext
    triggerSource: str              # See TriggerSource enum
    request: CustomMessageRequest
    response: CustomMessageResponse


@dataclass
class CallerContext:
    awsSdkVersion: str              # e.g., "aws-sdk-js-3.535.0"
    clientId: str                   # Cognito App Client ID


@dataclass
class CustomMessageRequest:
    userAttributes: dict[str, str]  # Must contain "email"
    codeParameter: str              # The actual OTP code (e.g., "123456")
    usernameParameter: str | None   # For admin-created users


@dataclass
class CustomMessageResponse:
    smsMessage: str | None          # SMS template (not used for EMAIL_OTP)
    emailMessage: str | None        # HTML email body template
    emailSubject: str | None        # Email subject line
```

## Trigger Sources

| Trigger Source | Description | Intercepted? |
|----------------|-------------|--------------|
| `CustomMessage_SignUp` | Sign-up confirmation | Yes |
| `CustomMessage_Authentication` | EMAIL_OTP login code | **Yes (Primary)** |
| `CustomMessage_ResendCode` | Resend confirmation | Yes |
| `CustomMessage_ForgotPassword` | Password reset | No |
| `CustomMessage_UpdateUserAttribute` | Attribute verification | No |
| `CustomMessage_VerifyUserAttribute` | Attribute verification | No |
| `CustomMessage_AdminCreateUser` | Admin-created user | No |

## Example Event

```json
{
  "version": "1",
  "region": "eu-west-1",
  "userPoolId": "eu-west-1_abc123XYZ",
  "userName": "550e8400-e29b-41d4-a716-446655440000",
  "callerContext": {
    "awsSdkVersion": "aws-sdk-js-3.535.0",
    "clientId": "1234567890abcdef"
  },
  "triggerSource": "CustomMessage_Authentication",
  "request": {
    "userAttributes": {
      "sub": "550e8400-e29b-41d4-a716-446655440000",
      "email_verified": "true",
      "email": "test+e2e-abc123@summerhouse.com"
    },
    "codeParameter": "123456",
    "usernameParameter": null
  },
  "response": {
    "smsMessage": null,
    "emailMessage": null,
    "emailSubject": null
  }
}
```

## Lambda Response Contract

The Lambda MUST return the event unmodified (pass-through) to allow normal email delivery:

```python
def handler(event: dict, context: Any) -> dict:
    # Process event (store OTP if test email)
    # ...

    # MUST return original event for Cognito to send email
    return event
```

## Validation Rules

1. **userAttributes.email** MUST be present (Cognito guarantees this for EMAIL_OTP)
2. **codeParameter** MUST be a 6-digit string
3. **triggerSource** MUST be one of the defined values
