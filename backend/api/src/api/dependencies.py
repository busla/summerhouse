"""FastAPI dependency injection providers for shared services.

This module provides factory functions for service instances using @lru_cache
to ensure singleton behavior within a request lifecycle. Services are lazily
instantiated and cached for performance.

Usage in routes:
    from api.dependencies import get_availability_service

    @router.get("/availability")
    async def check_availability(
        availability: AvailabilityService = Depends(get_availability_service),
    ):
        ...

Service Dependency Graph:
    DynamoDBService (singleton via get_dynamodb_service)
        ├── PricingService
        │       └── AvailabilityService
        │               └── BookingService
        └── PaymentService

Testing:
    Use reset_services() to clear cached instances between tests.
"""

from functools import lru_cache

from shared.services.availability import AvailabilityService
from shared.services.booking import BookingService
from shared.services.dynamodb import get_dynamodb_service
from shared.services.payment_service import PaymentService
from shared.services.pricing import PricingService


@lru_cache
def get_pricing_service() -> PricingService:
    """Get cached PricingService instance.

    Returns:
        PricingService configured with DynamoDB singleton.
    """
    return PricingService(db=get_dynamodb_service())


@lru_cache
def get_availability_service() -> AvailabilityService:
    """Get cached AvailabilityService instance.

    Returns:
        AvailabilityService configured with DynamoDB and PricingService.
    """
    return AvailabilityService(
        db=get_dynamodb_service(),
        pricing=get_pricing_service(),
    )


@lru_cache
def get_booking_service() -> BookingService:
    """Get cached BookingService instance.

    Returns:
        BookingService configured with all required dependencies.
    """
    return BookingService(
        db=get_dynamodb_service(),
        availability=get_availability_service(),
        pricing=get_pricing_service(),
    )


@lru_cache
def get_payment_service() -> PaymentService:
    """Get cached PaymentService instance.

    Returns:
        PaymentService configured with DynamoDB singleton.
    """
    return PaymentService(db=get_dynamodb_service())


def reset_services() -> None:
    """Clear all cached service instances.

    Call this in test fixtures to ensure clean state between tests.
    Also resets the underlying DynamoDB singleton.

    Example:
        @pytest.fixture(autouse=True)
        def reset_state():
            yield
            reset_services()
    """
    from shared.services.dynamodb import reset_dynamodb_service

    # Clear all lru_cache instances
    get_pricing_service.cache_clear()
    get_availability_service.cache_clear()
    get_booking_service.cache_clear()
    get_payment_service.cache_clear()

    # Reset underlying DynamoDB singleton
    reset_dynamodb_service()
