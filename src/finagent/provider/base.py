"""BaseSandbox — Harbor BaseEnvironment analogue (isolation provider only).

Not a market-data or MCP plugin. MCP / Qieman attach via PluginFactory.
Yahoo harvest stays adapters/ama/yahoo.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExecResult:
    stdout: str | None = None
    stderr: str | None = None
    return_code: int = 0


class BaseSandbox(ABC):
    """Isolation provider. Harbor cousin: harbor.environments.base.BaseEnvironment."""

    session_home: Path

    @staticmethod
    @abstractmethod
    def type() -> str:
        """'local-process' | later 'docker' | custom str."""

    @abstractmethod
    async def start(self, *, force_build: bool = False) -> None: ...

    @abstractmethod
    async def stop(self, *, delete: bool = True) -> None: ...

    @abstractmethod
    async def exec(
        self,
        argv: list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_sec: float | None = None,
    ) -> ExecResult:
        """argv is a list (no implicit shell). Official-CLI benches call exec_sync."""

    def exec_sync(
        self,
        argv: list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_sec: float | None = None,
    ) -> ExecResult:
        """Sync subprocess.run analogue. FinMCP / opted-in benches call this, not await exec."""
        raise NotImplementedError(f"{self.type()} exec_sync")
