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
    ) -> dict[str, Any]:
        telemetry = execution_result.telemetry
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

    async def run_collector(
        self,
        *,
        tenant_id: str,
        parameter: dict[str, Any],
        collector: dict[str, Any],
    ) -> dict[str, Any]:
        collector_with_context = {**collector, "tenant_id": tenant_id}
        execution = PowerShellExecution(
            script_path=self.resolver.resolve_script(collector=collector, parameter=parameter),
            tenant_id=tenant_id,
            collector_name=collector.get("collector_name") or parameter["parameter_key"],
            parameter_key=parameter["parameter_key"],
            parameter=parameter,
            collector=collector,
            timeout_seconds=float(collector.get("timeout_seconds") or self.timeout_seconds),
            max_retries=self._max_retries(collector),
        )
        execution_result = await self.executor.execute(execution)

        if execution_result.status != "success":
            message = "; ".join(execution_result.errors) or execution_result.stderr or "PowerShell collector failed"
            return self._failure_result(
                parameter=parameter,
                collector=collector_with_context,
                execution_result=execution_result,
                message=message,
            )

        try:
            contract = parse_collector_contract(execution_result.stdout)
        except PowerShellResultParseError as exc:
            return self._failure_result(
                parameter=parameter,
                collector=collector_with_context,
                execution_result=execution_result,
                message=str(exc),
            )

        return contract_to_collector_result(
            parameter=parameter,
            collector=collector,
            contract=contract,
            telemetry=execution_result.telemetry,
        )
