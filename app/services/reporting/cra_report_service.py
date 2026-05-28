from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.assessment_finding import AssessmentFinding
from app.db.models.assessment_artifact import AssessmentArtifact
from app.db.models.assessment_recommendation import AssessmentRecommendation
from app.db.models.assessment_report import AssessmentReport
from app.db.models.user import User
from app.services.assessment_service import get_assessment
from app.services.reporting.cra_chart_service import build_chart_data
from app.services.reporting.cra_docx_renderer import render_docx
from app.services.reporting.cra_narrative_service import build_narrative
from app.services.reporting.cra_pdf_renderer import render_pdf
from app.services.reporting.cra_risk_engine import aggregate_findings
from app.services.reporting.cra_summary_service import build_summary


REPORT_ROOT = Path("storage/reports")
SERVICE_ORDER = [
    "Entra ID",
    "Exchange Online",
    "Microsoft Purview",
    "Teams",
    "OneDrive",
    "SharePoint",
    "Licensing",
    "Microsoft 365",
]


async def generate_report_bundle(
    db: AsyncSession,
    *,
    current_user: User,
    assessment_id: UUID,
) -> dict[str, Any]:
    report_data = await build_report_data(db, current_user=current_user, assessment_id=assessment_id)
    assessment = report_data["assessment"]
    target_dir = REPORT_ROOT / str(assessment.id)
    pdf_path = render_pdf(target_dir / "copilot-readiness-assessment.pdf", report_data)
    docx_path = render_docx(target_dir / "copilot-readiness-assessment.docx", report_data)

    await db.execute(delete(AssessmentReport).where(AssessmentReport.assessment_id == assessment.id))
    artifacts = [
        AssessmentReport(
            assessment_id=assessment.id,
            report_type="pdf",
            report_status="generated",
            storage_path=str(pdf_path),
            generated_by=current_user.id,
            metadata_json=report_data["metadata"],
        ),
        AssessmentReport(
            assessment_id=assessment.id,
            report_type="docx",
            report_status="generated",
            storage_path=str(docx_path),
            generated_by=current_user.id,
            metadata_json=report_data["metadata"],
        ),
    ]
    db.add_all(artifacts)
    assessment.report_path = str(pdf_path)
    await db.commit()
    for artifact in artifacts:
        await db.refresh(artifact)

    return {
        "assessment_id": assessment.id,
        "status": "generated",
        "artifacts": [_artifact_payload(item) for item in artifacts],
        "summary": report_data["summary"],
        "analytics": report_data["analytics"],
    }


async def get_report_bundle(
    db: AsyncSession,
    *,
    current_user: User,
    assessment_id: UUID,
) -> dict[str, Any]:
    report_data = await build_report_data(db, current_user=current_user, assessment_id=assessment_id)
    result = await db.execute(
        select(AssessmentReport)
        .where(AssessmentReport.assessment_id == assessment_id)
        .order_by(AssessmentReport.generated_at.desc())
    )
    artifacts = list(result.scalars().all())
    return {
        "assessment_id": assessment_id,
        "status": "generated" if artifacts else "not_generated",
        "download_ready": bool(artifacts),
        "artifacts": [_artifact_payload(item) for item in artifacts],
        "summary": report_data["summary"],
        "analytics": report_data["analytics"],
    }


async def get_report_artifact(
    db: AsyncSession,
    *,
    current_user: User,
    assessment_id: UUID,
    report_type: str = "pdf",
) -> AssessmentReport:
    await get_assessment(db, current_user=current_user, assessment_id=assessment_id)
    result = await db.execute(
        select(AssessmentReport)
        .where(
            AssessmentReport.assessment_id == assessment_id,
            AssessmentReport.report_type == report_type,
        )
        .order_by(AssessmentReport.generated_at.desc())
        .limit(1)
    )
    artifact = result.scalars().first()
    if artifact is None:
        raise FileNotFoundError("Report artifact has not been generated")
    return artifact


async def build_report_data(
    db: AsyncSession,
    *,
    current_user: User,
    assessment_id: UUID,
) -> dict[str, Any]:
    assessment = await get_assessment(db, current_user=current_user, assessment_id=assessment_id)
    findings = await _load_findings(db, assessment.id)
    recommendations = await _load_recommendations(db, assessment.id, assessment.tenant_id)
    artifacts = await _load_artifacts(db, assessment.id, assessment.tenant_id)
    analytics_raw = aggregate_findings(findings)
    summary = build_summary(assessment=assessment, findings=findings, recommendations=recommendations)
    narrative = build_narrative(summary=summary, analytics=analytics_raw)
    analytics = build_chart_data(summary=summary, analytics=analytics_raw)
    sections = _build_sections(findings, recommendations, artifacts)
    return {
        "assessment": assessment,
        "summary": summary,
        "analytics": analytics,
        "narrative": narrative,
        "sections": sections,
        "metadata": {
            "finding_count": len(findings),
            "recommendation_count": len(recommendations),
            "failed_collector_count": len([item for item in artifacts if item.status != "collected"]),
            "evidence_policy": "missing or failed collectors are reported as NOT COLLECTED",
        },
    }


async def _load_findings(db: AsyncSession, assessment_id: UUID) -> list[AssessmentFinding]:
    result = await db.execute(
        select(AssessmentFinding)
        .options(selectinload(AssessmentFinding.parameter))
        .where(AssessmentFinding.assessment_id == assessment_id)
    )
    return list(result.scalars().all())


async def _load_recommendations(
    db: AsyncSession,
    assessment_id: UUID,
    tenant_id: str,
) -> list[AssessmentRecommendation]:
    result = await db.execute(
        select(AssessmentRecommendation).where(
            AssessmentRecommendation.assessment_id == assessment_id,
            AssessmentRecommendation.tenant_id == tenant_id,
        )
    )
    return list(result.scalars().all())


async def _load_artifacts(
    db: AsyncSession,
    assessment_id: UUID,
    tenant_id: str,
) -> list[AssessmentArtifact]:
    result = await db.execute(
        select(AssessmentArtifact).where(
            AssessmentArtifact.assessment_id == assessment_id,
            AssessmentArtifact.tenant_id == tenant_id,
        )
    )
    return list(result.scalars().all())


def _build_sections(
    findings: list[AssessmentFinding],
    recommendations: list[AssessmentRecommendation],
    artifacts: list[AssessmentArtifact],
) -> dict[str, list[dict[str, Any]]]:
    rec_by_key = {item.parameter_key: item for item in recommendations}
    sections = {service: [] for service in SERVICE_ORDER}
    for finding in findings:
        parameter = finding.parameter
        raw = finding.raw_value or {}
        parameter_key = raw.get("parameter_key") or getattr(parameter, "parameter_key", None) or ""
        service = _service_for_key(parameter_key, getattr(parameter, "category", None))
        recommendation = rec_by_key.get(parameter_key)
        item = {
            "title": getattr(parameter, "parameter_name", None) or parameter_key,
            "service": service,
            "pillar": getattr(parameter, "category", None) or "Best Practice",
            "severity": (finding.severity or "info").lower(),
            "finding": finding.evaluated_value or finding.status,
            "description": getattr(parameter, "copilot_relevance", None) or "Assessment control evaluated for Copilot readiness.",
            "risk": _risk_text(finding),
            "recommendation": recommendation.recommendation_text if recommendation else "Review and remediate this control.",
            "evidence": raw,
            "documentation_link": "",
        }
        sections.setdefault(service, []).append(item)
    collected_keys = {
        (finding.raw_value or {}).get("parameter_key") or getattr(finding.parameter, "parameter_key", None)
        for finding in findings
    }
    for artifact in artifacts:
        if artifact.status == "collected" or artifact.parameter_key in collected_keys:
            continue
        service = _service_for_key(artifact.parameter_key, artifact.service)
        sections.setdefault(service, []).append(
            {
                "title": artifact.parameter_key,
                "service": service,
                "pillar": artifact.service or "Unknown",
                "severity": "info",
                "finding": "NOT COLLECTED",
                "description": "Collector did not produce trusted evidence.",
                "risk": "No readiness conclusion was generated for this control because evidence was unavailable.",
                "recommendation": "Resolve collector configuration and re-run the assessment.",
                "evidence": {
                    "status": artifact.status,
                    "error": artifact.stderr,
                    "source_script": artifact.source_script,
                    "source_csv": artifact.source_csv,
                },
                "documentation_link": "",
            }
        )
    return {service: sections.get(service, []) for service in SERVICE_ORDER if sections.get(service)}


def _service_for_key(parameter_key: str, category: str | None) -> str:
    text = f"{parameter_key} {category or ''}".lower()
    if any(token in text for token in ["entra", "mfa", "identity", "admin", "guest_users"]):
        return "Entra ID"
    if any(token in text for token in ["exchange", "mailbox", "email", "calendar"]):
        return "Exchange Online"
    if any(token in text for token in ["purview", "audit", "dlp", "secure_score", "sensitivity"]):
        return "Microsoft Purview"
    if "teams" in text or "meeting" in text:
        return "Teams"
    if "onedrive" in text:
        return "OneDrive"
    if "sharepoint" in text or "site" in text or "sharing" in text:
        return "SharePoint"
    if "license" in text:
        return "Licensing"
    return "Microsoft 365"


def _risk_text(finding: AssessmentFinding) -> str:
    severity = (finding.severity or "info").lower()
    if finding.status == "pass":
        return "No immediate risk was identified for this control."
    if severity in {"critical", "high"}:
        return "This finding can materially increase Copilot deployment, data exposure, or governance risk."
    return "This finding should be reviewed as part of readiness improvement planning."


def _artifact_payload(item: AssessmentReport) -> dict[str, Any]:
    return {
        "id": item.id,
        "assessment_id": item.assessment_id,
        "report_type": item.report_type,
        "report_status": item.report_status,
        "storage_path": item.storage_path,
        "generated_at": item.generated_at.isoformat(),
        "generated_by": item.generated_by,
        "metadata": item.metadata_json,
    }
