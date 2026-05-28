"""
Registry-driven PowerShell collector runtime.
"""

from __future__ import annotations

from typing import Any

from app.services.powershell.powershell_collector_base import PowerShellCollectorResolver
from app.services.powershell.powershell_executor import (
    PowerShellExecution,
    PowerShellExecutionResult,
    PowerShellExecutor,
)
from app.services.powershell.powershell_result_parser import (
    PowerShellResultParseError,
    contract_to_collector_result,
    failure_contract,
    parse_collector_contract,
)


class PowerShellExecutionEngine:
    def __init__(
        self,
        *,
        executor: PowerShellExecutor | None = None,
        resolver: PowerShellCollectorResolver | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.executor = executor or PowerShellExecutor()
        self.resolver = resolver or PowerShellCollectorResolver()
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _max_retries(collector: dict[str, Any]) -> int:
        strategy = collector.get("throttling_strategy") or {}
        try:
            return max(0, min(int(strategy.get("max_retries", 0)), 3))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _failure_result(
        *,
        parameter: dict[str, Any],
        collector: dict[str, Any],
        execution_result: PowerShellExecutionResult,
        message: str,
        telemetry: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        telemetry = telemetry or execution_result.telemetry
        contract = failure_contract(
            collector=collector.get("collector_name") or parameter["parameter_key"],
            tenant_id=str(collector.get("tenant_id") or ""),
            parameter_key=parameter["parameter_key"],
            message=message,
            severity=parameter.get("severity") or "info",
            telemetry=telemetry,
        )
        return contract_to_collector_result(
            parameter=parameter,
            collector=collector,
            contract=contract,
            telemetry=telemetry,
        )

    @staticmethod
    def _contract_uses_mock_data(contract: dict[str, Any]) -> bool:
        text = " ".join(str(item).lower() for item in contract.get("warnings") or [])
        if "mock" in text or "simulated" in text:
            return True
        for finding in contract.get("findings") or []:
            if not isinstance(finding, dict):
                continue
            value = finding.get("value")
            if isinstance(value, dict) and str(value.get("source", "")).lower() in {
                "local_mock",
                "mock",
                "simulated",
            }:
                return True
        return False

    async def run_collector(
        self,
        *,
        tenant_id: str,
        parameter: dict[str, Any],
        collector: dict[str, Any],
        assessment_id: str | None = None,
    ) -> dict[str, Any]:
        manifest_entry = self.resolver.get_manifest_entry(parameter["parameter_key"]) or {}
        collector_context = {**collector, **manifest_entry}
        collector_with_context = {**collector_context, "tenant_id": tenant_id}
        try:
            script_path = self.resolver.resolve_script(collector=collector_context, parameter=parameter)
        except FileNotFoundError as exc:
            execution_result = PowerShellExecutionResult(
                status="failed",
                stdout="",
                stderr=str(exc),
                exit_code=None,
                duration_ms=0,
                attempts=0,
                errors=[str(exc)],
            )
            telemetry = execution_result.telemetry
            telemetry["source_script"] = None
            return self._failure_result(
                parameter=parameter,
                collector=collector_with_context,
                execution_result=execution_result,
                message=str(exc),
                telemetry=telemetry,
            )

        execution = PowerShellExecution(
            script_path=script_path,
            tenant_id=tenant_id,
            collector_name=collector.get("collector_name") or parameter["parameter_key"],
            parameter_key=parameter["parameter_key"],
            parameter=parameter,
            collector=collector_context,
            assessment_id=assessment_id,
            output_root=str(collector_context.get("output_root") or "artifacts"),
            timeout_seconds=float(collector_context.get("timeout_seconds") or self.timeout_seconds),
            max_retries=self._max_retries(collector_context),
        )
        execution_result = await self.executor.execute(execution)
        telemetry = execution_result.telemetry
        telemetry["source_script"] = str(script_path)

        if execution_result.status != "success":
            message = "; ".join(execution_result.errors) or execution_result.stderr or "PowerShell collector failed"
            return self._failure_result(
                parameter=parameter,
                collector=collector_with_context,
                execution_result=execution_result,
                message=message,
                telemetry=telemetry,
            )

        try:
            contract = parse_collector_contract(execution_result.stdout)
        except PowerShellResultParseError as exc:
            return self._failure_result(
                parameter=parameter,
                collector=collector_with_context,
                execution_result=execution_result,
                message=str(exc),
                telemetry=telemetry,
            )
        telemetry["generated_files"] = (
            contract.get("metrics", {}).get("generated_files")
            or contract.get("metrics", {}).get("generatedFiles")
            or []
        )

        if self._contract_uses_mock_data(contract):
            return self._failure_result(
                parameter=parameter,
                collector=collector_with_context,
                execution_result=execution_result,
                message="Collector returned mocked or simulated data; refusing to persist fake evidence",
                telemetry=telemetry,
            )

        return contract_to_collector_result(
            parameter=parameter,
            collector=collector,
            contract=contract,
            telemetry=telemetry,
        )
