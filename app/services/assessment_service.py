"""
Assessment orchestration-ready business logic.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException, TenantAccessException
from app.core.pagination import PaginationParams
from app.db.models.assessment import Assessment
from app.db.models.assessment_event import AssessmentEvent
from app.db.models.assessment_finding import AssessmentFinding
from app.db.models.assessment_job import AssessmentJob
from app.db.models.assessment_recommendation import AssessmentRecommendation
from app.db.models.user import User
from app.db.repositories.base_repository import TenantScopedRepository
from app.schemas.assessment import AssessmentStartRequest
from app.schemas.assessment_schema import AssessmentSummaryResponse
from app.services.audit_service import AuditEvent, audit_service
from app.services.runtime_recommendation_service import calculate_priority_score
from app.tasks.assessment_tasks import run_assessment_task

assessment_repository = TenantScopedRepository(Assessment)


def get_assessment_summary() -> AssessmentSummaryResponse:
    return AssessmentSummaryResponse(
        message="Assessment module ready for Phase 6 workflow implementation",
        module="assessment",
    )


def _assert_user_tenant(current_user: User, tenant_id: str) -> None:
    if current_user.microsoft_tid != tenant_id:
        raise TenantAccessException("Tenant is not available to the current user")


async def start_assessment(
    db: AsyncSession,
    *,
    current_user: User,
    payload: AssessmentStartRequest,
) -> Assessment:
    _assert_user_tenant(current_user, payload.tenant_id)
    assessment = await assessment_repository.create_for_tenant(
        db,
        tenant_id=payload.tenant_id,
        obj_in={
            "triggered_by_user_id": current_user.id,
            "status": "queued",
            "progress_pct": 0.0,
        },
    )
    job = AssessmentJob(
        assessment_id=assessment.id,
        tenant_id=payload.tenant_id,
        status="queued",
        current_stage="queued",
        progress_pct=0.0,
        metadata_payload={"runtime": "phase7a_simulated", "enqueue_status": "pending"},
    )
    db.add(job)
    await db.flush()
    await audit_service.log_event(
        db,
        tenant_id=payload.tenant_id,
        event=AuditEvent.ASSESSMENT_STARTED,
        action="assessment.started",
        user_id=current_user.id,
        resource="assessments",
        metadata={"assessment_id": str(assessment.id), "job_id": str(job.id)},
        commit=True,
    )
    try:
        queued_task = run_assessment_task.apply_async(args=[str(job.id)], retry=False)
        job.metadata_payload = {
            **(job.metadata_payload or {}),
            "enqueue_status": "queued",
            "celery_task_id": queued_task.id,
        }
    except Exception as exc:
        job.metadata_payload = {
            **(job.metadata_payload or {}),
            "enqueue_status": "failed",
            "enqueue_error": str(exc),
        }
    await db.commit()
    await db.refresh(assessment)
    await db.refresh(job)
    assessment.job_id = job.id
    return assessment


async def get_assessment(
    db: AsyncSession,
    *,
    current_user: User,
    assessment_id: UUID,
) -> Assessment:
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalars().first()
    if assessment is None:
        raise NotFoundException("Assessment not found")
    _assert_user_tenant(current_user, assessment.tenant_id)
    return assessment


async def list_tenant_assessments(
    db: AsyncSession,
    *,
    current_user: User,
    tenant_id: str,
    pagination: PaginationParams,
) -> list[Assessment]:
    _assert_user_tenant(current_user, tenant_id)
    return await assessment_repository.get_all_for_tenant(
        db,
        tenant_id=tenant_id,
        skip=pagination.resolved_offset,
        limit=pagination.limit,
    )


async def get_findings(
    db: AsyncSession,
    *,
    current_user: User,
    assessment_id: UUID,
    pagination: PaginationParams,
) -> list[AssessmentFinding]:
    assessment = await get_assessment(db, current_user=current_user, assessment_id=assessment_id)
    result = await db.execute(
        select(AssessmentFinding)
        .options(selectinload(AssessmentFinding.parameter))
        .where(AssessmentFinding.assessment_id == assessment.id)
        .offset(pagination.resolved_offset)
        .limit(pagination.limit)
    )
    return list(result.scalars().all())


async def get_events(
    db: AsyncSession,
    *,
    current_user: User,
    assessment_id: UUID,
    pagination: PaginationParams,
) -> list[AssessmentEvent]:
    assessment = await get_assessment(db, current_user=current_user, assessment_id=assessment_id)
    result = await db.execute(
        select(AssessmentEvent)
        .where(
            AssessmentEvent.assessment_id == assessment.id,
            AssessmentEvent.tenant_id == assessment.tenant_id,
        )
        .order_by(AssessmentEvent.created_at.desc())
        .offset(pagination.resolved_offset)
        .limit(pagination.limit)
    )
    return list(result.scalars().all())


async def get_job(
    db: AsyncSession,
    *,
    current_user: User,
    assessment_id: UUID,
) -> AssessmentJob:
    assessment = await get_assessment(db, current_user=current_user, assessment_id=assessment_id)
    result = await db.execute(
        select(AssessmentJob)
        .where(
            AssessmentJob.assessment_id == assessment.id,
            AssessmentJob.tenant_id == assessment.tenant_id,
        )
        .order_by(AssessmentJob.created_at.desc())
        .limit(1)
    )
    job = result.scalars().first()
    if job is None:
        raise NotFoundException("Assessment job not found")
    return job


async def get_score(
    db: AsyncSession,
    *,
    current_user: User,
    assessment_id: UUID,
) -> dict:
    assessment = await get_assessment(db, current_user=current_user, assessment_id=assessment_id)
    return {
        "assessment_id": assessment.id,
        "overall_score": assessment.overall_score,
        "categories": {
            "identity": assessment.identity_score,
            "security": assessment.security_score,
            "compliance": assessment.compliance_score,
            "collaboration": assessment.collaboration_score,
            "licensing": assessment.licensing_score,
        },
        "status": assessment.status,
    }


async def get_recommendations(
    db: AsyncSession,
    *,
    current_user: User,
    assessment_id: UUID,
) -> dict:
    assessment = await get_assessment(db, current_user=current_user, assessment_id=assessment_id)
    result = await db.execute(
        select(AssessmentRecommendation)
        .where(
            AssessmentRecommendation.assessment_id == assessment.id,
            AssessmentRecommendation.tenant_id == assessment.tenant_id,
        )
        .order_by(AssessmentRecommendation.created_at.desc())
    )
    recommendations = result.scalars().all()
    return {
        "assessment_id": assessment.id,
        "recommendations": [
            {
                "id": item.id,
                "assessment_id": item.assessment_id,
                "parameter_key": item.parameter_key,
                "severity": item.severity,
                "title": item.title,
                "recommendation_text": item.recommendation_text,
                "remediation_steps": item.remediation_steps,
                "effort": item.effort,
                "impact": item.impact,
                "priority_score": calculate_priority_score(
                    severity=item.severity,
                    effort=item.effort,
                    copilot_impact=item.impact,
                ),
                "created_at": item.created_at,
            }
            for item in recommendations
        ],
    }
