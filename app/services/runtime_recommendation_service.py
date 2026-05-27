"""
Runtime recommendation generation from registry metadata and findings.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.assessment_finding import AssessmentFinding
from app.db.models.assessment_recommendation import AssessmentRecommendation
from app.services.registry_service import get_registry


SEVERITY_PRIORITY = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}
EFFORT_INVERSE = {"low": 1.0, "medium": 0.72, "high": 0.45}


def _effort_for(severity: str) -> str:
    if severity in {"critical", "high"}:
        return "medium"
    return "low"


def calculate_priority_score(
    *,
    severity: str,
    effort: str | None = None,
    copilot_impact: str | None = None,
    registry_priority: int | float | None = None,
) -> int:
    severity_score = SEVERITY_PRIORITY.get((severity or "info").lower(), 1)
    effort_multiplier = EFFORT_INVERSE.get((effort or "medium").lower(), 0.72)
    copilot_multiplier = 1.25 if copilot_impact else 1.0
    base = registry_priority or severity_score
    return min(100, max(1, round(float(base) * severity_score * effort_multiplier * copilot_multiplier * 4)))


async def generate_recommendations(
    db: AsyncSession,
    *,
    assessment_id,
    tenant_id: str,
    findings: list[AssessmentFinding],
) -> list[AssessmentRecommendation]:
    registry = get_registry()
    await db.execute(
        delete(AssessmentRecommendation).where(
            AssessmentRecommendation.assessment_id == assessment_id,
            AssessmentRecommendation.tenant_id == tenant_id,
        )
    )
    created: list[AssessmentRecommendation] = []
    now = datetime.now(timezone.utc)
    for finding in findings:
        if finding.status == "pass":
            continue
        parameter_key = (finding.raw_value or {}).get("parameter_key")
        if not parameter_key:
            continue
        template = registry.get_recommendation_by_key(parameter_key) or {}
        severity = (finding.severity or template.get("severity") or "info").lower()
        title = template.get("title") or f"Remediate {parameter_key}"
        copilot_impact = template.get("copilot_impact")
        impact = template.get("impact") or copilot_impact or finding.evaluated_value
        steps = template.get("remediation_steps") or ["Review and remediate this CRA control."]
        effort = _effort_for(severity)
        priority = calculate_priority_score(
            severity=severity,
            effort=effort,
            copilot_impact=copilot_impact,
            registry_priority=template.get("priority"),
        )
        recommendation = AssessmentRecommendation(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            parameter_key=parameter_key,
            severity=severity,
            title=title,
            recommendation_text=f"{title}. Priority {priority}.",
            remediation_steps=steps,
            effort=effort,
            impact=impact,
            created_at=now,
        )
        db.add(recommendation)
        created.append(recommendation)
    await db.flush()
    return created
