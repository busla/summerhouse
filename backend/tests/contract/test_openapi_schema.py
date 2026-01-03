"""Contract tests for OpenAPI schema generation.

These tests validate that the generated OpenAPI schema:
1. Matches the contract schema (openapi-output.schema.json)
2. Contains all required AWS API Gateway extensions
3. Properly classifies public vs protected routes
"""

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

# Test configuration - matches Terraform inputs
TEST_LAMBDA_ARN = "arn:aws:lambda:eu-west-1:123456789012:function:booking-api"
TEST_USER_POOL_ID = "eu-west-1_TestPool123"
TEST_CLIENT_ID = "test-client-id-12345"
TEST_CORS_ORIGINS = ["*"]


@pytest.fixture
def openapi_schema() -> dict:
    """Load the OpenAPI output schema for validation."""
    # Path is relative to repo root - tests run from backend/ directory
    # Use Path(__file__) to get absolute path
    test_dir = Path(__file__).parent
    repo_root = test_dir.parent.parent.parent  # backend/tests/contract -> backend -> repo root
    schema_path = repo_root / "specs/006-backend-workspace-openapi/contracts/openapi-output.schema.json"
    return json.loads(schema_path.read_text())


@pytest.fixture
def generated_openapi() -> dict:
    """Generate OpenAPI spec with test configuration."""
    from api.scripts.generate_openapi import generate_openapi

    return generate_openapi(
        lambda_arn=TEST_LAMBDA_ARN,
        cognito_user_pool_id=TEST_USER_POOL_ID,
        cognito_client_id=TEST_CLIENT_ID,
        cors_allow_origins=TEST_CORS_ORIGINS,
    )


class TestOpenAPISchemaContract:
    """Test suite for OpenAPI schema contract compliance."""

    def test_generated_openapi_matches_contract_schema(
        self, generated_openapi: dict, openapi_schema: dict
    ) -> None:
        """Generated OpenAPI must match the contract schema."""
        # Should not raise ValidationError
        validate(instance=generated_openapi, schema=openapi_schema)

    def test_openapi_version_is_3_0_x(self, generated_openapi: dict) -> None:
        """OpenAPI version must be 3.0.x for API Gateway compatibility."""
        version = generated_openapi["openapi"]
        assert version.startswith("3.0."), f"Expected 3.0.x, got {version}"

    def test_has_info_section(self, generated_openapi: dict) -> None:
        """OpenAPI must have info section with title and version."""
        info = generated_openapi["info"]
        assert "title" in info
        assert "version" in info

    def test_has_cors_configuration(self, generated_openapi: dict) -> None:
        """OpenAPI must have x-amazon-apigateway-cors at root level."""
        cors = generated_openapi.get("x-amazon-apigateway-cors")
        assert cors is not None, "Missing x-amazon-apigateway-cors"
        assert "allowOrigins" in cors
        assert "allowMethods" in cors
        assert "allowHeaders" in cors


class TestAWSIntegrations:
    """Test suite for AWS API Gateway integration configuration."""

    def test_all_operations_have_lambda_integration(
        self, generated_openapi: dict
    ) -> None:
        """Every operation must have x-amazon-apigateway-integration."""
        for path, path_item in generated_openapi["paths"].items():
            for method in ["get", "post", "put", "delete", "patch"]:
                if method not in path_item:
                    continue

                operation = path_item[method]
                integration = operation.get("x-amazon-apigateway-integration")
                assert integration is not None, (
                    f"Missing integration for {method.upper()} {path}"
                )

    def test_integration_type_is_aws_proxy(self, generated_openapi: dict) -> None:
        """All integrations must use AWS_PROXY type."""
        for path, path_item in generated_openapi["paths"].items():
            for method in ["get", "post", "put", "delete", "patch"]:
                if method not in path_item:
                    continue

                integration = path_item[method].get("x-amazon-apigateway-integration", {})
                assert integration.get("type") == "AWS_PROXY", (
                    f"Expected AWS_PROXY for {method.upper()} {path}"
                )

    def test_integration_uri_contains_lambda_arn(
        self, generated_openapi: dict
    ) -> None:
        """Integration URI must contain the Lambda ARN."""
        for path, path_item in generated_openapi["paths"].items():
            for method in ["get", "post", "put", "delete", "patch"]:
                if method not in path_item:
                    continue

                integration = path_item[method].get("x-amazon-apigateway-integration", {})
                uri = integration.get("uri", "")
                assert TEST_LAMBDA_ARN in uri, (
                    f"Lambda ARN not found in URI for {method.upper()} {path}"
                )

    def test_payload_format_version_is_2_0(self, generated_openapi: dict) -> None:
        """All integrations must use payloadFormatVersion 2.0."""
        for path, path_item in generated_openapi["paths"].items():
            for method in ["get", "post", "put", "delete", "patch"]:
                if method not in path_item:
                    continue

                integration = path_item[method].get("x-amazon-apigateway-integration", {})
                assert integration.get("payloadFormatVersion") == "2.0", (
                    f"Expected payloadFormatVersion 2.0 for {method.upper()} {path}"
                )


class TestJWTAuthorizer:
    """Test suite for JWT authorizer configuration."""

    def test_has_cognito_jwt_security_scheme(self, generated_openapi: dict) -> None:
        """Must have cognito-jwt security scheme in components."""
        schemes = generated_openapi.get("components", {}).get("securitySchemes", {})
        assert "cognito-jwt" in schemes, "Missing cognito-jwt security scheme"

    def test_security_scheme_type_is_oauth2(self, generated_openapi: dict) -> None:
        """Security scheme type must be oauth2."""
        scheme = generated_openapi["components"]["securitySchemes"]["cognito-jwt"]
        assert scheme["type"] == "oauth2"

    def test_has_jwt_authorizer_extension(self, generated_openapi: dict) -> None:
        """Must have x-amazon-apigateway-authorizer with JWT type."""
        scheme = generated_openapi["components"]["securitySchemes"]["cognito-jwt"]
        authorizer = scheme.get("x-amazon-apigateway-authorizer")
        assert authorizer is not None, "Missing x-amazon-apigateway-authorizer"
        assert authorizer["type"] == "jwt"

    def test_jwt_issuer_matches_cognito_url(self, generated_openapi: dict) -> None:
        """JWT issuer must be Cognito User Pool URL."""
        scheme = generated_openapi["components"]["securitySchemes"]["cognito-jwt"]
        authorizer = scheme["x-amazon-apigateway-authorizer"]
        jwt_config = authorizer["jwtConfiguration"]

        expected_issuer = (
            f"https://cognito-idp.eu-west-1.amazonaws.com/{TEST_USER_POOL_ID}"
        )
        assert jwt_config["issuer"] == expected_issuer

    def test_jwt_audience_contains_client_id(self, generated_openapi: dict) -> None:
        """JWT audience must contain the Cognito client ID."""
        scheme = generated_openapi["components"]["securitySchemes"]["cognito-jwt"]
        authorizer = scheme["x-amazon-apigateway-authorizer"]
        jwt_config = authorizer["jwtConfiguration"]

        assert TEST_CLIENT_ID in jwt_config["audience"]


class TestRouteSecurityClassification:
    """Test suite for route security classification.

    These tests verify that routes are correctly marked as public or protected
    based on the presence of require_auth dependency.
    """

    def test_all_operations_have_security_field(self, generated_openapi: dict) -> None:
        """Every operation must have explicit security field."""
        for path, path_item in generated_openapi["paths"].items():
            for method in ["get", "post", "put", "delete", "patch"]:
                if method not in path_item:
                    continue

                operation = path_item[method]
                assert "security" in operation, (
                    f"Missing security field for {method.upper()} {path}"
                )

    def test_public_routes_have_empty_security(self, generated_openapi: dict) -> None:
        """Public routes must have security: []."""
        # Public routes that don't require JWT authentication
        # Note: Routes are at root level; REST API stage 'api' provides /api prefix
        public_routes = [
            # Health/ping
            ("get", "/ping"),
            ("get", "/health"),
            # Availability (public inquiry)
            ("get", "/availability"),
            ("get", "/availability/calendar/{month}"),
            # Pricing (public inquiry)
            ("get", "/pricing"),
            ("get", "/pricing/rates"),
            ("get", "/pricing/minimum-stay"),
            ("get", "/pricing/minimum-stay/{date}"),
            ("get", "/pricing/calculate"),
            # Property (public info)
            ("get", "/property"),
            ("get", "/property/photos"),
            # Area (public info)
            ("get", "/area"),
            ("get", "/area/recommendations"),
            # Guest verification (public to initiate)
            ("post", "/guests/verify"),
            ("post", "/guests/verify/confirm"),
            # Reservation lookup by ID (public for status check)
            ("get", "/reservations/{reservation_id}"),
            # Payment status lookup (public for status check)
            ("get", "/payments/{reservation_id}"),
        ]

        for method, path in public_routes:
            path_item = generated_openapi["paths"].get(path, {})
            if method not in path_item:
                continue  # Route may not exist yet

            operation = path_item[method]
            assert operation.get("security") == [], (
                f"Expected empty security for public route {method.upper()} {path}"
            )

    def test_protected_routes_have_jwt_security(self, generated_openapi: dict) -> None:
        """Protected routes must require cognito-jwt authentication."""
        # Routes that require JWT authentication
        # Note: Routes are at root level; REST API stage 'api' provides /api prefix
        protected_routes = [
            # Guest profile (owner only)
            ("get", "/guests/by-email/{email}"),
            ("patch", "/guests/{guest_id}"),
            # Reservations (authenticated operations)
            ("get", "/reservations"),  # List user's own reservations
            ("post", "/reservations"),
            ("patch", "/reservations/{reservation_id}"),
            ("delete", "/reservations/{reservation_id}"),
            # Payments (authenticated operations)
            ("post", "/payments"),
            ("post", "/payments/{reservation_id}/retry"),
            # Customers (authenticated profile management)
            ("get", "/customers/me"),
            ("post", "/customers/me"),
            ("put", "/customers/me"),
        ]

        for method, path in protected_routes:
            path_item = generated_openapi["paths"].get(path, {})
            if method not in path_item:
                continue  # Route may not exist yet

            operation = path_item[method]
            security = operation.get("security", [])
            # Should have cognito-jwt security requirement
            has_jwt = any("cognito-jwt" in s for s in security if isinstance(s, dict))
            assert has_jwt, (
                f"Expected cognito-jwt security for protected route {method.upper()} {path}"
            )


class TestCORSConfiguration:
    """Test suite for CORS configuration."""

    def test_cors_allow_origins_matches_config(self, generated_openapi: dict) -> None:
        """CORS allowOrigins must match configuration."""
        cors = generated_openapi["x-amazon-apigateway-cors"]
        assert cors["allowOrigins"] == TEST_CORS_ORIGINS

    def test_cors_includes_standard_methods(self, generated_openapi: dict) -> None:
        """CORS must allow standard HTTP methods."""
        cors = generated_openapi["x-amazon-apigateway-cors"]
        required_methods = {"GET", "POST", "PUT", "DELETE", "OPTIONS"}
        assert required_methods.issubset(set(cors["allowMethods"]))

    def test_cors_includes_authorization_header(self, generated_openapi: dict) -> None:
        """CORS must allow Authorization header for JWT."""
        cors = generated_openapi["x-amazon-apigateway-cors"]
        assert "Authorization" in cors["allowHeaders"]

    def test_cors_allows_credentials_for_specific_origins(
        self, generated_openapi: dict
    ) -> None:
        """CORS allowCredentials depends on origin configuration.

        AWS API Gateway security constraint: allowCredentials cannot be true
        when allowOrigins is ["*"]. This test uses wildcard origins, so
        allowCredentials must be False.
        """
        cors = generated_openapi["x-amazon-apigateway-cors"]
        # With TEST_CORS_ORIGINS = ["*"], credentials must be False
        assert cors.get("allowCredentials") is False


class TestAllEndpointsExist:
    """Test suite verifying all 28 business endpoints exist in OpenAPI spec.

    Organized by user story per spec 007-tools-api-endpoints.
    """

    # All expected endpoints organized by domain
    # Note: Routes are at root level; REST API stage 'api' provides /api prefix in URL
    EXPECTED_ENDPOINTS = {
        # Health & System
        "health": [
            ("get", "/ping"),
            ("get", "/health"),
        ],
        # US1: Availability
        "availability": [
            ("get", "/availability"),
            ("get", "/availability/calendar/{month}"),
        ],
        # US2: Pricing
        "pricing": [
            ("get", "/pricing"),
            ("get", "/pricing/rates"),
            ("get", "/pricing/minimum-stay"),
            ("get", "/pricing/minimum-stay/{date}"),
            ("get", "/pricing/calculate"),
        ],
        # US3: Reservations
        "reservations": [
            ("get", "/reservations"),
            ("post", "/reservations"),
            ("get", "/reservations/{reservation_id}"),
            ("patch", "/reservations/{reservation_id}"),
            ("delete", "/reservations/{reservation_id}"),
        ],
        # US4: Payments
        "payments": [
            ("post", "/payments"),
            ("get", "/payments/{reservation_id}"),
            ("post", "/payments/{reservation_id}/retry"),
        ],
        # US5: Guests
        "guests": [
            ("post", "/guests/verify"),
            ("post", "/guests/verify/confirm"),
            ("get", "/guests/by-email/{email}"),
            ("patch", "/guests/{guest_id}"),
        ],
        # US6: Property
        "property": [
            ("get", "/property"),
            ("get", "/property/photos"),
        ],
        # US7: Area
        "area": [
            ("get", "/area"),
            ("get", "/area/recommendations"),
        ],
        # US8: Customers (authenticated profile management)
        "customers": [
            ("get", "/customers/me"),
            ("post", "/customers/me"),
            ("put", "/customers/me"),
        ],
    }

    def test_all_business_endpoints_exist(self, generated_openapi: dict) -> None:
        """Verify all 28 business endpoints are present in the OpenAPI spec."""
        missing = []
        paths = generated_openapi.get("paths", {})

        for domain, endpoints in self.EXPECTED_ENDPOINTS.items():
            for method, path in endpoints:
                path_item = paths.get(path, {})
                if method not in path_item:
                    missing.append(f"{method.upper()} {path} ({domain})")

        assert not missing, f"Missing endpoints:\n" + "\n".join(missing)

    def test_endpoint_count_matches_expected(self, generated_openapi: dict) -> None:
        """Total business endpoint count should match expected."""
        expected_count = sum(
            len(endpoints) for endpoints in self.EXPECTED_ENDPOINTS.values()
        )
        # Count actual endpoints (excluding framework routes like /docs, /openapi.json)
        # Routes are at root level; REST API stage 'api' provides /api prefix in URL
        actual_count = 0
        for path, path_item in generated_openapi.get("paths", {}).items():
            # Skip OpenAPI framework routes
            if path in ["/docs", "/openapi.json", "/redoc"]:
                continue
            for method in ["get", "post", "put", "delete", "patch"]:
                if method in path_item:
                    actual_count += 1

        assert actual_count >= expected_count, (
            f"Expected at least {expected_count} endpoints, found {actual_count}"
        )

    @pytest.mark.parametrize(
        "domain",
        ["health", "availability", "pricing", "reservations", "payments", "guests", "property", "area", "customers"],
    )
    def test_domain_endpoints_complete(
        self, generated_openapi: dict, domain: str
    ) -> None:
        """Each domain must have all its expected endpoints."""
        paths = generated_openapi.get("paths", {})
        endpoints = self.EXPECTED_ENDPOINTS[domain]
        missing = []

        for method, path in endpoints:
            path_item = paths.get(path, {})
            if method not in path_item:
                missing.append(f"{method.upper()} {path}")

        assert not missing, f"Missing {domain} endpoints:\n" + "\n".join(missing)
