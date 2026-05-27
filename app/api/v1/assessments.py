"""
Assessment API routes.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_active_user
from app.core.pagination import PaginationParams, get_pagination_params
from app.core.responses import SuccessResponse, success_response
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.assessment import (
    AssessmentEventResponse,
    AssessmentFindingResponse,
    AssessmentJobResponse,
    AssessmentRecommendationResponse,
    AssessmentResponse,
    AssessmentScoreResponse,
    AssessmentStartRequest,
)
from app.services import assessment_service

router = APIRouter(tags=["Assessments"])


@router.post(
    "/assessments/start",
    response_model=SuccessResponse[AssessmentResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_assessment(
    payload: AssessmentStartRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AssessmentResponse]:
    assessment = await assessment_service.start_assessment(
        db, current_user=current_user, payload=payload
    )
    return success_response(
        message="Assessment queued",
        data=AssessmentResponse.model_validate(assessment),
        request_id=request.state.request_id,
    )


@router.get(
    "/assessments/{assessment_id}",
    response_model=SuccessResponse[AssessmentResponse],
)
async def get_assessment(
    assessment_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AssessmentResponse]:
    assessment = await assessment_service.get_assessment(
        db, current_user=current_user, assessment_id=assessment_id
    )
    return success_response(
        message="Assessment retrieved",
        data=AssessmentResponse.model_validate(assessment),
        request_id=request.state.request_id,
    )


@router.get(
    "/assessments/{assessment_id}/findings",
    response_model=SuccessResponse[list[AssessmentFindingResponse]],
)
async def get_assessment_findings(
    assessment_id: UUID,
    request: Request,
    pagination: PaginationParams = Depends(get_pagination_params),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[AssessmentFindingResponse]]:
    findings = await assessment_service.get_findings(
        db, current_user=current_user, assessment_id=assessment_id, pagination=pagination
    )
    return success_response(
        message="Assessment findings retrieved",
        data=[AssessmentFindingResponse.model_validate(finding) for finding in findings],
        request_id=request.state.request_id,
    )


@router.get(
    "/assessments/{assessment_id}/events",
    response_model=SuccessResponse[list[AssessmentEventResponse]],
)
async def get_assessment_events(
    assessment_id: UUID,
    request: Request,
    pagination: PaginationParams = Depends(get_pagination_params),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[AssessmentEventResponse]]:
    events = await assessment_service.get_events(
        db, current_user=current_user, assessment_id=assessment_id, pagination=pagination
    )
    return success_response(
        message="Assessment events retrieved",
        data=[AssessmentEventResponse.model_validate(event) for event in events],
        request_id=request.state.request_id,
    )


@router.get(
    "/assessments/{assessment_id}/job",
    response_model=SuccessResponse[AssessmentJobResponse],
)
async def get_assessment_job(
    assessment_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AssessmentJobResponse]:
    job = await assessment_service.get_job(
        db, current_user=current_user, assessment_id=assessment_id
    )
    return success_response(
        message="Assessment job retrieved",
        data=AssessmentJobResponse.model_validate(
            {
                "id": job.id,
                "assessment_id": job.assessment_id,
                "tenant_id": job.tenant_id,
                "status": job.status,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
                "current_stage": job.current_stage,
                "progress_pct": job.progress_pct,
                "worker_id": job.worker_id,
                "error_message": job.error_message,
                "metadata": job.metadata_payload,
                "created_at": job.created_at,
            }
        ),
        request_id=request.state.request_id,
    )


@router.get(
    "/assessments/{assessment_id}/recommendations",
    response_model=SuccessResponse[AssessmentRecommendationResponse],
)
async def get_assessment_recommendations(
    assessment_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AssessmentRecommendationResponse]:
    payload = await assessment_service.get_recommendations(
        db, current_user=current_user, assessment_id=assessment_id
    )
    return success_response(
        message="Assessment recommendations retrieved",
        data=AssessmentRecommendationResponse.model_validate(payload),
        request_id=request.state.request_id,
    )


@router.get(
    "/assessments/{assessment_id}/score",
    response_model=SuccessResponse[AssessmentScoreResponse],
)
async def get_assessment_score(
    assessment_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[AssessmentScoreResponse]:
    payload = await assessment_service.get_score(
        db, current_user=current_user, assessment_id=assessment_id
    )
    return success_response(
        message="Assessment score retrieved",
        data=AssessmentScoreResponse.model_validate(payload),
        request_id=request.state.request_id,
    )


@router.get(
    "/tenants/{tenant_id}/assessments",
    response_model=SuccessResponse[list[AssessmentResponse]],
)
async def list_tenant_assessments(
    tenant_id: str,
    request: Request,
    pagination: PaginationParams = Depends(get_pagination_params),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[AssessmentResponse]]:
    assessments = await assessment_service.list_tenant_assessments(
        db, current_user=current_user, tenant_id=tenant_id, pagination=pagination
    )
    return success_response(
        message="Tenant assessments retrieved",
        data=[AssessmentResponse.model_validate(item) for item in assessments],
        request_id=request.state.request_id,
    )
