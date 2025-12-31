"""API-specific request/response models.

This package contains Pydantic models specific to the REST API layer.
These models define request bodies and response schemas for endpoints.

Domain models (Reservation, Guest, Payment, etc.) are in shared.models
and should be reused here where appropriate.

Modules:
- common: Shared response wrappers and error models
- availability: Calendar and availability response models
- pricing: Pricing calculation response models
- reservations: Reservation request/response models
- payments: Payment request models
- guests: Guest verification response models
"""

__all__: list[str] = []
