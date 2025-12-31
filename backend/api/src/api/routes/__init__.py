"""API routes package.

This package contains FastAPI routers for all REST API endpoints.
Routers are organized by domain:

- health: Health check endpoints
- availability: Date availability checking (US1)
- pricing: Pricing and rates (US2)
- reservations: Booking management (US3)
- payments: Payment processing (US4)
- guests: Guest verification and profiles (US5)
- property: Property information (US6)
- area: Local area information (US7)

All routers are registered in main.py with /api prefix.
"""

from api.routes.area import router as area_router
from api.routes.availability import router as availability_router
from api.routes.guests import router as guests_router
from api.routes.health import router as health_router
from api.routes.payments import router as payments_router
from api.routes.pricing import router as pricing_router
from api.routes.property import router as property_router
from api.routes.reservations import router as reservations_router

__all__ = [
    "area_router",
    "availability_router",
    "guests_router",
    "health_router",
    "payments_router",
    "pricing_router",
    "property_router",
    "reservations_router",
]
