"""
Simulated collector engine.

No Microsoft Graph or PowerShell calls happen here. The goal is to validate
orchestration, persistence, scoring, recommendations, and live UI behavior.
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any


SEVERITY_RANK = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}


def _bucket(parameter_key: str) -> int:
    return int(hashlib.sha256(parameter_key.encode("utf-8")).hexdigest()[:8], 16)


def _status_for(parameter: dict[str, Any]) -> str:
    bucket = _bucket(parameter["parameter_key"]) % 10
    if bucket in {0, 1}:
        return "fail"
    if bucket in {2, 3}:
        return "warning"
    return "pass"


def _value_for(parameter: dict[str, Any], status: str) -> dict[str, Any]:
    bucket = _bucket(parameter["parameter_key"])
    score = 100 if status == "pass" else 72 if status == "warning" else 38
    return {
        "parameter_key": parameter["parameter_key"],
        "collector_type": parameter.get("collector_type", "unknown"),
        "simulated": True,
        "observed_score": score,
        "sample_size": 25 + (bucket % 300),
    }


async def run_simulated_collector(
    *,
    parameter: dict[str, Any],
    collector: dict[str, Any],
) -> dict[str, Any]:
    delay = 0.01 + ((_bucket(parameter["parameter_key"]) % 4) * 0.005)
    await asyncio.sleep(delay)
    status = _status_for(parameter)
    severity = parameter.get("severity") or "info"
    score_contribution = float(SEVERITY_RANK.get(severity, 1))
    if status == "pass":
        score_contribution = 0.0
    elif status == "warning":
        score_contribution = round(score_contribution * 0.45, 2)

    return {
        "parameter_key": parameter["parameter_key"],
        "status": status,
        "severity": severity,
        "raw_value": _value_for(parameter, status),
        "evaluated_value": (
            f"Simulated {status} result for {parameter['display_name']} "
            f"using {collector.get('collector_type', 'unknown')} collector"
        ),
        "score_contribution": score_contribution,
    }
