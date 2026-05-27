"""
Admin API business logic.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.core.pagination import PaginationParams
from app.db.models.assessment_parameter import AssessmentParameter
from app.db.models.assessment_rule import AssessmentRule
from app.schemas.admin import RuleUpdateRequest


async def list_parameters(
    db: AsyncSession,
    *,
    pagination: PaginationParams,
) -> list[AssessmentParameter]:
    result = await db.execute(
        select(AssessmentParameter)
        .offset(pagination.resolved_offset)
        .limit(pagination.limit)
    )
    return list(result.scalars().all())


async def upsert_parameter_rule(
    db: AsyncSession,
    *,
    parameter_id: UUID,
    payload: RuleUpdateRequest,
) -> AssessmentRule:
    parameter = await db.get(AssessmentParameter, parameter_id)
    if parameter is None:
        raise NotFoundException("Assessment parameter not found")

    result = await db.execute(
        select(AssessmentRule).where(AssessmentRule.parameter_id == parameter_id)
    )
    rule = result.scalars().first()
    if rule is None:
        rule = AssessmentRule(parameter_id=parameter_id, **payload.model_dump())
        db.add(rule)
    else:
        for key, value in payload.model_dump().items():
            setattr(rule, key, value)
    await db.commit()
    await db.refresh(rule)
    return rule
