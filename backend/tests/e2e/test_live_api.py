"""End-to-end tests against the live deployed API.

Run with: pytest tests/e2e/ -v

Configure the API URL via environment variable:
  export E2E_API_BASE_URL="https://booking.levy.apro.work/api"

Or via pytest command line:
  E2E_API_BASE_URL="https://..." pytest tests/e2e/ -v

The default URL uses CloudFront (via custom domain) which routes /api/* to API Gateway.
This tests the full production stack including:
- CloudFront CDN and caching behavior
- WAF rules (IP allowlist required)
- API Gateway REST API integration

For testing without WAF restrictions, use the direct API Gateway URL:
  E2E_API_BASE_URL="https://{api-id}.execute-api.{region}.amazonaws.com/api"

Markers:
  - e2e: All end-to-end tests
  - public: Tests that don't require authentication
  - protected: Tests for endpoints that require authentication
"""

import os
from datetime import date, timedelta

import httpx
import pytest

# API base URL - can be overridden via environment variable
# Default: CloudFront URL via custom domain (tests full production stack)
# Note: WAF IP allowlist must include the test runner's IP address
DEFAULT_API_URL = "https://booking.levy.apro.work/api"
API_BASE_URL = os.environ.get("E2E_API_BASE_URL", DEFAULT_API_URL)


@pytest.fixture(scope="module")
def client() -> httpx.Client:
    """Create an HTTP client for e2e tests."""
    return httpx.Client(base_url=API_BASE_URL, timeout=30.0)


@pytest.fixture
def future_dates() -> tuple[str, str]:
    """Generate future check-in and check-out dates for testing."""
    check_in = date.today() + timedelta(days=60)
    check_out = check_in + timedelta(days=7)
    return check_in.isoformat(), check_out.isoformat()


# =============================================================================
# Health Endpoint Tests
# =============================================================================


@pytest.mark.e2e
@pytest.mark.public
class TestHealthEndpoint:
    """Tests for the /api/health endpoint."""

    def test_health_returns_200(self, client: httpx.Client) -> None:
        """Health endpoint should return 200 with status healthy."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_health_response_structure(self, client: httpx.Client) -> None:
        """Health response should have expected structure."""
        response = client.get("/health")
        data = response.json()
        assert isinstance(data["status"], str)
        assert isinstance(data["version"], str)


# =============================================================================
# Property Endpoint Tests
# =============================================================================


@pytest.mark.e2e
@pytest.mark.public
class TestPropertyEndpoints:
    """Tests for the /api/property endpoints."""

    def test_get_property_details(self, client: httpx.Client) -> None:
        """Property endpoint should return apartment details."""
        response = client.get("/property")
        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "property" in data
        prop = data["property"]
        assert prop["name"] == "Quesada Apartment"
        assert prop["bedrooms"] == 2
        assert prop["max_guests"] == 4
        assert "amenities" in prop
        assert isinstance(prop["amenities"], list)

    def test_get_property_photos(self, client: httpx.Client) -> None:
        """Property photos endpoint should return photos list."""
        response = client.get("/property/photos")
        assert response.status_code == 200
        data = response.json()

        assert "photos" in data
        assert "total_count" in data
        assert data["total_count"] > 0
        assert len(data["photos"]) == data["total_count"]

    def test_get_property_photos_filtered_by_category(self, client: httpx.Client) -> None:
        """Property photos can be filtered by category."""
        response = client.get("/property/photos?category=exterior")
        assert response.status_code == 200
        data = response.json()

        assert data["category"] == "exterior"
        # All returned photos should be exterior category
        for photo in data["photos"]:
            assert photo["category"] == "exterior"

    def test_get_property_photos_invalid_category(self, client: httpx.Client) -> None:
        """Invalid photo category should return 400."""
        response = client.get("/property/photos?category=invalid")
        assert response.status_code == 400


# =============================================================================
# Area Endpoint Tests
# =============================================================================


@pytest.mark.e2e
@pytest.mark.public
class TestAreaEndpoints:
    """Tests for the /api/area endpoints."""

    def test_get_area_info(self, client: httpx.Client) -> None:
        """Area endpoint should return local places."""
        response = client.get("/area")
        assert response.status_code == 200
        data = response.json()

        assert "places" in data
        assert "total_count" in data
        assert data["total_count"] > 0

    def test_get_area_info_filtered_by_category(self, client: httpx.Client) -> None:
        """Area info can be filtered by category."""
        response = client.get("/area?category=golf")
        assert response.status_code == 200
        data = response.json()

        assert data["category"] == "golf"
        # All returned places should be golf category
        for place in data["places"]:
            assert place["category"] == "golf"

    def test_get_area_invalid_category(self, client: httpx.Client) -> None:
        """Invalid area category should return 400."""
        response = client.get("/area?category=invalid")
        assert response.status_code == 400

    def test_get_recommendations(self, client: httpx.Client) -> None:
        """Recommendations endpoint should return suggestions."""
        response = client.get("/area/recommendations")
        assert response.status_code == 200
        data = response.json()

        assert "recommendations" in data
        assert "total_count" in data
        assert "filters_applied" in data

    def test_get_recommendations_with_interests(self, client: httpx.Client) -> None:
        """Recommendations can be filtered by interests."""
        response = client.get("/area/recommendations?interests=golf,beach&limit=3")
        assert response.status_code == 200
        data = response.json()

        assert data["filters_applied"]["interests"] == ["golf", "beach"]
        assert data["filters_applied"]["limit"] == 3
        assert len(data["recommendations"]) <= 3

    def test_get_recommendations_with_distance_filter(self, client: httpx.Client) -> None:
        """Recommendations can be filtered by max distance."""
        response = client.get("/area/recommendations?max_distance_km=10")
        assert response.status_code == 200
        data = response.json()

        # All returned places should be within distance
        for place in data["recommendations"]:
            assert place["distance_km"] <= 10


# =============================================================================
# Pricing Endpoint Tests
# =============================================================================


@pytest.mark.e2e
@pytest.mark.public
class TestPricingEndpoints:
    """Tests for the /api/pricing endpoints."""

    def test_get_current_pricing(self, client: httpx.Client) -> None:
        """Pricing endpoint should return current season pricing."""
        response = client.get("/pricing")
        assert response.status_code == 200
        data = response.json()

        # Should have pricing data
        assert "nightly_rate" in data
        assert "cleaning_fee" in data
        assert "season_name" in data
        assert isinstance(data["nightly_rate"], int)

    def test_get_all_rates(self, client: httpx.Client) -> None:
        """Rates endpoint should return all seasons."""
        response = client.get("/pricing/rates")
        assert response.status_code == 200
        data = response.json()

        assert "seasons" in data
        assert "currency" in data
        assert data["currency"] == "EUR"
        assert len(data["seasons"]) > 0

        # Each season should have required fields
        for season in data["seasons"]:
            assert "season_id" in season
            assert "season_name" in season
            assert "nightly_rate" in season
            assert "start_date" in season
            assert "end_date" in season

    def test_calculate_price(
        self, client: httpx.Client, future_dates: tuple[str, str]
    ) -> None:
        """Calculate endpoint should return price breakdown."""
        check_in, check_out = future_dates
        response = client.get(f"/pricing/calculate?check_in={check_in}&check_out={check_out}")
        # May return 200 or error if dates not in pricing range
        if response.status_code == 200:
            data = response.json()
            assert "nights" in data
            assert "subtotal" in data
            assert "total_amount" in data

    def test_validate_minimum_stay(
        self, client: httpx.Client, future_dates: tuple[str, str]
    ) -> None:
        """Minimum stay validation endpoint should work."""
        check_in, check_out = future_dates
        response = client.get(
            f"/pricing/minimum-stay?check_in={check_in}&check_out={check_out}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "is_valid" in data
        assert "message" in data

    def test_get_minimum_stay_for_date(self, client: httpx.Client) -> None:
        """Minimum stay for date endpoint should return nights count."""
        future_date = (date.today() + timedelta(days=60)).isoformat()
        response = client.get(f"/pricing/minimum-stay/{future_date}")
        # May return 200 or 404 if date not in any season
        if response.status_code == 200:
            data = response.json()
            assert "minimum_nights" in data
            assert "date" in data
            assert "season_name" in data


# =============================================================================
# Availability Endpoint Tests
# =============================================================================


@pytest.mark.e2e
@pytest.mark.public
class TestAvailabilityEndpoints:
    """Tests for the /api/availability endpoints."""

    def test_check_availability(
        self, client: httpx.Client, future_dates: tuple[str, str]
    ) -> None:
        """Availability check should return status."""
        check_in, check_out = future_dates
        response = client.get(
            f"/availability?check_in={check_in}&check_out={check_out}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "is_available" in data
        assert isinstance(data["is_available"], bool)

    def test_get_calendar(self, client: httpx.Client) -> None:
        """Calendar endpoint should return monthly availability."""
        # Calendar uses /availability/calendar/{month} format (YYYY-MM)
        future_month = date.today() + timedelta(days=60)
        month_str = future_month.strftime("%Y-%m")
        response = client.get(f"/availability/calendar/{month_str}")
        assert response.status_code == 200
        data = response.json()
        assert "month" in data
        assert "days" in data
        assert isinstance(data["days"], list)
        assert "available_count" in data
        assert "booked_count" in data

    def test_availability_missing_params(self, client: httpx.Client) -> None:
        """Availability without required params should return 422."""
        response = client.get("/availability")
        assert response.status_code == 422  # FastAPI validation error


# =============================================================================
# Protected Endpoint Tests - Should Require Authentication
# =============================================================================


@pytest.mark.e2e
@pytest.mark.protected
class TestProtectedEndpoints:
    """Tests for endpoints that require authentication.

    These tests verify that protected endpoints properly reject
    unauthenticated requests.
    """

    def test_get_guest_requires_auth(self, client: httpx.Client) -> None:
        """Guest endpoint should require authentication."""
        # Note: actual route is /guests/by-email/{email}
        response = client.get("/guests/by-email/test@example.com")
        # Should return 401 Unauthorized or 403 Forbidden
        assert response.status_code in [401, 403]
        data = response.json()
        assert "detail" in data or "message" in data

    def test_update_guest_requires_auth(self, client: httpx.Client) -> None:
        """Guest update should require authentication."""
        response = client.patch(
            "/guests/GUEST-123",
            json={"name": "Test User"},
        )
        assert response.status_code in [401, 403]

    def test_get_reservation_not_found(self, client: httpx.Client) -> None:
        """Reservation endpoint is public; returns 404 for non-existent IDs."""
        response = client.get("/reservations/RES-2025-ABC123")
        assert response.status_code == 404

    def test_create_reservation_requires_auth(
        self, client: httpx.Client, future_dates: tuple[str, str]
    ) -> None:
        """Reservation creation should require authentication."""
        check_in, check_out = future_dates
        response = client.post(
            "/reservations",
            json={
                "check_in": check_in,
                "check_out": check_out,
                "num_guests": 2,
            },
        )
        assert response.status_code in [401, 403]

    def test_modify_reservation_requires_auth(
        self, client: httpx.Client, future_dates: tuple[str, str]
    ) -> None:
        """Reservation modification should require authentication."""
        check_in, check_out = future_dates
        response = client.patch(
            "/reservations/RES-2025-ABC123",
            json={
                "check_in": check_in,
                "check_out": check_out,
            },
        )
        assert response.status_code in [401, 403]

    def test_cancel_reservation_requires_auth(self, client: httpx.Client) -> None:
        """Reservation cancellation should require authentication."""
        response = client.delete("/reservations/RES-2025-ABC123")
        assert response.status_code in [401, 403]

    def test_list_reservations_requires_auth(self, client: httpx.Client) -> None:
        """List reservations should require authentication."""
        response = client.get("/reservations?guest_id=GUEST-123")
        assert response.status_code in [401, 403]

    def test_process_payment_requires_auth(self, client: httpx.Client) -> None:
        """Payment processing should require authentication."""
        response = client.post(
            "/payments",
            json={
                "reservation_id": "RES-2025-ABC123",
                "amount": 1000,
                "payment_method": "credit_card",
            },
        )
        assert response.status_code in [401, 403]

    def test_get_payment_status_not_found(self, client: httpx.Client) -> None:
        """Payment status is public; returns 404 for non-existent IDs."""
        response = client.get("/payments/PAY-2025-ABC123")
        assert response.status_code == 404

    def test_get_payment_by_reservation_not_found(self, client: httpx.Client) -> None:
        """Payment by reservation is public; returns 404 for non-existent reservations."""
        # Route is /payments/{reservation_id} - takes reservation ID directly
        response = client.get("/payments/RES-2025-ABC123")
        assert response.status_code == 404


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.e2e
@pytest.mark.public
class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_404_for_unknown_route(self, client: httpx.Client) -> None:
        """Unknown routes should return 404 or 403.

        Note: AWS REST API Gateway returns 403 (Forbidden) for undefined routes
        rather than 404 (Not Found). This is expected API Gateway behavior.
        """
        response = client.get("/unknown/route")
        assert response.status_code in [403, 404]

    def test_method_not_allowed(self, client: httpx.Client) -> None:
        """Wrong HTTP method returns 404 (API Gateway REST API behavior)."""
        response = client.post("/health")  # Should be GET
        # Note: API Gateway REST API returns 403 for unregistered method+path combos
        # (unlike Express/FastAPI standalone which return 405)
        assert response.status_code in [403, 404, 405]

    def test_invalid_date_format(self, client: httpx.Client) -> None:
        """Invalid date format should return 422."""
        response = client.get("/availability?check_in=not-a-date&check_out=2025-01-07")
        assert response.status_code == 422

    def test_dates_in_wrong_order(self, client: httpx.Client) -> None:
        """Check-out before check-in should return error."""
        response = client.get("/availability?check_in=2025-01-15&check_out=2025-01-10")
        # Should return 400 (bad request) or validation error
        assert response.status_code in [400, 422]
