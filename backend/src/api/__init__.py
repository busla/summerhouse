"""FastAPI application for Quesada Apartment Booking backend."""

from fastapi import FastAPI

app = FastAPI(
    title="Quesada Apartment Booking API",
    description="Agent-First Vacation Rental Booking Platform",
    version="0.1.0",
)

# Import and include routers (must be after app creation)
from src.api.health import router as health_router  # noqa: E402
from src.api.auth import router as auth_router  # noqa: E402

app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
