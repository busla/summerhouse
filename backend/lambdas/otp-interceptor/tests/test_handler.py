"""Unit tests for OTP Interceptor Lambda handler.

Uses moto to mock DynamoDB for isolated testing.
"""

import os
import time
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

# Import handler after setting up mocks
os.environ["VERIFICATION_CODES_TABLE"] = "test-verification-codes"
os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"

from handler import (
    INTERCEPTED_TRIGGERS,
    OTP_TTL_SECONDS,
    TEST_EMAIL_PATTERNS,
    handler,
    is_test_email,
    should_intercept,
    store_otp,
)


class TestIsTestEmail:
    """Tests for is_test_email() function."""

    def test_test_plus_pattern_matches(self):
        """test+anything@summerhouse.com should match."""
        assert is_test_email("test+abc123@summerhouse.com") is True
        assert is_test_email("test+e2e-booking-flow@summerhouse.com") is True
        assert is_test_email("test+550e8400-e29b-41d4@summerhouse.com") is True

    def test_test_subdomain_pattern_matches(self):
        """*@test.summerhouse.com should match."""
        assert is_test_email("user@test.summerhouse.com") is True
        assert is_test_email("anything@test.summerhouse.com") is True

    def test_regular_email_does_not_match(self):
        """Regular emails should not match."""
        assert is_test_email("user@summerhouse.com") is False
        assert is_test_email("test@summerhouse.com") is False
        assert is_test_email("user@example.com") is False

    def test_similar_but_different_patterns_do_not_match(self):
        """Similar but different patterns should not match."""
        assert is_test_email("test@summerhouse.com") is False  # No + suffix
        assert is_test_email("test+abc@other.com") is False  # Wrong domain
        assert is_test_email("user@summerhouse.test.com") is False  # Wrong subdomain


class TestShouldIntercept:
    """Tests for should_intercept() function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.valid_event = {
            "triggerSource": "CustomMessage_Authentication",
            "request": {
                "userAttributes": {
                    "email": "test+e2e@summerhouse.com"
                },
                "codeParameter": "123456"
            }
        }

    def test_intercepts_in_dev_environment(self):
        """Should intercept in dev environment with valid event."""
        with patch.dict(os.environ, {"ENVIRONMENT": "dev"}):
            assert should_intercept(self.valid_event) is True

    def test_does_not_intercept_in_prod(self):
        """Should NOT intercept in prod environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "prod"}):
            assert should_intercept(self.valid_event) is False

    def test_does_not_intercept_without_environment(self):
        """Should NOT intercept when ENVIRONMENT not set."""
        with patch.dict(os.environ, {"ENVIRONMENT": ""}):
            assert should_intercept(self.valid_event) is False

    def test_intercepts_authentication_trigger(self):
        """Should intercept CustomMessage_Authentication."""
        with patch.dict(os.environ, {"ENVIRONMENT": "dev"}):
            event = {**self.valid_event, "triggerSource": "CustomMessage_Authentication"}
            assert should_intercept(event) is True

    def test_intercepts_signup_trigger(self):
        """Should intercept CustomMessage_SignUp."""
        with patch.dict(os.environ, {"ENVIRONMENT": "dev"}):
            event = {**self.valid_event, "triggerSource": "CustomMessage_SignUp"}
            assert should_intercept(event) is True

    def test_intercepts_resend_trigger(self):
        """Should intercept CustomMessage_ResendCode."""
        with patch.dict(os.environ, {"ENVIRONMENT": "dev"}):
            event = {**self.valid_event, "triggerSource": "CustomMessage_ResendCode"}
            assert should_intercept(event) is True

    def test_does_not_intercept_forgot_password(self):
        """Should NOT intercept CustomMessage_ForgotPassword."""
        with patch.dict(os.environ, {"ENVIRONMENT": "dev"}):
            event = {**self.valid_event, "triggerSource": "CustomMessage_ForgotPassword"}
            assert should_intercept(event) is False

    def test_does_not_intercept_non_test_email(self):
        """Should NOT intercept for regular email addresses."""
        with patch.dict(os.environ, {"ENVIRONMENT": "dev"}):
            event = {
                **self.valid_event,
                "request": {
                    "userAttributes": {"email": "user@example.com"},
                    "codeParameter": "123456"
                }
            }
            assert should_intercept(event) is False


@pytest.fixture
def dynamodb_table():
    """Create mock DynamoDB table for OTP storage tests."""
    with mock_aws():
        client = boto3.client("dynamodb", region_name="eu-west-1")
        client.create_table(
            TableName="test-verification-codes",
            KeySchema=[{"AttributeName": "email", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "email", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST"
        )
        yield client


class TestStoreOtp:
    """Tests for store_otp() function using moto."""

    def test_stores_otp_in_dynamodb(self, dynamodb_table):
        """Should store OTP record in DynamoDB."""
        email = "test+e2e@summerhouse.com"
        code = "123456"
        trigger = "CustomMessage_Authentication"

        store_otp(email, code, trigger)

        # Verify item was stored
        response = dynamodb_table.get_item(
            TableName="test-verification-codes",
            Key={"email": {"S": email}}
        )

        assert "Item" in response
        item = response["Item"]
        assert item["email"]["S"] == email
        assert item["code"]["S"] == code
        assert item["trigger_source"]["S"] == trigger
        assert "created_at" in item
        assert "expires_at" in item

    def test_otp_has_correct_ttl(self, dynamodb_table):
        """Should set expires_at to ~5 minutes in the future."""
        email = "test+ttl@summerhouse.com"
        before = int(time.time())

        store_otp(email, "123456", "CustomMessage_Authentication")

        after = int(time.time())

        response = dynamodb_table.get_item(
            TableName="test-verification-codes",
            Key={"email": {"S": email}}
        )

        expires_at = int(response["Item"]["expires_at"]["N"])
        expected_min = before + OTP_TTL_SECONDS
        expected_max = after + OTP_TTL_SECONDS

        assert expected_min <= expires_at <= expected_max

    def test_overwrites_existing_otp(self, dynamodb_table):
        """Should overwrite existing OTP for same email."""
        email = "test+overwrite@summerhouse.com"

        # Store first OTP
        store_otp(email, "111111", "CustomMessage_Authentication")

        # Store second OTP (simulating resend)
        store_otp(email, "222222", "CustomMessage_ResendCode")

        # Verify only latest OTP is stored
        response = dynamodb_table.get_item(
            TableName="test-verification-codes",
            Key={"email": {"S": email}}
        )

        assert response["Item"]["code"]["S"] == "222222"
        assert response["Item"]["trigger_source"]["S"] == "CustomMessage_ResendCode"


class TestHandler:
    """Integration tests for the handler() function."""

    def test_handler_returns_event_unchanged(self, dynamodb_table):
        """Handler must return event unchanged for Cognito to send email."""
        event = {
            "version": "1",
            "region": "eu-west-1",
            "userPoolId": "eu-west-1_test",
            "userName": "test-user",
            "triggerSource": "CustomMessage_Authentication",
            "request": {
                "userAttributes": {"email": "test+e2e@summerhouse.com"},
                "codeParameter": "123456"
            },
            "response": {
                "smsMessage": None,
                "emailMessage": None,
                "emailSubject": None
            }
        }

        with patch.dict(os.environ, {"ENVIRONMENT": "dev"}):
            result = handler(event, None)

        assert result == event

    def test_handler_stores_otp_for_test_email_in_dev(self, dynamodb_table):
        """Handler should store OTP for test email in dev environment."""
        email = "test+handler@summerhouse.com"
        code = "654321"
        event = {
            "triggerSource": "CustomMessage_Authentication",
            "request": {
                "userAttributes": {"email": email},
                "codeParameter": code
            },
            "response": {}
        }

        with patch.dict(os.environ, {"ENVIRONMENT": "dev"}):
            handler(event, None)

        # Verify OTP was stored
        response = dynamodb_table.get_item(
            TableName="test-verification-codes",
            Key={"email": {"S": email}}
        )

        assert "Item" in response
        assert response["Item"]["code"]["S"] == code

    def test_handler_does_not_store_otp_in_prod(self, dynamodb_table):
        """Handler should NOT store OTP in prod environment."""
        email = "test+prod@summerhouse.com"
        event = {
            "triggerSource": "CustomMessage_Authentication",
            "request": {
                "userAttributes": {"email": email},
                "codeParameter": "123456"
            },
            "response": {}
        }

        with patch.dict(os.environ, {"ENVIRONMENT": "prod"}):
            handler(event, None)

        # Verify OTP was NOT stored
        response = dynamodb_table.get_item(
            TableName="test-verification-codes",
            Key={"email": {"S": email}}
        )

        assert "Item" not in response

    def test_handler_does_not_store_for_regular_email(self, dynamodb_table):
        """Handler should NOT store OTP for regular email addresses."""
        email = "user@example.com"
        event = {
            "triggerSource": "CustomMessage_Authentication",
            "request": {
                "userAttributes": {"email": email},
                "codeParameter": "123456"
            },
            "response": {}
        }

        with patch.dict(os.environ, {"ENVIRONMENT": "dev"}):
            handler(event, None)

        # Verify OTP was NOT stored
        response = dynamodb_table.get_item(
            TableName="test-verification-codes",
            Key={"email": {"S": email}}
        )

        assert "Item" not in response
