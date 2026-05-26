"""
Pydantic schemas for Dashboard API (Phase 2 stubs).
"""

from pydantic import BaseModel, Field


class DashboardSummaryResponse(BaseModel):
    """Dashboard overview payload (placeholder for Phase 3+)."""

    message: str = Field(..., description="Placeholder dashboard summary")
    module: str = Field(default="dashboard", description="CRA module identifier")
