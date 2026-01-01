"""Custom API documentation with OAuth2 security annotations.

This module provides /docs and /openapi.json endpoints that serve FastAPI's
native OpenAPI schema enhanced with proper OAuth2 Bearer security scheme.

Protected endpoints (those with require_auth dependency) are annotated with
security requirements, showing lock icons and the Authorize button in Swagger UI.
"""

from functools import lru_cache
from typing import Any

from fastapi import APIRouter
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter(tags=["Documentation"])


def _get_protected_routes() -> dict[str, list[str]]:
    """Extract routes that have require_auth dependency.

    Inspects FastAPI routes to find which have SecurityRequirement dependencies.

    Returns:
        Dict mapping "METHOD /path" to list of required scopes.
    """
    from api.main import app
    from api.security import SecurityRequirement

    protected: dict[str, list[str]] = {}

    for route in app.routes:
        # Skip non-API routes (mounts, etc.)
        if not hasattr(route, "methods") or not hasattr(route, "dependant"):
            continue

        # Check dependencies for SecurityRequirement
        dependant = route.dependant
        for dependency in dependant.dependencies:
            call = dependency.call
            if call is None:
                continue

            # Get the return annotation to check if it's SecurityRequirement
            return_annotation = getattr(call, "__annotations__", {}).get("return")
            if return_annotation is SecurityRequirement:
                for method in route.methods:
                    if method == "HEAD":
                        continue  # Skip HEAD, it mirrors GET
                    route_key = f"{method} {route.path}"
                    # Extract scopes if available (empty list = authenticated, no specific scopes)
                    protected[route_key] = []

    return protected


@lru_cache
def get_enhanced_openapi_schema() -> dict[str, Any]:
    """Generate FastAPI's native OpenAPI schema with OAuth2 security.

    Adds:
    - servers[].url = "/api" (API Gateway stage prefix)
    - OAuth2 Bearer security scheme to components.securitySchemes
    - Security requirements to protected routes (those with require_auth)

    Returns:
        OpenAPI schema dict with proper security annotations.
    """
    from api.main import app

    # Generate native FastAPI OpenAPI schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Set server base path (API Gateway stage adds /api prefix)
    openapi_schema["servers"] = [{"url": "/api"}]

    # Add OAuth2 Bearer security scheme
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    if "securitySchemes" not in openapi_schema["components"]:
        openapi_schema["components"]["securitySchemes"] = {}

    openapi_schema["components"]["securitySchemes"]["bearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": (
            "JWT token from Cognito authentication. "
            "Use the /auth/login endpoint to obtain a token."
        ),
    }

    # Get protected routes and add security requirements
    protected_routes = _get_protected_routes()

    for path, methods in openapi_schema.get("paths", {}).items():
        for method, operation in methods.items():
            if method.upper() in ("OPTIONS", "HEAD"):
                continue
            if not isinstance(operation, dict):
                continue

            route_key = f"{method.upper()} {path}"
            if route_key in protected_routes:
                operation["security"] = [{"bearerAuth": []}]
            else:
                operation["security"] = []

    return openapi_schema


@router.get("/openapi.json")
async def get_openapi_schema() -> JSONResponse:
    """Serve the OpenAPI schema with OAuth2 security annotations.

    This schema includes:
    - OAuth2 Bearer security scheme
    - Security requirements on protected endpoints (lock icons)
    - Standard FastAPI OpenAPI output (no AWS-specific extensions)
    """
    schema = get_enhanced_openapi_schema()
    return JSONResponse(content=schema)


@router.get("/docs")
async def swagger_ui_docs() -> HTMLResponse:
    """Serve Swagger UI with OAuth2 authentication support.

    Features:
    - Authorize button for JWT Bearer authentication
    - Lock icons on protected endpoints
    - Try-it-out functionality with automatic Authorization header
    """
    return get_swagger_ui_html(
        openapi_url="openapi.json",  # Relative URL: resolves to /api/openapi.json
        title="Booking Platform API - Swagger UI",
        swagger_js_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css",
    )
