"""
Report API business logic.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.schemas.report import ReportResponse
from app.services.assessment_service import get_assessment


async def get_report_status(
    db: AsyncSession,
    *,
    current_user: User,
    assessment_id: UUID,
) -> ReportResponse:
    assessment = await get_assessment(db, current_user=current_user, assessment_id=assessment_id)
    return ReportResponse(
        assessment_id=assessment.id,
        status=assessment.status,
        report_path=assessment.report_path,
        download_ready=assessment.report_path is not None,
    )
