"""
Health check business logic.

Routes stay thin: they call service functions and return validated schemas.
"""

from app.schemas.health_schema import HealthResponse


def get_health_status() -> HealthResponse:
    """Build the health check response (extend with DB checks in Phase 3+)."""
    return HealthResponse(status="Server Running Successfully")
