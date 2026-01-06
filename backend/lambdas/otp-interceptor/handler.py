"""OTP Interceptor Lambda - Cognito Custom Email Sender Trigger Handler.

Custom Email Sender receives the ENCRYPTED actual OTP code (not a placeholder).
This Lambda:
1. Decrypts the OTP code using AWS Encryption SDK + KMS
2. Stores it in DynamoDB for E2E test retrieval (test emails only)
3. Sends the email via SES (ALL emails - we've taken over email delivery)

Note: Requires build_in_docker=true in Terraform to compile cryptography
package with Linux-compatible native binaries (Rust-compiled .so files).

Reference: https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-lambda-custom-email-sender.html
"""

import base64
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

import aws_encryption_sdk
import boto3
from aws_encryption_sdk import CommitmentPolicy

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Test email patterns that trigger OTP storage (interception)
TEST_EMAIL_PATTERNS = [
    re.compile(r"^test\+.+@summerhouse\.com$"),  # test+{anything}@summerhouse.com
    re.compile(r"^.+@test\.summerhouse\.com$"),  # *@test.summerhouse.com
]

# Trigger sources we handle
EMAIL_SENDER_TRIGGERS = {
    "CustomEmailSender_SignUp",
    "CustomEmailSender_Authentication",
    "CustomEmailSender_ResendCode",
    "CustomEmailSender_ForgotPassword",
    "CustomEmailSender_UpdateUserAttribute",
    "CustomEmailSender_VerifyUserAttribute",
    "CustomEmailSender_AdminCreateUser",
}

# OTP validity in seconds (5 minutes)
OTP_TTL_SECONDS = 300

# Email templates by trigger source
EMAIL_SUBJECTS = {
    "CustomEmailSender_SignUp": "Welcome to Summerhouse - Verify your email",
    "CustomEmailSender_Authentication": "Your Summerhouse login code",
    "CustomEmailSender_ResendCode": "Your Summerhouse verification code",
    "CustomEmailSender_ForgotPassword": "Reset your Summerhouse password",
    "CustomEmailSender_UpdateUserAttribute": "Verify your email change",
    "CustomEmailSender_VerifyUserAttribute": "Verify your email address",
    "CustomEmailSender_AdminCreateUser": "Welcome to Summerhouse",
}

# Initialize AWS Encryption SDK client (singleton)
_encryption_client = None
_kms_key_provider = None


def get_encryption_client():
    """Get or create AWS Encryption SDK client singleton."""
    global _encryption_client, _kms_key_provider

    if _encryption_client is None:
        kms_key_arn = os.environ.get("KMS_KEY_ARN")
        if not kms_key_arn:
            raise ValueError("KMS_KEY_ARN environment variable not set")

        _kms_key_provider = aws_encryption_sdk.StrictAwsKmsMasterKeyProvider(
            key_ids=[kms_key_arn]
        )
        _encryption_client = aws_encryption_sdk.EncryptionSDKClient(
            commitment_policy=CommitmentPolicy.REQUIRE_ENCRYPT_ALLOW_DECRYPT
        )

    return _encryption_client, _kms_key_provider


def decrypt_code(encrypted_code: str) -> str:
    """Decrypt the OTP code from Cognito using AWS Encryption SDK.

    Args:
        encrypted_code: Base64-encoded encrypted code from Cognito

    Returns:
        Decrypted plaintext OTP code
    """
    client, key_provider = get_encryption_client()

    # Cognito sends the code as base64-encoded ciphertext
    ciphertext = base64.b64decode(encrypted_code)

    # Decrypt using AWS Encryption SDK
    plaintext, _ = client.decrypt(source=ciphertext, key_provider=key_provider)

    return plaintext.decode("utf-8")


def is_test_email(email: str) -> bool:
    """Check if email matches test patterns for OTP storage."""
    return any(pattern.match(email) for pattern in TEST_EMAIL_PATTERNS)


def should_store_otp(email: str) -> bool:
    """Determine if OTP should be stored in DynamoDB.

    Only stores in dev environment for test email patterns.
    """
    environment = os.environ.get("ENVIRONMENT", "")
    if environment != "dev":
        return False

    return is_test_email(email)


def store_otp(email: str, code: str, trigger_source: str) -> None:
    """Store OTP code in DynamoDB for E2E test retrieval.

    Args:
        email: User's email address (partition key)
        code: Decrypted 6-digit OTP code
        trigger_source: Cognito trigger type for debugging
    """
    table_name = os.environ.get("VERIFICATION_CODES_TABLE")
    if not table_name:
        logger.error("VERIFICATION_CODES_TABLE environment variable not set")
        return

    dynamodb = boto3.client("dynamodb")
    now = datetime.now(timezone.utc)
    expires_at = int(time.time()) + OTP_TTL_SECONDS

    item = {
        "email": {"S": email},
        "code": {"S": code},
        "trigger_source": {"S": trigger_source},
        "created_at": {"S": now.isoformat()},
        "expires_at": {"N": str(expires_at)},
    }

    try:
        dynamodb.put_item(TableName=table_name, Item=item)
        logger.info(f"Stored OTP for {email[:20]}... (trigger: {trigger_source})")
    except Exception as e:
        # Log error but don't fail - email should still be sent
        logger.error(f"Failed to store OTP: {e}")


def send_email(email: str, code: str, trigger_source: str) -> None:
    """Send OTP email via SES.

    Custom Email Sender means WE are responsible for all email delivery.
    Cognito does not send emails when this trigger is active.

    Args:
        email: Recipient email address
        code: Decrypted OTP code
        trigger_source: Cognito trigger type (for subject/template selection)
    """
    ses_from = os.environ.get("SES_FROM_EMAIL")
    ses_region = os.environ.get("SES_REGION")

    if not ses_from:
        logger.error("SES_FROM_EMAIL environment variable not set")
        return

    ses = boto3.client("ses", region_name=ses_region)

    subject = EMAIL_SUBJECTS.get(trigger_source, "Your Summerhouse verification code")

    # Simple HTML email body
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #333;">{subject}</h2>
        <p>Your verification code is:</p>
        <p style="font-size: 32px; font-weight: bold; color: #007bff; letter-spacing: 4px;">
            {code}
        </p>
        <p style="color: #666; font-size: 14px;">
            This code expires in 5 minutes.
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 12px;">
            If you didn't request this code, you can safely ignore this email.
        </p>
    </body>
    </html>
    """

    text_body = f"""
{subject}

Your verification code is: {code}

This code expires in 5 minutes.

If you didn't request this code, you can safely ignore this email.
"""

    try:
        ses.send_email(
            Source=ses_from,
            Destination={"ToAddresses": [email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": text_body, "Charset": "UTF-8"},
                    "Html": {"Data": html_body, "Charset": "UTF-8"},
                },
            },
        )
        logger.info(f"Sent email to {email[:20]}... (trigger: {trigger_source})")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise  # Re-raise so Cognito knows delivery failed


def handler(event: dict[str, Any], context: Any) -> None:
    """Cognito Custom Email Sender Lambda Trigger handler.

    1. Decrypts the OTP code from Cognito
    2. Stores it in DynamoDB for E2E tests (test emails in dev only)
    3. Sends the email via SES (all emails)

    Args:
        event: Cognito Custom Email Sender trigger event
        context: Lambda context (unused)

    Returns:
        None - Custom Email Sender doesn't expect a response
    """
    trigger_source = event.get("triggerSource", "unknown")
    logger.info(f"Custom Email Sender invoked: {trigger_source}")

    # Validate trigger source
    if trigger_source not in EMAIL_SENDER_TRIGGERS:
        logger.warning(f"Unknown trigger source: {trigger_source}")
        return

    # Extract request data
    request = event.get("request", {})
    encrypted_code = request.get("code", "")
    email = request.get("userAttributes", {}).get("email", "")

    if not encrypted_code or not email:
        logger.error(f"Missing code or email: code={bool(encrypted_code)}, email={bool(email)}")
        return

    # Decrypt the OTP code
    try:
        code = decrypt_code(encrypted_code)
        logger.info(f"Successfully decrypted code (length: {len(code)})")
    except Exception as e:
        logger.error(f"Failed to decrypt code: {e}")
        raise

    # Store OTP for E2E test retrieval (test emails in dev only)
    if should_store_otp(email):
        store_otp(email, code, trigger_source)

    # Send email via SES (all emails)
    send_email(email, code, trigger_source)
