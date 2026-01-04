"""Unit tests for PaymentService payment status methods.

Tests verify the service correctly:
- Retrieves payments for a reservation (T025)
- Converts DynamoDB items to Payment models with all Stripe fields
- Handles missing and empty payments lists

TDD: These tests verify PaymentService behavior at the service layer.

Test categories:
- T025-A: get_payments_for_reservation() retrieval
- T025-B: _item_to_payment() conversion with Stripe fields
- T025-C: Edge cases (empty results, missing fields)
"""

import datetime as dt
import os
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from shared.models.enums import PaymentMethod, PaymentProvider, TransactionStatus
from shared.models.payment import Payment
from shared.services.payment_service import PaymentService


# === Test Configuration ===

TEST_RESERVATION_ID = "RES-2026-UNITTEST"
TEST_PAYMENT_ID = "PAY-2026-UNITTEST"


# === Test Fixtures ===


@pytest.fixture
def mock_dynamodb_tables() -> Generator[None, None, None]:
    """Set up mock DynamoDB tables for testing."""
    with mock_aws():
        # Set up environment
        os.environ["DYNAMODB_TABLE_PREFIX"] = "test-booking"
        os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"

        db_client = boto3.client("dynamodb", region_name="eu-west-1")

        # Create payments table with reservation-index GSI
        db_client.create_table(
            TableName="test-booking-payments",
            KeySchema=[{"AttributeName": "payment_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "payment_id", "AttributeType": "S"},
                {"AttributeName": "reservation_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "reservation-index",
                    "KeySchema": [{"AttributeName": "reservation_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        yield


@pytest.fixture
def payment_service(mock_dynamodb_tables: None) -> PaymentService:
    """Create PaymentService instance with mock DynamoDB."""
    from shared.services.dynamodb import DynamoDBService

    db = DynamoDBService()
    return PaymentService(db)


@pytest.fixture
def sample_payment_item() -> dict[str, Any]:
    """Sample DynamoDB payment item with all fields including Stripe-specific."""
    return {
        "payment_id": TEST_PAYMENT_ID,
        "reservation_id": TEST_RESERVATION_ID,
        "amount": 112500,
        "currency": "EUR",
        "status": "completed",
        "payment_method": "card",
        "provider": "stripe",
        "provider_transaction_id": "pi_3ABC123DEF456",
        "stripe_checkout_session_id": "cs_test_abc123",
        "stripe_payment_intent_id": "pi_3ABC123DEF456",
        "created_at": "2026-07-01T10:00:00+00:00",
        "completed_at": "2026-07-01T10:05:00+00:00",
    }


@pytest.fixture
def sample_refunded_payment_item() -> dict[str, Any]:
    """Sample DynamoDB payment item with refund fields."""
    return {
        "payment_id": "PAY-2026-REFUNDED",
        "reservation_id": TEST_RESERVATION_ID,
        "amount": 112500,
        "currency": "EUR",
        "status": "refunded",
        "payment_method": "card",
        "provider": "stripe",
        "provider_transaction_id": "pi_refund123",
        "stripe_checkout_session_id": "cs_test_refund",
        "stripe_payment_intent_id": "pi_refund123",
        "stripe_refund_id": "re_refund123",
        "refund_amount": 112500,
        "created_at": "2026-07-01T10:00:00+00:00",
        "completed_at": "2026-07-01T10:05:00+00:00",
        "refunded_at": "2026-07-02T14:30:00+00:00",
    }


def _create_payment_in_db(payment_item: dict[str, Any]) -> None:
    """Helper to create a payment in mock DynamoDB."""
    resource = boto3.resource("dynamodb", region_name="eu-west-1")
    table = resource.Table("test-booking-payments")
    table.put_item(Item=payment_item)


# === T025-A: get_payments_for_reservation() Tests ===


class TestGetPaymentsForReservation:
    """Tests for PaymentService.get_payments_for_reservation()."""

    def test_returns_empty_list_when_no_payments(
        self,
        payment_service: PaymentService,
    ) -> None:
        """get_payments_for_reservation() returns empty list when none exist."""
        result = payment_service.get_payments_for_reservation("RES-NONEXISTENT")

        assert result == []
        assert isinstance(result, list)

    def test_returns_payment_list(
        self,
        payment_service: PaymentService,
        sample_payment_item: dict[str, Any],
    ) -> None:
        """get_payments_for_reservation() returns list of Payment objects."""
        _create_payment_in_db(sample_payment_item)

        result = payment_service.get_payments_for_reservation(TEST_RESERVATION_ID)

        assert len(result) == 1
        assert isinstance(result[0], Payment)
        assert result[0].payment_id == TEST_PAYMENT_ID
        assert result[0].reservation_id == TEST_RESERVATION_ID

    def test_returns_multiple_payments(
        self,
        payment_service: PaymentService,
        sample_payment_item: dict[str, Any],
    ) -> None:
        """get_payments_for_reservation() returns all payments for reservation."""
        # Create first payment
        _create_payment_in_db(sample_payment_item)

        # Create second payment (failed attempt)
        failed_payment = {
            **sample_payment_item,
            "payment_id": "PAY-2026-FAILED",
            "status": "failed",
            "error_message": "Card declined",
            "completed_at": None,
        }
        del failed_payment["completed_at"]  # Remove None value
        failed_payment.pop("completed_at", None)
        _create_payment_in_db(failed_payment)

        result = payment_service.get_payments_for_reservation(TEST_RESERVATION_ID)

        assert len(result) == 2
        payment_ids = {p.payment_id for p in result}
        assert TEST_PAYMENT_ID in payment_ids
        assert "PAY-2026-FAILED" in payment_ids


# === T025-B: _item_to_payment() Stripe Field Tests ===


class TestItemToPaymentConversion:
    """Tests for Payment model conversion including Stripe fields."""

    def test_converts_basic_fields(
        self,
        payment_service: PaymentService,
        sample_payment_item: dict[str, Any],
    ) -> None:
        """_item_to_payment() correctly converts required fields."""
        _create_payment_in_db(sample_payment_item)
        result = payment_service.get_payments_for_reservation(TEST_RESERVATION_ID)
        payment = result[0]

        assert payment.payment_id == TEST_PAYMENT_ID
        assert payment.reservation_id == TEST_RESERVATION_ID
        assert payment.amount == 112500
        assert payment.currency == "EUR"
        assert payment.status == TransactionStatus.COMPLETED
        assert payment.payment_method == PaymentMethod.CARD
        assert payment.provider == PaymentProvider.STRIPE

    def test_converts_stripe_specific_fields(
        self,
        payment_service: PaymentService,
        sample_payment_item: dict[str, Any],
    ) -> None:
        """_item_to_payment() correctly converts Stripe-specific fields (FR-028)."""
        _create_payment_in_db(sample_payment_item)
        result = payment_service.get_payments_for_reservation(TEST_RESERVATION_ID)
        payment = result[0]

        assert payment.stripe_checkout_session_id == "cs_test_abc123"
        assert payment.stripe_payment_intent_id == "pi_3ABC123DEF456"
        assert payment.provider_transaction_id == "pi_3ABC123DEF456"

    def test_converts_refund_fields(
        self,
        payment_service: PaymentService,
        sample_refunded_payment_item: dict[str, Any],
    ) -> None:
        """_item_to_payment() correctly converts refund fields (FR-028)."""
        _create_payment_in_db(sample_refunded_payment_item)
        result = payment_service.get_payments_for_reservation(TEST_RESERVATION_ID)
        payment = result[0]

        assert payment.status == TransactionStatus.REFUNDED
        assert payment.stripe_refund_id == "re_refund123"
        assert payment.refund_amount == 112500
        assert payment.refunded_at is not None
        assert isinstance(payment.refunded_at, dt.datetime)

    def test_converts_datetime_fields(
        self,
        payment_service: PaymentService,
        sample_payment_item: dict[str, Any],
    ) -> None:
        """_item_to_payment() correctly converts datetime fields."""
        _create_payment_in_db(sample_payment_item)
        result = payment_service.get_payments_for_reservation(TEST_RESERVATION_ID)
        payment = result[0]

        assert isinstance(payment.created_at, dt.datetime)
        assert isinstance(payment.completed_at, dt.datetime)


# === T025-C: Edge Case Tests ===


class TestPaymentServiceEdgeCases:
    """Edge case tests for PaymentService."""

    def test_handles_missing_optional_fields(
        self,
        payment_service: PaymentService,
    ) -> None:
        """Payment conversion handles missing optional fields gracefully."""
        minimal_payment = {
            "payment_id": "PAY-2026-MINIMAL",
            "reservation_id": TEST_RESERVATION_ID,
            "amount": 50000,
            "status": "pending",
            "payment_method": "card",
            "provider": "stripe",
            "created_at": "2026-07-01T10:00:00+00:00",
        }
        _create_payment_in_db(minimal_payment)

        result = payment_service.get_payments_for_reservation(TEST_RESERVATION_ID)
        payment = result[0]

        # Optional fields should be None
        assert payment.completed_at is None
        assert payment.stripe_checkout_session_id is None
        assert payment.stripe_payment_intent_id is None
        assert payment.stripe_refund_id is None
        assert payment.refund_amount is None
        assert payment.refunded_at is None
        assert payment.error_message is None
        assert payment.provider_transaction_id is None

    def test_handles_default_currency(
        self,
        payment_service: PaymentService,
    ) -> None:
        """Payment conversion uses EUR as default currency."""
        payment_no_currency = {
            "payment_id": "PAY-2026-NOCURRENCY",
            "reservation_id": TEST_RESERVATION_ID,
            "amount": 50000,
            "status": "pending",
            "payment_method": "card",
            "provider": "stripe",
            "created_at": "2026-07-01T10:00:00+00:00",
            # No currency field
        }
        _create_payment_in_db(payment_no_currency)

        result = payment_service.get_payments_for_reservation(TEST_RESERVATION_ID)
        payment = result[0]

        assert payment.currency == "EUR"

    def test_get_payment_by_id(
        self,
        payment_service: PaymentService,
        sample_payment_item: dict[str, Any],
    ) -> None:
        """get_payment() returns Payment by ID."""
        _create_payment_in_db(sample_payment_item)

        result = payment_service.get_payment(TEST_PAYMENT_ID)

        assert result is not None
        assert result.payment_id == TEST_PAYMENT_ID

    def test_get_payment_returns_none_when_not_found(
        self,
        payment_service: PaymentService,
    ) -> None:
        """get_payment() returns None for non-existent payment."""
        result = payment_service.get_payment("PAY-NONEXISTENT")

        assert result is None
