"""BenchAdapter — Harbor adapter analogue (typing only; no default bodies).

EnvAdapter stays the scored SPI on adapters/*.py. BenchFactory always
returns EnvAdapterAsBench; callers must not assume a raw *EnvAdapter
has run_official.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from adapters.base import ProtocolSpec
from finagent.scorecard.types import SuiteResult


class BenchAdapter(Protocol):
    suite_id: str
    module_dir: str

    def describe(self) -> Mapping[str, Any]: ...

    def run_official(
        self,
        harness: object,
        protocol: ProtocolSpec,
        sandbox: object | None = None,
    ) -> SuiteResult: ...
