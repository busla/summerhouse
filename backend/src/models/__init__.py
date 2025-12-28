"""Pydantic models for Summerhouse data entities."""

from .availability import (
    Availability,
    AvailabilityRange,
    AvailabilityResponse,
)
from .enums import (
    AvailabilityStatus,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    ReservationStatus,
    TransactionStatus,
)
from .guest import Guest, GuestCreate, GuestUpdate
from .payment import Payment, PaymentCreate, PaymentResult
from .pricing import PriceCalculation, Pricing, PricingCreate
from .reservation import Reservation, ReservationCreate, ReservationSummary
from .verification import (
    VerificationAttempt,
    VerificationCode,
    VerificationRequest,
    VerificationResult,
)
from .area_info import (
    AreaCategory,
    AreaInfo,
    AreaInfoResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from .property import (
    Address,
    Coordinates,
    Photo,
    PhotoCategory,
    PhotosResponse,
    Property,
    PropertyDetailsResponse,
    PropertySummary,
)

__all__ = [
    # Enums
    "AvailabilityStatus",
    "PaymentMethod",
    "PaymentProvider",
    "PaymentStatus",
    "ReservationStatus",
    "TransactionStatus",
    # Guest
    "Guest",
    "GuestCreate",
    "GuestUpdate",
    # Reservation
    "Reservation",
    "ReservationCreate",
    "ReservationSummary",
    # Availability
    "Availability",
    "AvailabilityRange",
    "AvailabilityResponse",
    # Pricing
    "Pricing",
    "PricingCreate",
    "PriceCalculation",
    # Payment
    "Payment",
    "PaymentCreate",
    "PaymentResult",
    # Verification
    "VerificationCode",
    "VerificationRequest",
    "VerificationAttempt",
    "VerificationResult",
    # Area Info
    "AreaCategory",
    "AreaInfo",
    "AreaInfoResponse",
    "RecommendationRequest",
    "RecommendationResponse",
    # Property
    "Address",
    "Coordinates",
    "Photo",
    "PhotoCategory",
    "PhotosResponse",
    "Property",
    "PropertyDetailsResponse",
    "PropertySummary",
]
