"""
CRA Assessment business logic (Phase 2 placeholder).

Copilot Readiness Assessment workflows will be implemented here.
"""

from app.schemas.assessment_schema import AssessmentSummaryResponse


def get_assessment_summary() -> AssessmentSummaryResponse:
    """Return assessment module status (stub until CRA logic is added)."""
    return AssessmentSummaryResponse(
        message="Assessment module ready (Phase 2 stub)",
        module="assessment",
    )
