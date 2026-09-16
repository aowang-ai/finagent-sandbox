"""EnvPlugin — finance env on top of a sandbox provider (not a sandbox type).

Harbor cousins: MCPServerConfig / task files — NOT EnvironmentType.
mount() must not take a harness argument and must not write native config.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sandbox.provider.base import BaseSandbox


@dataclass
class MCPServerConfig:
    """Harbor-shaped MCP server fields. Local copy; do not import harbor."""

    name: str
    transport: str = "http"
    url: str | None = None
    command: str | None = None
    args: list[str] = field(default_factory=list)


@dataclass
class PluginMount:
    mcp_servers: list[MCPServerConfig] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    notes: str = ""


class EnvPlugin(ABC):
    """Mounted into a sandbox. Yahoo harvest is not a plugin."""

    @staticmethod
    @abstractmethod
    def name() -> str: ...

    @abstractmethod
    def describe(self) -> dict: ...

    @abstractmethod
    async def mount(self, sandbox: BaseSandbox) -> PluginMount:
        """Return env and/or MCPServerConfig. Do not import harness types."""

    async def unmount(self, sandbox: BaseSandbox) -> None:
        del sandbox
