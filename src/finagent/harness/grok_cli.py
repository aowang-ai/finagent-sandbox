"""GrokCliHarness — peel of GrokRunner + GrokCliAgentAdapter.

OIDC / complete_json stay on GrokRunner. as_agent_adapter() returns the
existing GrokCliAgentAdapter so EnvAdapter.run(agent, protocol) is unchanged.
"""

from __future__ import annotations

from pathlib import Path

from adapters.base import ALL_SUITE_IDS, AgentAdapter
from finagent.harness.grok import GrokCliAgentAdapter, GrokRunner, refresh_xai_api_key
from finagent.harness.base import BaseHarness, HarnessCapabilities


class GrokCliHarness(BaseHarness):
    """Registered as 'grok-cli'. Sits every ALL_SUITE_IDS bench (required + optional)."""

    def __init__(
        self,
        *,
        backend: str | None = None,
        model: str | None = None,
        artifacts_dir: str | Path | None = None,
        runner: GrokRunner | None = None,
        **_kwargs: object,
    ) -> None:
        self.runner = runner or GrokRunner(
            backend=backend,
            model=model,
            artifacts_dir=artifacts_dir,
        )
        self._agent = GrokCliAgentAdapter(self.runner)

    @staticmethod
    def name() -> str:
        return "grok-cli"

    def version(self) -> str | None:
        return self.runner.model

    def features(self) -> HarnessCapabilities:
        cli = self.runner.backend == "cli"
        return HarnessCapabilities(
            decide_lcd=True,
            native_cli=cli,
            mcp_servers=cli,
            skills=False,
        )

    def suite_ids(self) -> set[str]:
        return set(ALL_SUITE_IDS)

    def as_agent_adapter(self) -> AgentAdapter:
        return self._agent

    def preflight(self) -> None:
        refresh_xai_api_key()

    async def setup(self, sandbox: object) -> None:
        """API backend: no-op. CLI backend: grok --version + session-HOME config.toml."""

        if self.runner.backend != "cli":
            return
        await sandbox.exec(["grok", "--version"])
        home = Path(sandbox.session_home)
        grok_dir = home / ".grok"
        grok_dir.mkdir(parents=True, exist_ok=True)
        (grok_dir / "config.toml").write_text(
            "# grok-cli session config (sandbox.session_home; never operator $HOME)\n",
            encoding="utf-8",
        )
