"""EnvAdapterAsBench — factory always returns this wrapper.

Default run_official ignores sandbox and calls EnvAdapter.run on the
host (today's subprocess). FinMCP opts into sandbox.exec_sync.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from adapters.base import EnvAdapter, ProtocolSpec
from finagent.scorecard.types import SuiteResult


class EnvAdapterAsBench:
    """Always-on wrapper. EnvAdapter.run stays the scored SPI until a bench opts into sandbox."""

    opt_in_sandbox = False
    default_plugins: tuple[str, ...] = ()

    def __init__(self, inner: EnvAdapter) -> None:
        self.inner = inner
        self.suite_id = inner.suite_id
        self.module_dir = inner.module_dir

    def describe(self) -> Mapping[str, Any]:
        return self.inner.describe()

    def run_official(
        self,
        harness: object,
        protocol: ProtocolSpec,
        sandbox: object | None = None,
    ) -> SuiteResult:
        del sandbox  # default wrapper: host subprocess as today
        return self.inner.run(harness.as_agent_adapter(), protocol)

    def generate(self, output_dir: Path, *, limit: int | None = None) -> list[Path]:
        del output_dir, limit
        raise NotImplementedError(f"{self.suite_id} has no Harbor-like generate()")


class FinMcpEnvAdapterAsBench(EnvAdapterAsBench):
    """Opt-in: official CLI via sandbox.exec_sync + plugin_env (not await exec)."""

    opt_in_sandbox = True
    default_plugins: tuple[str, ...] = ("mcp",)

    def run_official(
        self,
        harness: object,
        protocol: ProtocolSpec,
        sandbox: object | None = None,
    ) -> SuiteResult:
        proto = ProtocolSpec(
            suite_id=protocol.suite_id,
            date_from=protocol.date_from,
            date_to=protocol.date_to,
            universe=list(protocol.universe or []),
            data_vintage=protocol.data_vintage,
            extra=dict(protocol.extra),
        )
        proto.extra.setdefault("plugin_env", {})
        if sandbox is not None:
            proto.extra["_sandbox"] = sandbox
        return self.inner.run(harness.as_agent_adapter(), proto)
