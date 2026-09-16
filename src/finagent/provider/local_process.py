"""LocalProcessSandbox — first provider (session HOME, host process).

Not Docker. Host-process is not a security boundary. Session HOME keeps
harness-native writes off the operator $HOME.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from finagent.provider.base import BaseSandbox, ExecResult

from finagent._paths import REPO_ROOT as ROOT
DEFAULT_SESSIONS = ROOT / "artifacts" / "_sessions"


class LocalProcessSandbox(BaseSandbox):
    """session root artifacts/_sessions/<id>/{work,home}; HOME overlay on exec."""

    def __init__(
        self,
        *,
        python: Path | str | None = None,
        session_id: str | None = None,
        artifacts_dir: Path | str | None = None,
        **_kwargs: object,
    ) -> None:
        self.python = Path(python) if python else None
        self.session_id = session_id or uuid.uuid4().hex
        sessions_root = Path(artifacts_dir) if artifacts_dir is not None else DEFAULT_SESSIONS
        self._root = sessions_root / self.session_id
        self._work = self._root / "work"
        self._home = self._root / "home"
        self._started = False

    @staticmethod
    def type() -> str:
        return "local-process"

    def _exec_env(self, extra: dict[str, str] | None) -> dict[str, str]:
        env = os.environ.copy()
        if extra:
            env.update({str(k): str(v) for k, v in extra.items()})
        env["HOME"] = str(self.session_home)
        env["XDG_CONFIG_HOME"] = str(self.session_home / ".config")
        return env

    async def start(self, *, force_build: bool = False) -> None:
        del force_build
        self._work.mkdir(parents=True, exist_ok=True)
        self._home.mkdir(parents=True, exist_ok=True)
        (self._home / ".config").mkdir(parents=True, exist_ok=True)
        self.session_home = self._home
        (self._root / "session.env").write_text(
            f"HOME={self.session_home}\n"
            f"XDG_CONFIG_HOME={self.session_home / '.config'}\n"
            f"SESSION_ID={self.session_id}\n",
            encoding="utf-8",
        )
        self._started = True

    async def stop(self, *, delete: bool = True) -> None:
        if delete and self._root.exists():
            shutil.rmtree(self._root, ignore_errors=True)
        self._started = False

    async def exec(
        self,
        argv: list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_sec: float | None = None,
    ) -> ExecResult:
        return await asyncio.to_thread(
            self.exec_sync,
            argv,
            cwd=cwd,
            env=env,
            timeout_sec=timeout_sec,
        )

    def exec_sync(
        self,
        argv: list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_sec: float | None = None,
    ) -> ExecResult:
        if not self._started:
            raise RuntimeError("LocalProcessSandbox.exec_sync before start()")
        proc = subprocess.run(
            list(argv),
            cwd=cwd or str(self._work),
            env=self._exec_env(env),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        return ExecResult(
            stdout=proc.stdout,
            stderr=proc.stderr,
            return_code=int(proc.returncode),
        )
