"""OpenPM-Bench — point-in-time portfolio + honesty / audit trail.

Upstream: https://github.com/aslcai/OpenPM-Bench
Dataset: https://huggingface.co/datasets/aslcai/OpenPM-Bench
Preferred over PortBench (GOAL.md optional lock). Apache-2.0.

Official surface: `python -m agents.portfolio --provider llm_tiered ...`
Canonical README window: 2026-03-02 .. 2026-05-01, S&P 500 PIT membership.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .base import (
    AgentAdapter,
    Artifact,
    EnvAdapter,
    Metric,
    ProtocolSpec,
    SuiteResult,
    SuiteStatus,
    skipped_suite,
)
from .v2_runtime import (
    error_result,
    execute_or_skip,
    python_imports_ok,
    repo_venv_python,
    run_logged,
    skip_message,
    tail_text,
    uv_pip_install,
    xai_env,
)

SUITE_ID = "openpm.portfolio_pit"
MODULE_REL = "modules/openpm"
UPSTREAM_CLI = (
    "python -m agents.portfolio --provider llm_tiered "
    "--llm-provider openai --model <model> "
    "--start-date 2026-03-02 --end-date 2026-05-01 "
    "--api-key-env XAI_API_KEY --base-url https://api.x.ai/v1"
)
DEFAULT_FROM = "2026-03-02"
DEFAULT_TO = "2026-05-01"
VENV_NAME = "v2_openpm"


class OpenPmEnvAdapter:
    suite_id = SUITE_ID
    module_dir = MODULE_REL

    def __init__(self, repo_root: str | Path = ".") -> None:
        self.repo_root = Path(repo_root).resolve()
        self.module_path = self.repo_root / MODULE_REL

    def describe(self) -> Mapping[str, Any]:
        return {
            "suite_id": SUITE_ID,
            "role": "exam_room",
            "layer": "environment.portfolio_pit",
            "task_suite": "point_in_time_portfolio + honesty_audit",
            "tier": "optional",
            "required_for_promote": False,
            "module": str(self.module_path),
            "entry": "python -m agents.portfolio --provider llm_tiered",
            "artifacts": "reports/evaluations/<provider>.json",
            "metrics": [
                "total_return",
                "sharpe",
                "max_drawdown",
                "beat_all_benchmarks",
            ],
            "pitfalls": [
                "dataset/panel/price_panel_5m.parquet is gitignored; HF or rebuild",
                "LLM path is BYOK (--api-key-env); baselines run without a key if the panel exists",
            ],
            "wired": True,
        }

    def run(self, agent: AgentAdapter, protocol: ProtocolSpec) -> SuiteResult:
        _ = agent
        proto = ProtocolSpec(
            suite_id=SUITE_ID,
            date_from=protocol.date_from or DEFAULT_FROM,
            date_to=protocol.date_to or DEFAULT_TO,
            universe=list(protocol.universe or ["SP500_PIT"]),
            data_vintage=protocol.data_vintage
            or "OpenPM-Bench PIT S&P 500 5m panel + wikipedia_historical membership",
            execution_timing=protocol.execution_timing or "60min_post_open_then_hold",
            extra=dict(protocol.extra),
        )
        proto.extra.setdefault("provider", "llm_tiered")
        proto.extra.setdefault("rebalance", "once")
        proto.extra.setdefault("pit_membership", True)
        proto.extra.setdefault("risk", "balanced")
        proto.extra.setdefault("dataset", "https://huggingface.co/datasets/aslcai/OpenPM-Bench")
        skipped = execute_or_skip(
            suite_id=SUITE_ID,
            protocol=proto,
            upstream_cli=UPSTREAM_CLI,
            blockers=_hard_blockers(self.module_path),
            skip_notes=_skip_notes(self.module_path, dry=True),
        )
        if skipped:
            return skipped
        try:
            return self._run_full(proto)
        except Exception as exc:  # noqa: BLE001
            return error_result(
                SUITE_ID,
                proto,
                f"openpm official CLI error: {exc}",
                upstream_cli=UPSTREAM_CLI,
            )

    def _run_full(self, proto: ProtocolSpec) -> SuiteResult:
        from runners.grok import DEFAULT_MODEL_API, refresh_xai_api_key

        key = refresh_xai_api_key()
        if not key:
            return skipped_suite(
                SUITE_ID,
                protocol=proto,
                upstream_cli=UPSTREAM_CLI,
                notes="skip: XAI_API_KEY / ~/.grok/auth.json missing; BYOK LLM path blocked",
            )
        artifacts = Path(
            proto.extra.get("artifacts_dir") or (self.repo_root / "artifacts" / "openpm")
        )
        artifacts.mkdir(parents=True, exist_ok=True)
        python = proto.extra.get("python") or repo_venv_python(self.repo_root, VENV_NAME)
        model = str(proto.extra.get("model") or DEFAULT_MODEL_API)
        proto.extra["model"] = model
        _ensure_openpm_install(python)

        outdir = artifacts / "reports"
        outdir.mkdir(parents=True, exist_ok=True)
        log_path = artifacts / "portfolio.log"
        oom_stamp = artifacts / "oom_sigkill.json"
        if oom_stamp.is_file():
            return skipped_suite(
                SUITE_ID,
                protocol=proto,
                upstream_cli=UPSTREAM_CLI,
                notes=(
                    "skip: official llm_tiered previously SIGKILL/OOM (returncode=-9) "
                    "loading dataset/feature_output/feature_output.ndjson (2.6GiB → ~7.3GiB RSS) "
                    "on this 15GiB host with 0 swap. Stamp: "
                    + str(oom_stamp)
                    + ". Not inventing --max-bars / --universe subset."
                ),
            )
        cmd = [
            python,
            "-m",
            "agents.portfolio",
            "--provider",
            "llm_tiered",
            "--llm-provider",
            "openai",
            "--model",
            model,
            "--constructor-model",
            model,
            "--api-key-env",
            "XAI_API_KEY",
            "--base-url",
            "https://api.x.ai/v1",
            "--start-date",
            proto.date_from or DEFAULT_FROM,
            "--end-date",
            proto.date_to or DEFAULT_TO,
            "--rebalance",
            str(proto.extra.get("rebalance") or "once"),
            "--risk",
            str(proto.extra.get("risk") or "balanced"),
            "--outdir",
            str(outdir),
        ]
        env = xai_env(pythonpath_dirs=[self.module_path, self.repo_root])
        env["XAI_API_KEY"] = key
        env["OPENAI_API_KEY"] = key
        proc = run_logged(cmd, cwd=self.module_path, env=env, log_path=log_path)
        if proc.returncode == -9:
            oom_stamp.write_text(
                json.dumps({"returncode": -9, "log": str(log_path)}, indent=2) + "\n",
                encoding="utf-8",
            )
            return skipped_suite(
                SUITE_ID,
                protocol=proto,
                upstream_cli=" ".join(cmd),
                notes=(
                    "skip: official `python -m agents.portfolio --provider llm_tiered` "
                    "SIGKILL/OOM (returncode=-9) loading dataset/feature_output/feature_output.ndjson "
                    "(2.6GiB on disk; ~7.3GiB anon-rss) on this 15GiB host with 0 swap. "
                    "Panel+features are present. Not inventing --max-bars / --universe subset. "
                    f"log={log_path}"
                ),
            )
        eval_json = _find_eval_json(outdir)
        harvested = _harvest_openpm(eval_json)
        if proc.returncode != 0 and not eval_json:
            status = SuiteStatus.ERROR.value
        elif eval_json:
            status = SuiteStatus.PASS.value if proc.returncode == 0 else SuiteStatus.FAIL.value
        else:
            status = SuiteStatus.FAIL.value
        metrics = [
            Metric(name=k, value=v, source=str(eval_json) if eval_json else "openpm")
            for k, v in harvested.items()
            if isinstance(v, (int, float))
        ]
        arts = [Artifact(kind="log", path=str(log_path), media_type="text/plain")]
        if eval_json:
            arts.append(Artifact(kind="evaluation_json", path=str(eval_json), media_type="application/json"))
        notes = (
            f"Official OpenPM llm_tiered window {proto.date_from}..{proto.date_to} "
            f"rebalance={proto.extra.get('rebalance')} model={model} "
            f"returncode={proc.returncode} eval={eval_json}. "
            + tail_text(log_path, 20).replace("\n", " | ")[:400]
        )
        return SuiteResult(
            suite_id=SUITE_ID,
            status=status,
            protocol=proto,
            metrics=metrics,
            artifacts=arts,
            traces_path=str(outdir),
            notes=notes,
            upstream_cli=" ".join(cmd),
        )


def _hard_blockers(module_path: Path) -> list[str]:
    blockers: list[str] = []
    if not module_path.is_dir():
        blockers.append("modules/openpm missing (run scripts/clone_modules.sh)")
    panel = module_path / "dataset" / "panel" / "price_panel_5m.parquet"
    if not panel.is_file():
        blockers.append(
            "dataset/panel/price_panel_5m.parquet missing (HF aslcai/OpenPM-Bench or rebuild)"
        )
    features = module_path / "dataset" / "feature_output" / "feature_output.ndjson"
    if not features.is_file():
        blockers.append("dataset/feature_output/feature_output.ndjson missing")
    entry = module_path / "agents" / "portfolio" / "__main__.py"
    if not entry.is_file():
        blockers.append("agents/portfolio/__main__.py missing")
    return blockers


def _skip_notes(module_path: Path, *, dry: bool) -> str:
    return skip_message(_hard_blockers(module_path), dry=dry)


def _ensure_openpm_install(python: str) -> None:
    if python_imports_ok(python, "pandas", "numpy", "pyarrow", "openai", "httpx"):
        return
    print("[openpm] installing runtime deps", flush=True)
    uv_pip_install(python, "pandas", "numpy", "pyarrow", "openai", "httpx", "yfinance", "lxml")


def _find_eval_json(outdir: Path) -> Path | None:
    hits = sorted((outdir / "evaluations").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if (outdir / "evaluations").is_dir() else []
    if not hits:
        hits = sorted(outdir.rglob("evaluations/*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return hits[0] if hits else None


def _harvest_openpm(path: Path | None) -> dict[str, float]:
    if path is None or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, float] = {}
    metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else data
    if not isinstance(metrics, dict):
        return out
    mapping = {
        "total_return": ("total_return", "totalReturn", "return"),
        "sharpe": ("sharpe", "sharpe_ratio", "annualized_sharpe"),
        "max_drawdown": ("max_drawdown", "maxDrawdown", "mdd"),
        "beat_all_benchmarks": ("beat_all_benchmarks",),
    }
    for dest, keys in mapping.items():
        for k in keys:
            val = metrics.get(k)
            if val is None and isinstance(data.get(k), (int, float, bool)):
                val = data.get(k)
            if isinstance(val, bool):
                out[dest] = 1.0 if val else 0.0
                break
            if isinstance(val, (int, float)):
                out[dest] = float(val)
                break
    return out


def _assert_protocol() -> None:
    _: EnvAdapter = OpenPmEnvAdapter()  # type: ignore[assignment]


__all__ = ["SUITE_ID", "OpenPmEnvAdapter"]
