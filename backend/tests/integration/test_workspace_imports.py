"""Workspace import integration tests.

Validates that all three workspace packages (shared, api, agent) are correctly
installable and their public interfaces are accessible.
"""

import pytest


class TestSharedPackageImports:
    """Tests for shared package public interface."""

    def test_can_import_shared_package(self):
        """Shared package should be importable."""
        import shared

        assert hasattr(shared, "__version__")

    def test_can_import_models(self):
        """All public models should be importable from shared.models."""
        from shared.models import (
            # Enums
            AvailabilityStatus,
            PaymentMethod,
            PaymentProvider,
            PaymentStatus,
            ReservationStatus,
            TransactionStatus,
            # Guest
            Guest,
            GuestCreate,
            GuestUpdate,
            # Reservation
            Reservation,
            ReservationCreate,
            ReservationSummary,
            # Availability
            Availability,
            AvailabilityRange,
            AvailabilityResponse,
            # Pricing
            Pricing,
            PricingCreate,
            PriceCalculation,
            # Payment
            Payment,
            PaymentCreate,
            PaymentResult,
            # Verification
            VerificationCode,
            VerificationRequest,
            VerificationAttempt,
            VerificationResult,
            # Property
            Address,
            Coordinates,
            Photo,
            PhotoCategory,
            PhotosResponse,
            Property,
            PropertyDetailsResponse,
            PropertySummary,
            # Area Info
            AreaCategory,
            AreaInfo,
            AreaInfoResponse,
            RecommendationRequest,
            RecommendationResponse,
            # Errors
            BookingError,
            ErrorCode,
            ToolError,
        )

        # Verify a few key types are actually classes/enums
        assert hasattr(Guest, "model_fields")  # Pydantic model
        assert hasattr(ReservationStatus, "PENDING")  # Enum
        assert hasattr(Property, "model_fields")  # Pydantic model

    def test_can_import_services(self):
        """Key services should be importable from shared.services."""
        from shared.services.dynamodb import DynamoDBService, get_dynamodb_service

        assert callable(get_dynamodb_service)
        assert DynamoDBService is not None

    def test_can_import_tools(self):
        """Tools should be importable from shared.tools."""
        from shared.tools import ALL_TOOLS

        # Should have at least 10 tools
        assert len(ALL_TOOLS) >= 10


class TestApiPackageImports:
    """Tests for API package public interface."""

    def test_can_import_api_package(self):
        """API package should be importable."""
        import api

        assert hasattr(api, "__version__")

    def test_can_import_fastapi_app(self):
        """FastAPI app should be importable from api.main."""
        from api.main import app

        # Should be a FastAPI application
        assert app is not None
        assert hasattr(app, "routes")

    def test_can_import_routes(self):
        """Route modules should be importable."""
        from api.routes import health

        assert hasattr(health, "router") or hasattr(health, "ping")


class TestAgentPackageImports:
    """Tests for Agent package public interface."""

    def test_can_import_agent_package(self):
        """Agent package should be importable."""
        import agent

        assert hasattr(agent, "__version__")

    def test_can_import_booking_agent(self):
        """Booking agent should be importable."""
        from agent.booking_agent import get_agent

        assert callable(get_agent)


class TestCrossPackageDependencies:
    """Tests for cross-package dependencies."""

    def test_api_can_use_shared_models(self):
        """API package should be able to use shared models."""
        from shared.models import Guest
        from api.main import app

        # This validates that API can import and use shared types
        assert Guest is not None
        assert app is not None

    def test_agent_can_use_shared_tools(self):
        """Agent package should be able to use shared tools."""
        from shared.tools import ALL_TOOLS
        from agent.booking_agent import get_agent

        # This validates that agent can import and use shared tools
        assert len(ALL_TOOLS) > 0
        assert get_agent is not None
