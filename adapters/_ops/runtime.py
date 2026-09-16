"""Shared stdlib helpers for optional-suite EnvAdapters.

One place for subprocess, xAI env, skip notes, text patches, and JSON
harvest utilities. Suite-specific resume/harvest lives in `adapters/<bench>/ops.py`.
Doctor-safe (stdlib + `finagent.harness.grok` for key refresh). Filename is historical.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

from adapters.base import ProtocolSpec, SuiteResult, SuiteStatus, skipped_suite


XAI_BASE_URL = "https://api.x.ai/v1"


def repo_venv_python(repo_root: Path, name: str) -> str:
    path = repo_root / "venvs" / name / "bin" / "python"
    if path.is_file():
        return str(path)
    return sys.executable


def artifacts_dir(repo_root: Path, name: str) -> Path:
    path = repo_root / "artifacts" / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def port_open(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def which(cmd: str) -> str | None:
    return shutil.which(cmd)


def xai_env(
    extra: Mapping[str, str] | None = None,
    *,
    pythonpath_dirs: list[Path] | None = None,
) -> dict[str, str]:
    from finagent.harness.grok import refresh_xai_api_key

    env = os.environ.copy()
    key = refresh_xai_api_key() or env.get("XAI_API_KEY") or env.get("OPENAI_API_KEY") or ""
    if key:
        env["OPENAI_API_KEY"] = key
        env["XAI_API_KEY"] = key
        env["X_AI_API_KEY"] = key
        env["LLM_API_KEY"] = key
    env["OPENAI_BASE_URL"] = env.get("OPENAI_BASE_URL") or XAI_BASE_URL
    env["PYTHONUNBUFFERED"] = "1"
    if pythonpath_dirs:
        parts = [str(p) for p in pythonpath_dirs if p]
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = os.pathsep.join(parts + ([existing] if existing else []))
    if extra:
        env.update({str(k): str(v) for k, v in extra.items()})
    return env


def run_logged(
    cmd: list[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    log_path: Path,
    timeout: int | None = None,
    append: bool = False,
) -> subprocess.CompletedProcess[str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[suite] cwd={cwd} cmd={' '.join(cmd)} log={log_path}", flush=True)
    mode = "a" if append else "w"
    with log_path.open(mode, encoding="utf-8") as logf:
        logf.write(f"$ {' '.join(cmd)}\n")
        logf.flush()
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=dict(env),
            stdout=logf,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=timeout,
            text=True,
        )
    print(f"[suite] returncode={proc.returncode} log={log_path}", flush=True)
    return proc


def uv_pip_install(python: str, *pkgs: str) -> int:
    uv = shutil.which("uv")
    if uv:
        cmd = [uv, "pip", "install", "--python", python, *pkgs]
    else:
        cmd = [python, "-m", "pip", "install", *pkgs]
    print(f"[suite] {' '.join(cmd)}", flush=True)
    proc = subprocess.run(cmd, check=False)
    return int(proc.returncode)


def python_imports_ok(python: str, *mods: str) -> bool:
    if not mods:
        return True
    proc = subprocess.run(
        [python, "-c", "import " + ", ".join(mods)],
        check=False,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def tail_text(path: Path, n: int = 40) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-n:])


def skip_message(
    blockers: list[str],
    *,
    dry: bool = False,
    extras: Iterable[str] = (),
) -> str:
    notes = list(blockers)
    if dry:
        notes.append("dry: protocol.extra.execute is not true")
    notes.extend(extras)
    return "skip: " + "; ".join(notes)


def execute_or_skip(
    *,
    suite_id: str,
    protocol: ProtocolSpec,
    upstream_cli: str,
    blockers: list[str],
    skip_notes: str,
) -> SuiteResult | None:
    """Skip when dry-run or hard-blocked; None means the adapter should execute."""

    if not protocol.extra.get("execute"):
        return skipped_suite(
            suite_id,
            protocol=protocol,
            upstream_cli=upstream_cli,
            notes=skip_notes,
        )
    if blockers:
        return skipped_suite(
            suite_id,
            protocol=protocol,
            upstream_cli=upstream_cli,
            notes="skip: " + "; ".join(blockers),
        )
    return None


def error_result(
    suite_id: str,
    protocol: ProtocolSpec,
    notes: str,
    *,
    upstream_cli: str | None = None,
) -> SuiteResult:
    return SuiteResult(
        suite_id=suite_id,
        status=SuiteStatus.ERROR.value,
        protocol=protocol,
        notes=notes,
        upstream_cli=upstream_cli,
    )


def apply_text_patch(
    path: Path,
    *,
    marker: str,
    needle: str,
    replacement: str,
    label: str,
) -> bool:
    """Idempotent needle/replacement. True if the file was written."""

    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return False
    if needle not in text:
        print(f"[{label}] needle not found in {path.name}", flush=True)
        return False
    path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
    print(f"[{label}] patched {path.name}", flush=True)
    return True


def load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def json_list_len(path: Path) -> int:
    data = load_json(path)
    return len(data) if isinstance(data, list) else 0


def pid_alive(pid_path: Path) -> str:
    try:
        pid = int(pid_path.read_text().strip())
    except (OSError, ValueError):
        return "missing"
    try:
        os.kill(pid, 0)
        return f"run:{pid}"
    except OSError:
        return f"dead:{pid}"


def missing_clone(module_path: Path, name: str) -> str | None:
    if module_path.is_dir():
        return None
    return f"modules/{name} missing (run scripts/clone_modules.sh)"
