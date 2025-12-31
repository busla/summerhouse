"""FastAPI application for Booking platform REST API.

This package provides REST endpoints for:
- Health checks
- Booking tools (availability, pricing, reservations, etc.)

NOTE: Agent invocation endpoints (/invoke-stream, /invoke, /reset) are handled
by the AgentCore Runtime (agent package), not this FastAPI app. This ensures
clean separation of concerns and independent deployment of API vs Agent.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from api.exceptions import register_exception_handlers
from api.routes.area import router as area_router
from api.routes.availability import router as availability_router
from api.routes.guests import router as guests_router
from api.routes.health import router as health_router
from api.routes.payments import router as payments_router
from api.routes.pricing import router as pricing_router
from api.routes.property import router as property_router
from api.routes.reservations import router as reservations_router

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Booking Platform API",
    description="REST API for authentication and booking operations",
    version="0.1.0",
)

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers for consistent error responses
register_exception_handlers(app)

# Include routers under /api prefix
# This matches CloudFront routing: /api/* → API Gateway
app.include_router(health_router, prefix="/api")
app.include_router(availability_router, prefix="/api")
app.include_router(pricing_router, prefix="/api")
app.include_router(reservations_router, prefix="/api")
app.include_router(payments_router, prefix="/api")
app.include_router(guests_router, prefix="/api")
app.include_router(property_router, prefix="/api")
app.include_router(area_router, prefix="/api")


@app.get("/api/ping")
async def ping() -> dict[str, Any]:
    """Root health check endpoint at /api/ping.

    Matches CloudFront path pattern /api/* → API Gateway.
    """
    return {
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
        "service": "booking-api",
    }


# Lambda handler - Mangum wraps FastAPI for AWS Lambda + API Gateway
handler = Mangum(app, lifespan="off")


def run_server(host: str = "0.0.0.0", port: int = 8080, reload: bool = True) -> None:
    """Run the FastAPI server.

    Args:
        host: Host to bind to (default: 0.0.0.0)
        port: Port to listen on (default: 8080)
        reload: Enable hot reload for development (default: True)
    """
    import uvicorn

    if reload:
        # Use string reference for reload mode (uvicorn requirement)
        uvicorn.run(
            "api.main:app",
            host=host,
            port=port,
            reload=True,
            reload_dirs=["api/src", "shared/src", "agent/src"],
        )
    else:
        uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
