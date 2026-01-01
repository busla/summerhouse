#!/usr/bin/env python3
"""Generate OpenAPI schema with AWS API Gateway extensions.

This script generates an OpenAPI 3.0.1 specification from the FastAPI app
and adds AWS-specific extensions for API Gateway (HTTP API or REST API):

HTTP API (api_type="http"):
- x-amazon-apigateway-integration: Lambda proxy with AWS_PROXY type
- x-amazon-apigateway-cors: CORS configuration at root level
- x-amazon-apigateway-authorizer: JWT authorizer in securitySchemes

REST API (api_type="rest"):
- x-amazon-apigateway-integration: Lambda proxy with aws_proxy type (lowercase)
- OPTIONS methods with mock integration for CORS (per-path)
- x-amazon-apigateway-authorizer: cognito_user_pools with providerARNs

Usage:
    As Terraform external data source (reads JSON from stdin):
        echo '{"lambda_arn": "...", "cognito_user_pool_id": "...", "api_type": "rest", ...}' | \
            python generate_openapi.py

    Direct invocation for testing:
        python generate_openapi.py --test
        python generate_openapi.py --test --api-type rest

Output:
    JSON to stdout: {"openapi_spec": "<json-encoded-openapi>"}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class OpenAPIGeneratorConfig(BaseModel):
    """Configuration for OpenAPI generation script.

    Values come from stdin JSON (Terraform external data source).
    """

    # Required: Lambda integration
    lambda_arn: str = Field(
        ...,
        description="Full Lambda ARN for API integration",
    )

    # Required: Cognito JWT authorizer
    cognito_user_pool_id: str = Field(
        ...,
        description="Cognito User Pool ID (format: {region}_{id})",
    )
    cognito_client_id: str = Field(
        ...,
        description="Cognito App Client ID (used by HTTP API, ignored by REST API)",
    )

    # Optional: CORS configuration
    cors_allow_origins: list[str] = Field(
        default=["*"],
        description="Allowed CORS origins",
    )

    # API Gateway type (T003)
    api_type: Literal["http", "rest"] = Field(
        default="http",
        description="API Gateway type: 'http' (HTTP API) or 'rest' (REST API)",
    )

    # AWS Account ID - required for REST API Cognito authorizer ARN (T004)
    aws_account_id: str | None = Field(
        default=None,
        description="AWS Account ID (required for REST API cognito_user_pools authorizer)",
    )

    @field_validator("lambda_arn")
    @classmethod
    def validate_lambda_arn(cls, v: str) -> str:
        """Validate Lambda ARN format."""
        if not v.startswith("arn:aws:lambda:"):
            raise ValueError(
                f"Invalid Lambda ARN: must start with 'arn:aws:lambda:', got {v}"
            )
        parts = v.split(":")
        if len(parts) < 7:
            raise ValueError(f"Invalid Lambda ARN: expected 7+ parts, got {len(parts)}")
        return v

    @field_validator("cognito_user_pool_id")
    @classmethod
    def validate_user_pool_id(cls, v: str) -> str:
        """Validate Cognito User Pool ID format."""
        if "_" not in v:
            raise ValueError(
                f"Invalid User Pool ID: expected format {{region}}_{{id}}, got {v}"
            )
        return v

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from JSON string if needed.

        Terraform passes arrays as JSON-encoded strings.
        """
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
            # Single origin string
            return [v]
        return v

    @model_validator(mode="after")
    def validate_rest_api_requires_account_id(self) -> "OpenAPIGeneratorConfig":
        """Validate that REST API type requires aws_account_id."""
        if self.api_type == "rest" and not self.aws_account_id:
            raise ValueError(
                "aws_account_id is required when api_type='rest' "
                "(needed for Cognito authorizer providerARNs)"
            )
        return self


class ScriptError(Exception):
    """Structured error for OpenAPI generation script."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for JSON output."""
        return {
            "error": True,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }

    def exit(self) -> None:
        """Print error to stderr and exit with non-zero status."""
        print(json.dumps(self.to_dict()), file=sys.stderr)
        sys.exit(1)


def get_lambda_integration_uri(lambda_arn: str) -> str:
    """Build API Gateway Lambda integration URI from Lambda ARN.

    Args:
        lambda_arn: Full Lambda ARN
            (e.g., arn:aws:lambda:eu-west-1:123456789012:function:my-func)

    Returns:
        API Gateway integration URI format.
    """
    # Parse region from ARN: arn:aws:lambda:{region}:{account}:function:{name}
    parts = lambda_arn.split(":")
    region = parts[3]
    return (
        f"arn:aws:apigateway:{region}:lambda:path/2015-03-31"
        f"/functions/{lambda_arn}/invocations"
    )


def get_jwt_issuer(user_pool_id: str) -> str:
    """Build Cognito JWT issuer URL from User Pool ID.

    Args:
        user_pool_id: Cognito User Pool ID (format: {region}_{id})

    Returns:
        Cognito issuer URL.
    """
    # Extract region from user pool ID (format: {region}_{id})
    region = user_pool_id.split("_")[0]
    return f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"


def get_cognito_user_pool_arn(user_pool_id: str, aws_account_id: str) -> str:
    """Build Cognito User Pool ARN from User Pool ID and AWS Account ID.

    Args:
        user_pool_id: Cognito User Pool ID (format: {region}_{id})
        aws_account_id: AWS Account ID

    Returns:
        Full Cognito User Pool ARN for REST API authorizer providerARNs.
    """
    # Extract region from user pool ID (format: {region}_{id})
    region = user_pool_id.split("_")[0]
    return f"arn:aws:cognito-idp:{region}:{aws_account_id}:userpool/{user_pool_id}"


def generate_openapi(
    lambda_arn: str,
    cognito_user_pool_id: str,
    cognito_client_id: str,
    cors_allow_origins: list[str] | None = None,
    api_type: Literal["http", "rest"] = "http",
    aws_account_id: str | None = None,
) -> dict[str, Any]:
    """Generate OpenAPI schema with AWS API Gateway extensions.

    Args:
        lambda_arn: Full Lambda ARN for integration.
        cognito_user_pool_id: Cognito User Pool ID.
        cognito_client_id: Cognito App Client ID (used by HTTP API only).
        cors_allow_origins: List of allowed CORS origins.
        api_type: API Gateway type - "http" (HTTP API) or "rest" (REST API).
        aws_account_id: AWS Account ID (required for REST API authorizer).

    Returns:
        OpenAPI schema dict with AWS extensions.
    """
    # Import FastAPI app - lazy import to avoid slow startup
    try:
        from fastapi.openapi.utils import get_openapi

        from api.main import app
    except ImportError as e:
        raise ScriptError(
            code="IMPORT_ERROR",
            message=f"Failed to import FastAPI app: {e}",
            details={"import_error": str(e)},
        ) from e

    # Get base OpenAPI schema from FastAPI
    try:
        openapi = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version="3.0.1",  # API Gateway supports 3.0.x
            description=app.description,
            routes=app.routes,
        )
    except Exception as e:
        raise ScriptError(
            code="GENERATION_ERROR",
            message=f"Failed to generate OpenAPI: {e}",
            details={"error": str(e)},
        ) from e

    # Build integration URI
    integration_uri = get_lambda_integration_uri(lambda_arn)

    # CORS configuration differs by API type
    origins = cors_allow_origins or ["*"]
    allow_credentials = "*" not in origins  # Only allow credentials with specific origins

    # HTTP API: Add x-amazon-apigateway-cors at root level
    # REST API: Will add OPTIONS methods per-path below
    if api_type == "http":
        openapi["x-amazon-apigateway-cors"] = {
            "allowOrigins": origins,
            "allowMethods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
            "allowHeaders": [
                "Content-Type",
                "Authorization",
                "X-Requested-With",
                "X-Amz-Date",
            ],
            "exposeHeaders": ["X-Request-Id"],
            "maxAge": 86400,
            "allowCredentials": allow_credentials,
        }

    # Add securitySchemes with authorizer (type differs by API type)
    if "components" not in openapi:
        openapi["components"] = {}
    if "securitySchemes" not in openapi["components"]:
        openapi["components"]["securitySchemes"] = {}

    # T007, T008, T010: Different authorizer configuration by API type
    if api_type == "http":
        # HTTP API: JWT authorizer with client ID audience
        openapi["components"]["securitySchemes"]["cognito-jwt"] = {
            "type": "oauth2",
            "x-amazon-apigateway-authorizer": {
                "type": "jwt",
                "identitySource": "$request.header.Authorization",
                "jwtConfiguration": {
                    "issuer": get_jwt_issuer(cognito_user_pool_id),
                    "audience": [cognito_client_id],
                },
            },
            # OAuth2 flows definition (required for valid OpenAPI)
            "flows": {
                "implicit": {
                    "authorizationUrl": f"{get_jwt_issuer(cognito_user_pool_id)}/oauth2/authorize",
                    "scopes": {
                        "openid": "OpenID Connect scope",
                        "email": "Email address scope",
                        "profile": "User profile scope",
                    },
                }
            },
        }
    else:
        # REST API: cognito_user_pools authorizer with providerARNs (T007, T008, T010)
        # Note: aws_account_id is required and validated by OpenAPIGeneratorConfig
        assert aws_account_id is not None, "aws_account_id required for REST API"
        openapi["components"]["securitySchemes"]["CognitoAuthorizer"] = {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "x-amazon-apigateway-authtype": "cognito_user_pools",
            "x-amazon-apigateway-authorizer": {
                "type": "cognito_user_pools",
                "providerARNs": [
                    get_cognito_user_pool_arn(cognito_user_pool_id, aws_account_id)
                ],
            },
        }

    # Determine security scheme name based on API type
    security_scheme_name = "cognito-jwt" if api_type == "http" else "CognitoAuthorizer"

    # Add x-amazon-apigateway-integration to all path operations
    # and determine security requirements based on require_auth dependency
    protected_routes = _get_protected_routes(app)

    # Track paths that need OPTIONS methods for REST API CORS
    paths_needing_options: set[str] = set()

    for path, path_item in openapi.get("paths", {}).items():
        for method in ["get", "post", "put", "delete", "patch", "options", "head"]:
            if method not in path_item:
                continue

            operation = path_item[method]

            # T005, T006: Integration type and payload handling differ by API type
            if api_type == "http":
                # HTTP API: AWS_PROXY (uppercase) with payloadFormatVersion
                operation["x-amazon-apigateway-integration"] = {
                    "type": "AWS_PROXY",
                    "httpMethod": "POST",
                    "uri": integration_uri,
                    "payloadFormatVersion": "2.0",
                }
            else:
                # REST API: aws_proxy (lowercase) with passthroughBehavior
                operation["x-amazon-apigateway-integration"] = {
                    "type": "aws_proxy",
                    "httpMethod": "POST",
                    "uri": integration_uri,
                    "passthroughBehavior": "when_no_match",
                }

            # Add security requirement if route is protected
            route_key = f"{method.upper()} {path}"
            if route_key in protected_routes:
                operation["security"] = [{security_scheme_name: protected_routes[route_key]}]
            else:
                # Explicitly mark as public (no security)
                operation["security"] = []

            # Track paths for REST API OPTIONS generation (skip if OPTIONS already exists)
            if api_type == "rest" and method != "options":
                paths_needing_options.add(path)

    # T009: Generate OPTIONS methods with mock integration for REST API CORS
    if api_type == "rest":
        _add_options_methods_for_cors(openapi, paths_needing_options, origins)

    return openapi


def _add_options_methods_for_cors(
    openapi: dict[str, Any],
    paths: set[str],
    origins: list[str],
) -> None:
    """Add OPTIONS methods with mock integration for REST API CORS.

    REST API doesn't support the x-amazon-apigateway-cors extension like HTTP API.
    Instead, we must explicitly add OPTIONS methods with mock integration to each path.

    Args:
        openapi: OpenAPI schema dict to modify in place.
        paths: Set of paths that need OPTIONS methods.
        origins: List of allowed CORS origins.
    """
    # Determine CORS header values
    allow_origin = origins[0] if len(origins) == 1 else ",".join(origins)
    # For wildcard, just use *
    if "*" in origins:
        allow_origin = "*"

    allow_headers = "Content-Type,Authorization,X-Requested-With,X-Amz-Date"
    allow_methods = "GET,POST,PUT,DELETE,OPTIONS,PATCH"

    for path in paths:
        path_item = openapi["paths"].get(path, {})

        # Skip if OPTIONS already exists
        if "options" in path_item:
            continue

        # Collect methods defined on this path for Access-Control-Allow-Methods
        defined_methods = [
            m.upper()
            for m in ["get", "post", "put", "delete", "patch", "head"]
            if m in path_item
        ]
        if defined_methods:
            path_allow_methods = ",".join(defined_methods + ["OPTIONS"])
        else:
            path_allow_methods = allow_methods

        # T009: Add OPTIONS method with mock integration
        path_item["options"] = {
            "summary": "CORS preflight",
            "description": "Handles CORS preflight requests",
            "responses": {
                "200": {
                    "description": "CORS preflight response",
                    "headers": {
                        "Access-Control-Allow-Origin": {
                            "schema": {"type": "string"},
                        },
                        "Access-Control-Allow-Methods": {
                            "schema": {"type": "string"},
                        },
                        "Access-Control-Allow-Headers": {
                            "schema": {"type": "string"},
                        },
                    },
                }
            },
            # No security for OPTIONS (CORS preflight must be public)
            "security": [],
            # Mock integration for REST API CORS
            "x-amazon-apigateway-integration": {
                "type": "mock",
                "requestTemplates": {
                    "application/json": '{"statusCode": 200}',
                },
                "responses": {
                    "default": {
                        "statusCode": "200",
                        "responseParameters": {
                            "method.response.header.Access-Control-Allow-Methods": f"'{path_allow_methods}'",
                            "method.response.header.Access-Control-Allow-Headers": f"'{allow_headers}'",
                            "method.response.header.Access-Control-Allow-Origin": f"'{allow_origin}'",
                        },
                    }
                },
            },
        }


def _get_protected_routes(app: Any) -> dict[str, list[str]]:
    """Extract routes that have require_auth dependency.

    Inspects FastAPI routes to find which have SecurityRequirement dependencies.

    Args:
        app: FastAPI application instance.

    Returns:
        Dict mapping "METHOD /path" to list of required scopes.
    """
    from api.security import SecurityRequirement

    protected: dict[str, list[str]] = {}

    for route in app.routes:
        # Skip non-API routes (mounts, etc.)
        if not hasattr(route, "methods") or not hasattr(route, "dependant"):
            continue

        # Check dependencies for SecurityRequirement
        dependant = route.dependant
        for dependency in dependant.dependencies:
            # Check if this dependency returns SecurityRequirement
            call = dependency.call
            if call is None:
                continue

            # Get the return annotation or check the actual return
            return_annotation = getattr(call, "__annotations__", {}).get("return")
            if return_annotation is SecurityRequirement:
                # Found a protected route
                for method in route.methods:
                    if method == "HEAD":
                        continue  # Skip HEAD, it mirrors GET
                    route_key = f"{method} {route.path}"
                    # For now, all protected routes use empty scopes
                    # Future: extract scopes from the dependency
                    protected[route_key] = []

    return protected


def main() -> None:
    """Main entry point for OpenAPI generation script."""
    # Check for test mode
    if "--test" in sys.argv:
        # Determine API type from command line (default: http for backward compatibility)
        api_type: Literal["http", "rest"] = "rest" if "--api-type" in sys.argv and "rest" in sys.argv else "http"

        # Use test values
        config = OpenAPIGeneratorConfig(
            lambda_arn="arn:aws:lambda:eu-west-1:123456789012:function:booking-api",
            cognito_user_pool_id="eu-west-1_TestPool123",
            cognito_client_id="test-client-id-12345",
            cors_allow_origins=["*"],
            api_type=api_type,
            # REST API requires aws_account_id for Cognito authorizer providerARNs
            aws_account_id="123456789012" if api_type == "rest" else None,
        )
    else:
        # Read config from stdin (Terraform external data source)
        try:
            input_json = sys.stdin.read()
            if not input_json.strip():
                ScriptError(
                    code="INVALID_INPUT",
                    message="No input provided on stdin",
                    details={"hint": "Terraform external data source should provide JSON input"},
                ).exit()

            input_data = json.loads(input_json)
        except json.JSONDecodeError as e:
            ScriptError(
                code="INVALID_INPUT",
                message=f"Invalid JSON input: {e}",
                details={"input_preview": input_json[:100] if input_json else ""},
            ).exit()
            return  # For type checker

        # Parse and validate config
        try:
            config = OpenAPIGeneratorConfig(**input_data)
        except Exception as e:
            ScriptError(
                code="INVALID_INPUT",
                message=f"Invalid configuration: {e}",
                details={"received_keys": list(input_data.keys())},
            ).exit()
            return

    # Generate OpenAPI schema
    try:
        openapi = generate_openapi(
            lambda_arn=config.lambda_arn,
            cognito_user_pool_id=config.cognito_user_pool_id,
            cognito_client_id=config.cognito_client_id,
            cors_allow_origins=config.cors_allow_origins,
            api_type=config.api_type,
            aws_account_id=config.aws_account_id,
        )
    except ScriptError:
        raise
    except Exception as e:
        ScriptError(
            code="GENERATION_ERROR",
            message=f"Unexpected error during generation: {e}",
            details={"error_type": type(e).__name__},
        ).exit()
        return

    # Output for Terraform external data source
    # The openapi_spec is JSON-encoded as a string value
    output = {"openapi_spec": json.dumps(openapi)}
    print(json.dumps(output))


if __name__ == "__main__":
    main()
