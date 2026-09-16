"""BaseHarness — Harbor BaseAgent analogue.

Trial skip gate is suite_ids() (empty = sit none). Do not conflate with
AgentAdapter.capabilities() (empty = all; unused by the eval loop).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adapters.base import AgentAdapter


@dataclass
class HarnessCapabilities:
    """Harbor AgentCapabilities analogue. Not a ClassVar: Grok API vs CLI differ."""

    decide_lcd: bool = False
    native_cli: bool = False
    mcp_servers: bool = False
    skills: bool = False


class BaseHarness(ABC):
    """Unit under test. Sits only the benches in suite_ids(); empty means none.

    Harbor cousin: harbor.agents.base.BaseAgent
    Current cousin: adapters.base.AgentAdapter + finagent.harness.grok.GrokCliAgentAdapter
    """

    @staticmethod
    @abstractmethod
    def name() -> str:
        """Registry key, e.g. 'grok-cli'."""

    @abstractmethod
    def version(self) -> str | None: ...

    def features(self) -> HarnessCapabilities:
        return HarnessCapabilities()

    def suite_ids(self) -> set[str]:
        """Benches this instance will sit. Empty = sit none (NOT AgentAdapter empty=all)."""
        return set()

    def as_agent_adapter(self) -> AgentAdapter:
        """LCD for benches whose seating cell is decide() (AMA, FINSABER, FinTool)."""
        raise NotImplementedError(f"{self.name()} does not expose decide()")

    async def setup(self, sandbox: object) -> None:
        """Harbor BaseAgent.setup: install CLI; write native config under sandbox HOME.

        The only place that writes ~/.grok/config.toml (session HOME, never
        operator $HOME). Plugins do not take a harness argument. API-backend
        Grok is a no-op. Default: no-op.
        """
        del sandbox

    async def run(self, instruction: str, sandbox: object, context: dict) -> None:
        """Harbor BaseAgent.run. Official-CLI benches call BenchAdapter.run_official."""
        raise NotImplementedError

    def bind_mcp(self, servers: list[object]) -> None:
        """Store Harbor-shaped MCP configs for setup(). Unused until a harness-native MCP bench."""
        self._mcp_servers = list(servers)

    def preflight(self) -> None:
        """Harbor BaseAgent.preflight analogue: credentials present?"""
