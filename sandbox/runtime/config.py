"""TrialConfig — thin runtime options for one harness × bench sitting."""

from __future__ import annotations

from dataclasses import dataclass, field

from adapters.base import ProtocolSpec


@dataclass
class TrialConfig:
    harness: str
    suite_id: str
    sandbox_type: str = "local-process"
    plugins: list[str] = field(default_factory=list)
    protocol: ProtocolSpec | None = None
    execute: bool = False
    artifacts_dir: str | None = None
    python: str | None = None
