"""Enumeration types for Summerhouse data models."""

from enum import Enum


class ReservationStatus(str, Enum):
    """Status of a reservation."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class PaymentStatus(str, Enum):
    """Payment status for a reservation."""

    PENDING = "pending"
    PAID = "paid"
    COMPLETED = "completed"  # Alias for paid, used in some contexts
    REFUNDED = "refunded"
    PARTIAL_REFUND = "partial_refund"
    CANCELLED = "cancelled"  # No refund given


class AvailabilityStatus(str, Enum):
    """Status of a date's availability."""

    AVAILABLE = "available"
    BOOKED = "booked"
    BLOCKED = "blocked"


class PaymentMethod(str, Enum):
    """Supported payment methods."""

    CARD = "card"
    PAYPAL = "paypal"
    BANK_TRANSFER = "bank_transfer"


class PaymentProvider(str, Enum):
    """Payment processing providers."""

    STRIPE = "stripe"
    MOCK = "mock"


class TransactionStatus(str, Enum):
    """Status of a payment transaction."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
