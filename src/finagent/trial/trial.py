"""Thin Trial — extras, seating skip, plugin_env, to_thread(run_official), stop.

Not a Harbor Trial state machine. Default EnvAdapterAsBench still ignores
sandbox. FinMCP (opt-in) uses plugin_env + sandbox.exec_sync.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from finagent.scorecard.types import SuiteResult, SuiteStatus, skipped_suite
from finagent.benches.factory import BenchFactory, ProtocolFactory
from finagent.harness.base import BaseHarness
from finagent.harness.factory import HarnessFactory
from finagent.plugins.base import PluginMount
from finagent.plugins.factory import PluginFactory
from finagent.provider.factory import SandboxFactory
from finagent.trial.config import TrialConfig

from finagent._paths import REPO_ROOT as ROOT


class Trial:
    def __init__(
        self,
        config: TrialConfig,
        *,
        repo_root: Path | None = None,
        harness: BaseHarness | None = None,
    ) -> None:
        self.config = config
        self.repo_root = Path(repo_root) if repo_root is not None else ROOT
        self.harness = harness or HarnessFactory.create(config.harness)
        py_raw = config.python
        python = Path(py_raw) if py_raw else None
        self.sandbox = SandboxFactory.create(
            config.sandbox_type,
            python=python,
            session_id=f"{self.harness.name()}__{config.suite_id}",
            artifacts_dir=self.repo_root / "artifacts" / "_sessions",
        )
        self.bench = BenchFactory.create(config.suite_id, repo_root=self.repo_root)
        self.plugins = [PluginFactory.create(n) for n in config.plugins]
        proto = config.protocol or ProtocolFactory.create(config.suite_id)
        proto.extra = dict(proto.extra)
        proto.extra["execute"] = config.execute
        proto.extra["artifacts_dir"] = config.artifacts_dir or str(
            self.repo_root / "artifacts" / config.suite_id.split(".")[0]
        )
        proto.extra["python"] = str(python or proto.extra.get("python") or sys.executable)
        proto.extra["harness_name"] = self.harness.name()
        proto.extra["sandbox_type"] = self.sandbox.type()
        proto.extra["plugins"] = list(config.plugins)
        self.protocol = proto

    def _skip(self, notes: str) -> SuiteResult:
        return skipped_suite(self.config.suite_id, protocol=self.protocol, notes=notes)

    def _run_official_sync(self) -> SuiteResult:
        return self.bench.run_official(self.harness, self.protocol, self.sandbox)

    async def run(self) -> SuiteResult:
        seated = self.harness.suite_ids()
        if self.config.suite_id not in seated:
            return self._skip(
                f"harness {self.harness.name()!r} suite_ids={sorted(seated) or '∅'} "
                f"does not sit {self.config.suite_id}; skip (not HOLD-fill)"
            )
        await self.sandbox.start()
        try:
            mounts: list[PluginMount] = []
            for plugin in self.plugins:
                mounts.append(await plugin.mount(self.sandbox))
            harness_mcp = [s for m in mounts for s in m.mcp_servers]
            env_overlay: dict[str, str] = {}
            for mount in mounts:
                env_overlay.update(mount.env)
            self.protocol.extra["plugin_env"] = dict(env_overlay)
            # Fail-closed ONLY for harness-native MCPServerConfig, not FinMCP env.
            if harness_mcp and not self.harness.features().mcp_servers:
                return self._skip(
                    "harness-native MCPServerConfig mounted but features().mcp_servers "
                    "is false (Harbor Trial._validate_agent_capabilities analogue). "
                    "FinMCP plugin_env-only mounts must not take this branch."
                )
            if harness_mcp:
                self.harness.bind_mcp(harness_mcp)
            await self.harness.setup(self.sandbox)
            return await asyncio.to_thread(self._run_official_sync)
        except Exception as exc:  # noqa: BLE001
            return SuiteResult(
                suite_id=self.config.suite_id,
                status=SuiteStatus.ERROR.value,
                protocol=self.protocol,
                notes=f"trial caught: {exc}",
            )
        finally:
            for plugin in reversed(self.plugins):
                await plugin.unmount(self.sandbox)
            await self.sandbox.stop(delete=True)
