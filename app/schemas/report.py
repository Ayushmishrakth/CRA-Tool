"""
Report API schemas.
"""

from uuid import UUID

from pydantic import BaseModel


class ReportResponse(BaseModel):
    assessment_id: UUID
    status: str
    report_path: str | None
    download_ready: bool
