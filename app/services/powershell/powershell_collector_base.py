"""
PowerShell collector script resolution.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


POWERSHELL_ROOT = Path(__file__).resolve().parents[2] / "powershell"


def collector_slug(collector: dict[str, Any], parameter: dict[str, Any]) -> str:
    raw = collector.get("collector_name") or collector.get("powershell_script") or parameter["parameter_key"]
    raw = str(raw).split(".")[-1]
    return re.sub(r"[^a-zA-Z0-9_]+", "_", raw.strip().lower()).strip("_")


class PowerShellCollectorResolver:
    def __init__(self, *, root: Path = POWERSHELL_ROOT) -> None:
        self.root = root

    def resolve_script(self, *, collector: dict[str, Any], parameter: dict[str, Any]) -> Path:
        slug = collector_slug(collector, parameter)
        candidates = list(self.root.glob(f"*/{slug}.ps1"))
        if candidates:
            return candidates[0]
        return self.root / "generic_collector.ps1"
