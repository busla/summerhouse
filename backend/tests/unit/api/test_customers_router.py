"""Unit tests for customer router utilities (T026a).

Tests for _get_cognito_sub() helper which extracts the cognito_sub
from API Gateway-injected headers.

TDD Red Phase: These tests define expected behavior before implementation.

Trust Model:
- API Gateway validates JWT using Cognito authorizer
- After validation, API Gateway injects x-user-sub header with cognito sub claim
- Backend trusts this header since it comes from API Gateway, not client
"""

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from starlette.datastructures import Headers


class TestGetCognitoSub:
    """Test suite for _get_cognito_sub() helper function."""

    def test_extracts_cognito_sub_from_x_user_sub_header(self) -> None:
        """_get_cognito_sub returns cognito_sub from x-user-sub header."""
        # Import here to allow module to not exist yet (TDD Red Phase)
        from api.routes.customers import _get_cognito_sub

        # Arrange: Create mock request with x-user-sub header
        # (API Gateway injects this after JWT validation)
        mock_scope = {
            "type": "http",
            "path": "/customers/me",
            "headers": [
                (b"x-user-sub", b"cognito-sub-12345-abcdef"),
                (b"content-type", b"application/json"),
            ],
        }
        request = Request(scope=mock_scope)

        # Act
        result = _get_cognito_sub(request)

        # Assert
        assert result == "cognito-sub-12345-abcdef"

    def test_raises_401_when_x_user_sub_header_missing(self) -> None:
        """_get_cognito_sub raises HTTPException 401 when header is missing."""
        from api.routes.customers import _get_cognito_sub

        # Arrange: Request without x-user-sub header
        mock_scope = {
            "type": "http",
            "path": "/customers/me",
            "headers": [
                (b"content-type", b"application/json"),
            ],
        }
        request = Request(scope=mock_scope)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            _get_cognito_sub(request)

        assert exc_info.value.status_code == 401
        assert "authentication" in exc_info.value.detail.lower()

    def test_raises_401_when_x_user_sub_header_empty(self) -> None:
        """_get_cognito_sub raises HTTPException 401 when header is empty string."""
        from api.routes.customers import _get_cognito_sub

        # Arrange: Request with empty x-user-sub header
        mock_scope = {
            "type": "http",
            "path": "/customers/me",
            "headers": [
                (b"x-user-sub", b""),
                (b"content-type", b"application/json"),
            ],
        }
        request = Request(scope=mock_scope)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            _get_cognito_sub(request)

        assert exc_info.value.status_code == 401

    def test_handles_uuid_format_cognito_sub(self) -> None:
        """_get_cognito_sub handles standard UUID format cognito_sub."""
        from api.routes.customers import _get_cognito_sub

        # Cognito sub is typically a UUID
        cognito_sub = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        mock_scope = {
            "type": "http",
            "path": "/customers/me",
            "headers": [
                (b"x-user-sub", cognito_sub.encode()),
            ],
        }
        request = Request(scope=mock_scope)

        result = _get_cognito_sub(request)

        assert result == cognito_sub

    def test_header_name_is_case_insensitive(self) -> None:
        """_get_cognito_sub handles case variations in header name.

        HTTP headers are case-insensitive per RFC 7230.
        Starlette normalizes to lowercase internally.
        """
        from api.routes.customers import _get_cognito_sub

        # Arrange: Header with different case (Starlette normalizes to lowercase)
        mock_scope = {
            "type": "http",
            "path": "/customers/me",
            "headers": [
                (b"X-User-Sub", b"cognito-sub-uppercase"),
            ],
        }
        request = Request(scope=mock_scope)

        result = _get_cognito_sub(request)

        assert result == "cognito-sub-uppercase"

    def test_strips_whitespace_from_cognito_sub(self) -> None:
        """_get_cognito_sub strips leading/trailing whitespace."""
        from api.routes.customers import _get_cognito_sub

        mock_scope = {
            "type": "http",
            "path": "/customers/me",
            "headers": [
                (b"x-user-sub", b"  cognito-sub-with-spaces  "),
            ],
        }
        request = Request(scope=mock_scope)

        result = _get_cognito_sub(request)

        assert result == "cognito-sub-with-spaces"

    def test_raises_401_when_cognito_sub_is_whitespace_only(self) -> None:
        """_get_cognito_sub raises 401 when header contains only whitespace."""
        from api.routes.customers import _get_cognito_sub

        mock_scope = {
            "type": "http",
            "path": "/customers/me",
            "headers": [
                (b"x-user-sub", b"   "),
            ],
        }
        request = Request(scope=mock_scope)

        with pytest.raises(HTTPException) as exc_info:
            _get_cognito_sub(request)

        assert exc_info.value.status_code == 401


class TestGetCognitoSubDependency:
    """Test _get_cognito_sub as FastAPI dependency."""

    def test_can_be_used_as_fastapi_dependency(self) -> None:
        """_get_cognito_sub can be injected via Depends()."""
        from fastapi import Depends, FastAPI

        from api.routes.customers import _get_cognito_sub

        # Arrange: Create test app with endpoint using dependency
        app = FastAPI()

        @app.get("/test-auth")
        def test_endpoint(cognito_sub: str = Depends(_get_cognito_sub)) -> dict:
            return {"cognito_sub": cognito_sub}

        client = TestClient(app)

        # Act: Call with valid header
        response = client.get(
            "/test-auth",
            headers={"x-user-sub": "test-sub-123"},
        )

        # Assert
        assert response.status_code == 200
        assert response.json() == {"cognito_sub": "test-sub-123"}

    def test_dependency_returns_401_without_header(self) -> None:
        """Endpoint returns 401 when x-user-sub header missing."""
        from fastapi import Depends, FastAPI

        from api.routes.customers import _get_cognito_sub

        app = FastAPI()

        @app.get("/test-auth")
        def test_endpoint(cognito_sub: str = Depends(_get_cognito_sub)) -> dict:
            return {"cognito_sub": cognito_sub}

        client = TestClient(app)

        # Act: Call without header
        response = client.get("/test-auth")

        # Assert
        assert response.status_code == 401


# =============================================================================
# T029a-T031a: Customer Endpoint Tests (TDD Red Phase)
# =============================================================================


class TestGetCustomerMe:
    """Test suite for GET /customers/me endpoint (T029a).

    This endpoint returns the authenticated user's customer profile.
    Uses cognito_sub from x-user-sub header to look up the profile.
    """

    def test_returns_customer_profile_when_found(self) -> None:
        """GET /customers/me returns profile for authenticated user."""
        from unittest.mock import patch

        from fastapi import FastAPI

        from api.routes.customers import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Mock guest data from DynamoDB
        mock_guest = {
            "guest_id": "guest-uuid-12345",
            "email": "test@example.com",
            "cognito_sub": "cognito-sub-abc123",
            "name": "Test User",
            "phone": "+1234567890",
            "preferred_language": "en",
            "email_verified": True,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }

        with patch(
            "api.routes.customers.get_dynamodb_service"
        ) as mock_get_db:
            mock_db = mock_get_db.return_value
            mock_db.get_guest_by_cognito_sub.return_value = mock_guest

            response = client.get(
                "/customers/me",
                headers={"x-user-sub": "cognito-sub-abc123"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"
        assert data["preferred_language"] == "en"

    def test_returns_404_when_profile_not_found(self) -> None:
        """GET /customers/me returns 404 when no profile exists."""
        from unittest.mock import patch

        from fastapi import FastAPI

        from api.routes.customers import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch(
            "api.routes.customers.get_dynamodb_service"
        ) as mock_get_db:
            mock_db = mock_get_db.return_value
            mock_db.get_guest_by_cognito_sub.return_value = None

            response = client.get(
                "/customers/me",
                headers={"x-user-sub": "cognito-sub-nonexistent"},
            )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_returns_401_without_auth_header(self) -> None:
        """GET /customers/me returns 401 without x-user-sub header."""
        from fastapi import FastAPI

        from api.routes.customers import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/customers/me")

        assert response.status_code == 401


class TestCreateCustomerMe:
    """Test suite for POST /customers/me endpoint (T030a).

    This endpoint creates a new customer profile for the authenticated user.
    The cognito_sub comes from x-user-sub header.
    Email is extracted from x-user-email header (injected by API Gateway from JWT).
    """

    def test_creates_customer_profile_successfully(self) -> None:
        """POST /customers/me creates profile with provided data."""
        from unittest.mock import patch

        from fastapi import FastAPI

        from api.routes.customers import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch(
            "api.routes.customers.get_dynamodb_service"
        ) as mock_get_db:
            mock_db = mock_get_db.return_value
            # No existing profile
            mock_db.get_guest_by_cognito_sub.return_value = None
            mock_db.create_guest.return_value = True

            response = client.post(
                "/customers/me",
                headers={
                    "x-user-sub": "cognito-sub-new-user",
                    "x-user-email": "newuser@example.com",
                },
                json={
                    "name": "New User",
                    "phone": "+1987654321",
                    "preferred_language": "es",
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["name"] == "New User"
        assert data["preferred_language"] == "es"
        assert "guest_id" in data

    def test_returns_409_when_profile_already_exists(self) -> None:
        """POST /customers/me returns 409 if profile already exists."""
        from unittest.mock import patch

        from fastapi import FastAPI

        from api.routes.customers import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        existing_guest = {
            "guest_id": "existing-uuid",
            "cognito_sub": "cognito-sub-existing",
            "email": "existing@example.com",
        }

        with patch(
            "api.routes.customers.get_dynamodb_service"
        ) as mock_get_db:
            mock_db = mock_get_db.return_value
            mock_db.get_guest_by_cognito_sub.return_value = existing_guest

            response = client.post(
                "/customers/me",
                headers={
                    "x-user-sub": "cognito-sub-existing",
                    "x-user-email": "existing@example.com",
                },
                json={"name": "Duplicate User"},
            )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    def test_returns_401_without_auth_header(self) -> None:
        """POST /customers/me returns 401 without x-user-sub header."""
        from fastapi import FastAPI

        from api.routes.customers import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post(
            "/customers/me",
            json={"name": "Test User"},
        )

        assert response.status_code == 401

    def test_returns_400_without_email_header(self) -> None:
        """POST /customers/me returns 400 without x-user-email header."""
        from fastapi import FastAPI

        from api.routes.customers import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post(
            "/customers/me",
            headers={"x-user-sub": "cognito-sub-test"},
            json={"name": "Test User"},
        )

        assert response.status_code == 400
        assert "email" in response.json()["detail"].lower()

    def test_validates_name_min_length(self) -> None:
        """POST /customers/me validates name minimum length."""
        from fastapi import FastAPI

        from api.routes.customers import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post(
            "/customers/me",
            headers={
                "x-user-sub": "cognito-sub-test",
                "x-user-email": "test@example.com",
            },
            json={"name": "A"},  # Too short (min 2)
        )

        assert response.status_code == 422  # Validation error

    def test_validates_preferred_language_pattern(self) -> None:
        """POST /customers/me validates preferred_language is en or es."""
        from fastapi import FastAPI

        from api.routes.customers import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post(
            "/customers/me",
            headers={
                "x-user-sub": "cognito-sub-test",
                "x-user-email": "test@example.com",
            },
            json={"preferred_language": "fr"},  # Invalid
        )

        assert response.status_code == 422  # Validation error


class TestUpdateCustomerMe:
    """Test suite for PUT /customers/me endpoint (T031a).

    This endpoint updates the authenticated user's customer profile.
    Only provided fields are updated (partial update).
    """

    def test_updates_customer_profile_successfully(self) -> None:
        """PUT /customers/me updates profile fields."""
        from unittest.mock import patch

        from fastapi import FastAPI

        from api.routes.customers import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        existing_guest = {
            "guest_id": "guest-uuid-12345",
            "email": "test@example.com",
            "cognito_sub": "cognito-sub-abc123",
            "name": "Old Name",
            "phone": "+1234567890",
            "preferred_language": "en",
        }

        updated_guest = {
            **existing_guest,
            "name": "New Name",
            "preferred_language": "es",
        }

        with patch(
            "api.routes.customers.get_dynamodb_service"
        ) as mock_get_db:
            mock_db = mock_get_db.return_value
            mock_db.get_guest_by_cognito_sub.return_value = existing_guest
            mock_db.update_item.return_value = updated_guest

            response = client.put(
                "/customers/me",
                headers={"x-user-sub": "cognito-sub-abc123"},
                json={
                    "name": "New Name",
                    "preferred_language": "es",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["preferred_language"] == "es"

    def test_returns_404_when_profile_not_found(self) -> None:
        """PUT /customers/me returns 404 when no profile exists."""
        from unittest.mock import patch

        from fastapi import FastAPI

        from api.routes.customers import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch(
            "api.routes.customers.get_dynamodb_service"
        ) as mock_get_db:
            mock_db = mock_get_db.return_value
            mock_db.get_guest_by_cognito_sub.return_value = None

            response = client.put(
                "/customers/me",
                headers={"x-user-sub": "cognito-sub-nonexistent"},
                json={"name": "New Name"},
            )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_returns_401_without_auth_header(self) -> None:
        """PUT /customers/me returns 401 without x-user-sub header."""
        from fastapi import FastAPI

        from api.routes.customers import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.put(
            "/customers/me",
            json={"name": "New Name"},
        )

        assert response.status_code == 401

    def test_updates_only_provided_fields(self) -> None:
        """PUT /customers/me only updates fields that are provided."""
        from unittest.mock import patch

        from fastapi import FastAPI

        from api.routes.customers import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        existing_guest = {
            "guest_id": "guest-uuid-12345",
            "email": "test@example.com",
            "cognito_sub": "cognito-sub-abc123",
            "name": "Original Name",
            "phone": "+1234567890",
            "preferred_language": "en",
        }

        # Only name updated, phone preserved
        updated_guest = {
            **existing_guest,
            "name": "Updated Name",
        }

        with patch(
            "api.routes.customers.get_dynamodb_service"
        ) as mock_get_db:
            mock_db = mock_get_db.return_value
            mock_db.get_guest_by_cognito_sub.return_value = existing_guest
            mock_db.update_item.return_value = updated_guest

            response = client.put(
                "/customers/me",
                headers={"x-user-sub": "cognito-sub-abc123"},
                json={"name": "Updated Name"},  # Only name, no phone
            )

        assert response.status_code == 200
        # Verify update_item was called with only the name field
        mock_db.update_item.assert_called_once()
        call_kwargs = mock_db.update_item.call_args

        # The update expression should only contain name-related updates
        assert "name" in str(call_kwargs).lower()

    def test_validates_name_max_length(self) -> None:
        """PUT /customers/me validates name maximum length."""
        from fastapi import FastAPI

        from api.routes.customers import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.put(
            "/customers/me",
            headers={"x-user-sub": "cognito-sub-test"},
            json={"name": "A" * 101},  # Too long (max 100)
        )

        assert response.status_code == 422  # Validation error
