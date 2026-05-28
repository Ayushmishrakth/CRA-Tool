"""
Phase 7 assessment runtime orchestration.

Phase 7B keeps the lifecycle intact and swaps collector execution to the
PowerShell runtime. Microsoft Graph collectors plug into this lifecycle later.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.assessment import Assessment
from app.db.models.assessment_artifact import AssessmentArtifact
from app.db.models.assessment_finding import AssessmentFinding
from app.db.models.assessment_job import AssessmentJob
from app.db.models.assessment_parameter import AssessmentParameter
from app.db.models.assessment_rule import AssessmentRule
from app.db.session import AsyncSessionLocal
from app.services.audit_service import AuditEvent, audit_service
from app.services.event_bus import emit_event
from app.services.powershell import PowerShellExecutionEngine
from app.services.registry_service import get_registry
from app.services.runtime_recommendation_service import calculate_priority_score, generate_recommendations
from app.services.runtime_scoring_service import apply_scores


RUNTIME_STAGES = {
    "starting": ("starting", 3.0),
    "collecting": ("collecting", 8.0),
    "evaluating": ("evaluating", 82.0),
    "scoring": ("scoring", 90.0),
    "recommendations": ("generating_recommendations", 95.0),
    "completed": ("completed", 100.0),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _short_ref(parameter: dict[str, Any]) -> str | None:
    source_refs = parameter.get("source_refs") or []
    if not source_refs:
        return None
    source = source_refs[0]
    sheet = str(source.get("sheet") or "")[:18]
    row = source.get("row") or ""
    return f"{sheet}:{row}"[:50]


def _pass_threshold(rule: dict[str, Any]) -> str | None:
    expression = rule.get("expression") or {}
    thresholds = expression.get("percentage_thresholds") or expression.get("count_thresholds")
    if thresholds:
        return ",".join(str(item) for item in thresholds)[:255]
    criteria = expression.get("pass_criteria")
    return str(criteria)[:255] if criteria else None


async def ensure_registry_seeded(
    db: AsyncSession,
) -> tuple[dict[str, AssessmentParameter], dict[str, AssessmentRule]]:
    """Materialize runtime registry rows required by persisted findings."""

    registry = get_registry()
    parameters = registry.get_parameters()
    parameter_keys = [item["parameter_key"] for item in parameters]

    existing_parameters = (
        await db.execute(
            select(AssessmentParameter).where(
                AssessmentParameter.parameter_key.in_(parameter_keys)
            )
        )
    ).scalars().all()
    parameter_by_key = {item.parameter_key: item for item in existing_parameters}

    for parameter in parameters:
        key = parameter["parameter_key"]
        if key in parameter_by_key:
            continue
        collector = registry.get_collector_by_key(key) or {}
        db_parameter = AssessmentParameter(
            parameter_key=key,
            parameter_name=parameter.get("display_name") or key,
            category=parameter.get("category") or parameter.get("domain") or "unclassified",
            collection_method=parameter.get("collection_method") or "unknown",
            collector_module=collector.get("collector_name")
            or f"powershell.{parameter.get('collector_type') or 'unknown'}",
            graph_endpoint=parameter.get("graph_endpoint") or None,
            copilot_relevance=parameter.get("copilot_relevance") or None,
            is_active=True,
            excel_row_reference=_short_ref(parameter),
        )
        db.add(db_parameter)
        parameter_by_key[key] = db_parameter

    await db.flush()

    parameter_ids = [item.id for item in parameter_by_key.values()]
    existing_rules = (
        await db.execute(
            select(AssessmentRule).where(AssessmentRule.parameter_id.in_(parameter_ids))
        )
    ).scalars().all()
    rule_by_parameter_id = {item.parameter_id: item for item in existing_rules}
    rule_by_key: dict[str, AssessmentRule] = {}

    for parameter in parameters:
        key = parameter["parameter_key"]
        db_parameter = parameter_by_key[key]
        existing_rule = rule_by_parameter_id.get(db_parameter.id)
        if existing_rule is not None:
            rule_by_key[key] = existing_rule
            continue

        registry_rule = registry.get_rule_by_key(key) or {}
        expression = registry_rule.get("expression") or {}
        db_rule = AssessmentRule(
            parameter_id=db_parameter.id,
            rule_type=registry_rule.get("rule_type") or "configuration_value_check",
            pass_threshold=_pass_threshold(registry_rule),
            warning_threshold=str(expression.get("warning_threshold") or "")[:255] or None,
            pass_condition=expression,
            severity=registry_rule.get("severity") or parameter.get("severity") or "info",
            scoring_weight=float(registry_rule.get("scoring_weight") or 1.0),
            copilot_blocking=bool(
                registry_rule.get("copilot_blocking")
                if "copilot_blocking" in registry_rule
                else parameter.get("copilot_blocker")
            ),
        )
        db.add(db_rule)
        rule_by_key[key] = db_rule

    await db.flush()
    return parameter_by_key, rule_by_key


async def _load_job(db: AsyncSession, job_id: str | UUID) -> AssessmentJob:
    result = await db.execute(select(AssessmentJob).where(AssessmentJob.id == UUID(str(job_id))))
    job = result.scalars().first()
    if job is None:
        raise RuntimeError(f"Assessment job not found: {job_id}")
    return job


async def _load_assessment(db: AsyncSession, assessment_id: UUID) -> Assessment:
    assessment = await db.get(Assessment, assessment_id)
    if assessment is None:
        raise RuntimeError(f"Assessment not found: {assessment_id}")
    return assessment


async def _set_stage(
    db: AsyncSession,
    *,
    assessment: Assessment,
    job: AssessmentJob,
    status: str,
    stage: str,
    progress: float,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    assessment.status = status
    assessment.progress_pct = progress
    job.status = status
    job.current_stage = stage
    job.progress_pct = progress
    if status == "running" and job.started_at is None:
        job.started_at = _utc_now()
    await emit_event(
        db,
        assessment_id=assessment.id,
        tenant_id=assessment.tenant_id,
        event_type=event_type,
        payload={"stage": stage, "progress_pct": progress, **(payload or {})},
    )
    await db.commit()


async def _persist_finding(
    db: AsyncSession,
    *,
    assessment: Assessment,
    parameter: AssessmentParameter,
    rule: AssessmentRule | None,
    collector_result: dict[str, Any],
) -> AssessmentFinding:
    now = _utc_now()
    finding = AssessmentFinding(
        assessment_id=assessment.id,
        parameter_id=parameter.id,
        rule_id=rule.id if rule else None,
        status=collector_result["status"],
        raw_value=collector_result["raw_value"],
        evaluated_value=collector_result["evaluated_value"],
        severity=collector_result["severity"],
        score_contribution=collector_result["score_contribution"],
        collected_at=now,
        evaluated_at=now,
    )
    db.add(finding)
    await db.flush()
    return finding


async def _persist_artifact(
    db: AsyncSession,
    *,
    assessment: Assessment,
    job: AssessmentJob,
    parameter_key: str,
    collector: dict[str, Any],
    collector_result: dict[str, Any] | None = None,
    status: str,
    artifact_type: str = "collector_execution",
    error: str | None = None,
) -> AssessmentArtifact:
    telemetry = (collector_result or {}).get("telemetry") or {}
    raw_value = (collector_result or {}).get("raw_value") or {}
    contract = raw_value.get("collector_contract") if isinstance(raw_value, dict) else None
    artifact = AssessmentArtifact(
        assessment_id=assessment.id,
        job_id=job.id,
        tenant_id=assessment.tenant_id,
        parameter_key=parameter_key,
        service=collector.get("service") or collector.get("collector_type"),
        artifact_type=artifact_type,
        source_script=telemetry.get("source_script"),
        source_csv=(
            (telemetry.get("generated_files") or [None])[0]
            if isinstance(telemetry.get("generated_files"), list)
            else collector.get("output_file") or None
        ),
        status=status,
        stdout=telemetry.get("stdout") or telemetry.get("stdout_preview"),
        stderr=telemetry.get("stderr") or error,
        payload={
            "collector": collector,
            "result": collector_result,
            "contract": contract,
            "error": error,
        },
    )
    db.add(artifact)
    await db.flush()
    return artifact


def _finding_payload(
    finding: AssessmentFinding,
    parameter: AssessmentParameter,
    collector_result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": str(finding.id),
        "assessment_id": str(finding.assessment_id),
        "parameter_id": str(finding.parameter_id),
        "parameter_key": collector_result["parameter_key"],
        "parameter_name": parameter.parameter_name,
        "category": parameter.category,
        "status": finding.status,
        "raw_value": finding.raw_value,
        "evaluated_value": finding.evaluated_value,
        "severity": finding.severity,
        "score_contribution": finding.score_contribution,
        "collected_at": finding.collected_at.isoformat() if finding.collected_at else None,
        "evaluated_at": finding.evaluated_at.isoformat() if finding.evaluated_at else None,
    }


async def _collect_findings(
    db: AsyncSession,
    *,
    assessment: Assessment,
    job: AssessmentJob,
) -> list[AssessmentFinding]:
    registry = get_registry()
    powershell_engine = PowerShellExecutionEngine()
    parameter_by_key, rule_by_key = await ensure_registry_seeded(db)
    await db.execute(delete(AssessmentFinding).where(AssessmentFinding.assessment_id == assessment.id))
    await db.execute(delete(AssessmentArtifact).where(AssessmentArtifact.assessment_id == assessment.id))
    await db.commit()

    parameters = registry.get_parameters()
    findings: list[AssessmentFinding] = []
    telemetry_summary = {
        "collector_runtime": "powershell",
        "collector_failures": 0,
        "collector_timeouts": 0,
        "collector_retries": 0,
        "collector_duration_ms": 0,
    }
    total = max(1, len(parameters))

    for index, parameter_config in enumerate(parameters, start=1):
        key = parameter_config["parameter_key"]
        collector = registry.get_collector_by_key(key) or {}
        progress = round(8.0 + (index - 1) / total * 74.0, 2)
        assessment.progress_pct = progress
        job.progress_pct = progress
        job.current_stage = "collecting"

        await emit_event(
            db,
            assessment_id=assessment.id,
            tenant_id=assessment.tenant_id,
            event_type="collector.started",
            payload={
                "parameter_key": key,
                "collector": collector.get("collector_name"),
                "collector_type": collector.get("collector_type"),
                "runtime": "powershell",
                "progress_pct": progress,
            },
        )
        await db.commit()

        try:
            collector_result = await powershell_engine.run_collector(
                tenant_id=assessment.tenant_id,
                parameter=parameter_config,
                collector=collector,
                assessment_id=str(assessment.id),
            )
            telemetry = collector_result.get("telemetry") or {}
            telemetry_summary["collector_retries"] += int(telemetry.get("retries") or 0)
            telemetry_summary["collector_duration_ms"] += int(telemetry.get("duration_ms") or 0)
            if telemetry.get("timed_out"):
                telemetry_summary["collector_timeouts"] += 1
                await emit_event(
                    db,
                    assessment_id=assessment.id,
                    tenant_id=assessment.tenant_id,
                    event_type="collector.timeout",
                    severity="warning",
                    payload={
                        "parameter_key": key,
                        "collector": collector.get("collector_name"),
                        "timeout_count": telemetry.get("timeout_count", 1),
                        "duration_ms": telemetry.get("duration_ms"),
                        "progress_pct": progress,
                    },
                )
            if telemetry.get("stdout_preview"):
                await emit_event(
                    db,
                    assessment_id=assessment.id,
                    tenant_id=assessment.tenant_id,
                    event_type="collector.stdout",
                    payload={
                        "parameter_key": key,
                        "collector": collector.get("collector_name"),
                        "stdout_preview": telemetry.get("stdout_preview"),
                        "duration_ms": telemetry.get("duration_ms"),
                        "attempts": telemetry.get("attempts"),
                        "progress_pct": progress,
                    },
                )
            for warning in collector_result.get("warnings") or []:
                await emit_event(
                    db,
                    assessment_id=assessment.id,
                    tenant_id=assessment.tenant_id,
                    event_type="collector.warning",
                    severity="warning",
                    payload={
                        "parameter_key": key,
                        "collector": collector.get("collector_name"),
                        "warning": str(warning),
                        "progress_pct": progress,
                    },
                )
            if collector_result.get("errors"):
                telemetry_summary["collector_failures"] += 1
                await _persist_artifact(
                    db,
                    assessment=assessment,
                    job=job,
                    parameter_key=key,
                    collector=collector,
                    collector_result=collector_result,
                    status="failed",
                )
                await emit_event(
                    db,
                    assessment_id=assessment.id,
                    tenant_id=assessment.tenant_id,
                    event_type="collector.failed",
                    severity="warning",
                    payload={
                        "parameter_key": key,
                        "collector": collector.get("collector_name"),
                        "errors": collector_result.get("errors"),
                        "stderr": telemetry.get("stderr"),
                        "exit_code": telemetry.get("exit_code"),
                        "attempts": telemetry.get("attempts"),
                        "retries": telemetry.get("retries"),
                        "duration_ms": telemetry.get("duration_ms"),
                        "progress_pct": progress,
                        "finding_generated": False,
                    },
                )
                await db.commit()
                continue
            if collector_result.get("status") == "not_collected":
                telemetry_summary["collector_failures"] += 1
                await _persist_artifact(
                    db,
                    assessment=assessment,
                    job=job,
                    parameter_key=key,
                    collector=collector,
                    collector_result=collector_result,
                    status="evidence_collected",
                )
                await emit_event(
                    db,
                    assessment_id=assessment.id,
                    tenant_id=assessment.tenant_id,
                    event_type="csv.detected",
                    payload={
                        "parameter_key": key,
                        "collector": collector.get("collector_name"),
                        "generated_files": (
                            collector_result.get("raw_value", {})
                            .get("collector_contract", {})
                            .get("metrics", {})
                            .get("generated_files", [])
                        ),
                        "finding_generated": False,
                        "progress_pct": progress,
                    },
                )
                await db.commit()
                continue
            await _persist_artifact(
                db,
                assessment=assessment,
                job=job,
                parameter_key=key,
                collector=collector,
                collector_result=collector_result,
                status="collected",
            )
            db_parameter = parameter_by_key[key]
            db_rule = rule_by_key.get(key)
            finding = await _persist_finding(
                db,
                assessment=assessment,
                parameter=db_parameter,
                rule=db_rule,
                collector_result=collector_result,
            )
            findings.append(finding)

            finding_payload = _finding_payload(finding, db_parameter, collector_result)
            progress = round(8.0 + index / total * 74.0, 2)
            assessment.progress_pct = progress
            job.progress_pct = progress
            await emit_event(
                db,
                assessment_id=assessment.id,
                tenant_id=assessment.tenant_id,
                event_type="finding.generated",
                severity=finding.severity or "info",
                payload={"finding": finding_payload, "progress_pct": progress},
            )
            await emit_event(
                db,
                assessment_id=assessment.id,
                tenant_id=assessment.tenant_id,
                event_type="collector.completed",
                payload={
                    "parameter_key": key,
                    "collector": collector.get("collector_name"),
                    "status": collector_result["status"],
                    "runtime": "powershell",
                    "duration_ms": telemetry.get("duration_ms"),
                    "attempts": telemetry.get("attempts"),
                    "retries": telemetry.get("retries"),
                    "exit_code": telemetry.get("exit_code"),
                    "progress_pct": progress,
                },
            )
            await emit_event(
                db,
                assessment_id=assessment.id,
                tenant_id=assessment.tenant_id,
                event_type="progress.update",
                payload={"progress_pct": progress, "stage": "collecting"},
            )
            await db.commit()
        except Exception as exc:
            telemetry_summary["collector_failures"] += 1
            await _persist_artifact(
                db,
                assessment=assessment,
                job=job,
                parameter_key=key,
                collector=collector,
                status="failed",
                error=str(exc),
            )
            await emit_event(
                db,
                assessment_id=assessment.id,
                tenant_id=assessment.tenant_id,
                event_type="collector.failed",
                severity="warning",
                payload={
                    "parameter_key": key,
                    "collector": collector.get("collector_name"),
                    "error": str(exc),
                    "progress_pct": progress,
                },
            )
            await db.commit()

    job.metadata_payload = {
        **(job.metadata_payload or {}),
        **telemetry_summary,
        "collector_total": len(parameters),
        "collector_collected": len(findings),
        "collector_incomplete": telemetry_summary["collector_failures"]
        + telemetry_summary["collector_timeouts"],
    }
    await db.commit()
    return findings


async def run_assessment_job(job_id: str, *, worker_id: str | None = None) -> dict[str, Any]:
    """Execute a queued assessment job end to end."""

    async with AsyncSessionLocal() as db:
        job = await _load_job(db, job_id)
        assessment = await _load_assessment(db, job.assessment_id)
        job.worker_id = worker_id
        job.error_message = None
        job.metadata_payload = {
            **(job.metadata_payload or {}),
            "runtime": "phase7b_powershell",
            "worker_id": worker_id,
        }

        try:
            await _set_stage(
                db,
                assessment=assessment,
                job=job,
                status="running",
                stage=RUNTIME_STAGES["starting"][0],
                progress=RUNTIME_STAGES["starting"][1],
                event_type="assessment.started",
                payload={"job_id": str(job.id), "worker_id": worker_id},
            )
            await _set_stage(
                db,
                assessment=assessment,
                job=job,
                status="running",
                stage=RUNTIME_STAGES["collecting"][0],
                progress=RUNTIME_STAGES["collecting"][1],
                event_type="progress.update",
            )

            findings = await _collect_findings(db, assessment=assessment, job=job)
            incomplete_count = int((job.metadata_payload or {}).get("collector_incomplete") or 0)
            if incomplete_count:
                assessment.status = "incomplete"
                assessment.progress_pct = RUNTIME_STAGES["completed"][1]
                job.status = "incomplete"
                job.current_stage = "incomplete"
                job.progress_pct = RUNTIME_STAGES["completed"][1]
                job.completed_at = _utc_now()
                job.error_message = (
                    f"{incomplete_count} collector(s) failed or were not collected; "
                    "scoring and recommendations were not generated"
                )
                await emit_event(
                    db,
                    assessment_id=assessment.id,
                    tenant_id=assessment.tenant_id,
                    event_type="assessment.incomplete",
                    severity="warning",
                    payload={
                        "job_id": str(job.id),
                        "collector_total": (job.metadata_payload or {}).get("collector_total"),
                        "collector_collected": len(findings),
                        "collector_incomplete": incomplete_count,
                        "progress_pct": RUNTIME_STAGES["completed"][1],
                    },
                )
                await audit_service.log_event(
                    db,
                    tenant_id=assessment.tenant_id,
                    event=AuditEvent.ASSESSMENT_FAILED,
                    action="assessment.incomplete",
                    user_id=assessment.triggered_by_user_id,
                    resource="assessments",
                    metadata={
                        "assessment_id": str(assessment.id),
                        "job_id": str(job.id),
                        "collector_incomplete": incomplete_count,
                    },
                )
                await db.commit()
                return {
                    "assessment_id": str(assessment.id),
                    "job_id": str(job.id),
                    "status": assessment.status,
                    "progress_pct": assessment.progress_pct,
                    "findings": len(findings),
                    "collector_incomplete": incomplete_count,
                }

            await _set_stage(
                db,
                assessment=assessment,
                job=job,
                status="running",
                stage=RUNTIME_STAGES["evaluating"][0],
                progress=RUNTIME_STAGES["evaluating"][1],
                event_type="progress.update",
            )
            await _set_stage(
                db,
                assessment=assessment,
                job=job,
                status="running",
                stage=RUNTIME_STAGES["scoring"][0],
                progress=RUNTIME_STAGES["scoring"][1],
                event_type="progress.update",
            )
            scores = apply_scores(assessment, findings)
            await emit_event(
                db,
                assessment_id=assessment.id,
                tenant_id=assessment.tenant_id,
                event_type="scoring.completed",
                payload={"scores": scores, "progress_pct": RUNTIME_STAGES["scoring"][1]},
            )
            await db.commit()

            await _set_stage(
                db,
                assessment=assessment,
                job=job,
                status="running",
                stage=RUNTIME_STAGES["recommendations"][0],
                progress=RUNTIME_STAGES["recommendations"][1],
                event_type="progress.update",
            )
            recommendations = await generate_recommendations(
                db,
                assessment_id=assessment.id,
                tenant_id=assessment.tenant_id,
                findings=findings,
            )
            for recommendation in recommendations:
                await emit_event(
                    db,
                    assessment_id=assessment.id,
                    tenant_id=assessment.tenant_id,
                    event_type="recommendation.generated",
                    severity=recommendation.severity,
                    payload={
                        "recommendation": {
                            "id": str(recommendation.id),
                            "assessment_id": str(recommendation.assessment_id),
                            "parameter_key": recommendation.parameter_key,
                            "severity": recommendation.severity,
                            "title": recommendation.title,
                            "recommendation_text": recommendation.recommendation_text,
                            "remediation_steps": recommendation.remediation_steps,
                            "effort": recommendation.effort,
                            "impact": recommendation.impact,
                            "priority_score": calculate_priority_score(
                                severity=recommendation.severity,
                                effort=recommendation.effort,
                                copilot_impact=recommendation.impact,
                            ),
                        },
                        "progress_pct": RUNTIME_STAGES["recommendations"][1],
                    },
                )
            await db.commit()

            assessment.status = "completed"
            assessment.progress_pct = RUNTIME_STAGES["completed"][1]
            job.status = "completed"
            job.current_stage = RUNTIME_STAGES["completed"][0]
            job.progress_pct = RUNTIME_STAGES["completed"][1]
            job.completed_at = _utc_now()
            await emit_event(
                db,
                assessment_id=assessment.id,
                tenant_id=assessment.tenant_id,
                event_type="assessment.completed",
                payload={
                    "assessment": {
                        "id": str(assessment.id),
                        "tenant_id": assessment.tenant_id,
                        "status": assessment.status,
                        "progress_pct": assessment.progress_pct,
                        "overall_score": assessment.overall_score,
                        "identity_score": assessment.identity_score,
                        "security_score": assessment.security_score,
                        "compliance_score": assessment.compliance_score,
                        "collaboration_score": assessment.collaboration_score,
                        "licensing_score": assessment.licensing_score,
                        "total_findings": assessment.total_findings,
                        "critical_findings": assessment.critical_findings,
                        "high_findings": assessment.high_findings,
                    },
                    "job_id": str(job.id),
                    "progress_pct": RUNTIME_STAGES["completed"][1],
                },
            )
            await audit_service.log_event(
                db,
                tenant_id=assessment.tenant_id,
                event=AuditEvent.ASSESSMENT_COMPLETED,
                action="assessment.completed",
                user_id=assessment.triggered_by_user_id,
                resource="assessments",
                metadata={"assessment_id": str(assessment.id), "job_id": str(job.id)},
            )
            await db.commit()
            return {
                "assessment_id": str(assessment.id),
                "job_id": str(job.id),
                "status": assessment.status,
                "progress_pct": assessment.progress_pct,
                "findings": len(findings),
                "recommendations": len(recommendations),
            }
        except Exception as exc:
            await db.rollback()
            job = await _load_job(db, job_id)
            assessment = await _load_assessment(db, job.assessment_id)
            now = _utc_now()
            assessment.status = "failed"
            job.status = "failed"
            job.current_stage = "failed"
            job.error_message = str(exc)
            job.completed_at = now
            await emit_event(
                db,
                assessment_id=assessment.id,
                tenant_id=assessment.tenant_id,
                event_type="assessment.failed",
                severity="error",
                payload={"error": str(exc), "job_id": str(job.id)},
            )
            await audit_service.log_event(
                db,
                tenant_id=assessment.tenant_id,
                event=AuditEvent.ASSESSMENT_FAILED,
                action="assessment.failed",
                user_id=assessment.triggered_by_user_id,
                resource="assessments",
                metadata={
                    "assessment_id": str(assessment.id),
                    "job_id": str(job.id),
                    "error": str(exc),
                },
            )
            await db.commit()
            return {
                "assessment_id": str(assessment.id),
                "job_id": str(job.id),
                "status": "failed",
                "error": str(exc),
            }
