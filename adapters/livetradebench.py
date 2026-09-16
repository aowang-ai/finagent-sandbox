"""LiveTradeBench — live multi-market (US equities + Polymarket) exam room.

Upstream: https://github.com/ulab-uiuc/live-trade-bench  ·  arXiv:2511.03628
Site: https://trade-bench.live

Official live protocol is ~50 days. This adapter runs the official offline
entry `examples/backtest_demo.py` (documented backtest / replay) with Grok as
the LLM. Never invent a 1-day fake pass.

Patches / harvest / resume: `adapters.v2_ops.livetradebench`.
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
from .v2_ops.livetradebench import (
    DEFAULT_FROM,
    DEFAULT_TO,
    DEFAULT_UNIVERSE,
    MODULE_REL,
    SUITE_ID,
    UPSTREAM_CLI,
    VENV_NAME,
    apply_continue_patches,
    ensure_install,
    hard_blockers,
    harvest_backtest,
    harvest_existing_run,
    patch_backtest_models,
    patch_yfinance_scalar,
    skip_notes,
)
from .v2_runtime import (
    artifacts_dir,
    error_result,
    execute_or_skip,
    repo_venv_python,
    run_logged,
    tail_text,
    xai_env,
)


class LiveTradeBenchEnvAdapter:
    suite_id = SUITE_ID
    module_dir = MODULE_REL

    def __init__(self, repo_root: str | Path = ".") -> None:
        self.repo_root = Path(repo_root).resolve()
        self.module_path = self.repo_root / MODULE_REL

    def describe(self) -> Mapping[str, Any]:
        return {
            "suite_id": SUITE_ID,
            "role": "exam_room",
            "layer": "environment.live_multi_market",
            "task_suite": "live_portfolio_allocation",
            "wave": "v2",
            "required_for_promote": False,
            "module": str(self.module_path),
            "entry": "examples/backtest_demo.py (official offline/replay)",
            "artifacts": "backend/models_data_init.json + adapter results.json",
            "metrics": ["n_days", "total_return", "return_percentage"],
            "pitfalls": [
                "Paper live window is ~50 days; this pass uses the official backtest_demo defaults",
                "Needs live LLM keys; news/reddit fetchers optional",
                "PolyForm Noncommercial 1.0.0 — commercial use needs LICENSE.COMMERCIAL",
            ],
            "wired": True,
        }

    def run(self, agent: AgentAdapter, protocol: ProtocolSpec) -> SuiteResult:
        _ = agent
        proto = ProtocolSpec(
            suite_id=SUITE_ID,
            date_from=protocol.date_from or DEFAULT_FROM,
            date_to=protocol.date_to or DEFAULT_TO,
            universe=list(protocol.universe or DEFAULT_UNIVERSE),
            data_vintage=protocol.data_vintage or "official backtest_demo.py replay (yfinance)",
            extra=dict(protocol.extra),
        )
        proto.extra.setdefault("n_days", 50)
        proto.extra.setdefault("markets", ["us_equities"])
        proto.extra.setdefault("license", "PolyForm-Noncommercial-1.0.0")
        proto.extra.setdefault("protocol_entry", "examples/backtest_demo.py")
        skipped = execute_or_skip(
            suite_id=SUITE_ID,
            protocol=proto,
            upstream_cli=UPSTREAM_CLI,
            blockers=hard_blockers(self.module_path),
            skip_notes=skip_notes(self.module_path, dry=True),
        )
        if skipped:
            return skipped
        try:
            return self._run_full(proto)
        except Exception as exc:  # noqa: BLE001
            return error_result(
                SUITE_ID,
                proto,
                f"livetradebench official backtest error: {exc}",
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
                notes="skip: XAI_API_KEY / ~/.grok/auth.json missing; cannot run backtest_demo LLM",
            )
        artifacts = Path(proto.extra.get("artifacts_dir") or artifacts_dir(self.repo_root, "livetradebench"))
        artifacts.mkdir(parents=True, exist_ok=True)
        python = proto.extra.get("python") or repo_venv_python(self.repo_root, VENV_NAME)
        model = str(proto.extra.get("model") or f"xai/{DEFAULT_MODEL_API}")
        proto.extra["model"] = model
        ensure_install(python)
        patch_backtest_models(self.module_path, model)
        patch_yfinance_scalar(self.module_path)

        stocks = ",".join(
            s for s in (proto.universe or DEFAULT_UNIVERSE) if s and s.upper() != "POLYMARKET"
        )
        log_path = artifacts / "backtest_demo.log"
        results_out = artifacts / "backtest_results.json"
        cmd = [
            python,
            str(self.module_path / "examples" / "backtest_demo.py"),
            "--exchanges",
            "stock",
            "--start-date",
            proto.date_from or DEFAULT_FROM,
            "--end-date",
            proto.date_to or DEFAULT_TO,
            "--stocks",
            stocks,
            "--stock-count",
            str(len(proto.universe or DEFAULT_UNIVERSE)),
        ]
        env = xai_env(pythonpath_dirs=[self.module_path, self.repo_root])
        env["X_AI_API_KEY"] = key
        env["XAI_API_KEY"] = key
        env["OPENAI_API_KEY"] = key
        env["OPENAI_BASE_URL"] = "https://api.x.ai/v1"
        env["LTB_PARALLELISM"] = str(proto.extra.get("parallelism") or "1")
        proc = run_logged(cmd, cwd=self.module_path, env=env, log_path=log_path)
        models_data = self.module_path / "backend" / "models_data_init.json"
        harvested = harvest_backtest(log_path, models_data)
        if harvested:
            results_out.write_text(json.dumps(harvested, indent=2), encoding="utf-8")
        n_days = harvested.get("n_days")
        n_window = harvested.get("n_days_window")
        ret = harvested.get("return_percentage")
        if proc.returncode != 0 and not harvested:
            status = SuiteStatus.ERROR.value
        elif proc.returncode == 0 and harvested:
            status = SuiteStatus.PASS.value
        else:
            status = SuiteStatus.FAIL.value
        metrics: list[Metric] = []
        if isinstance(n_days, (int, float)):
            metrics.append(Metric(name="n_days", value=float(n_days), source="backtest_demo"))
        if isinstance(harvested.get("n_days_completed"), (int, float)):
            metrics.append(
                Metric(name="n_days_completed", value=float(harvested["n_days_completed"]), source="backtest_demo")
            )
        if isinstance(n_window, (int, float)):
            metrics.append(Metric(name="n_days_window", value=float(n_window), source="backtest_demo"))
        if isinstance(ret, (int, float)):
            metrics.append(Metric(name="return_percentage", value=float(ret), source="backtest_demo"))
            metrics.append(Metric(name="total_return", value=float(ret) / 100.0, source="backtest_demo"))
        arts = [Artifact(kind="log", path=str(log_path), media_type="text/plain")]
        if results_out.is_file():
            arts.append(Artifact(kind="results_json", path=str(results_out), media_type="application/json"))
        if models_data.is_file():
            arts.append(Artifact(kind="models_data", path=str(models_data), media_type="application/json"))
        notes = (
            f"Official examples/backtest_demo.py window {proto.date_from}..{proto.date_to} "
            f"(demo defaults, not a 1-day invention) exchanges=stock model={model} "
            f"returncode={proc.returncode}. Live 50-day dual-market not run in-session. "
            + tail_text(log_path, 20).replace("\n", " | ")[:400]
        )
        return SuiteResult(
            suite_id=SUITE_ID,
            status=status,
            protocol=proto,
            metrics=metrics,
            artifacts=arts,
            traces_path=str(artifacts),
            notes=notes,
            upstream_cli=" ".join(cmd),
        )


def _assert_protocol() -> None:
    _: EnvAdapter = LiveTradeBenchEnvAdapter()  # type: ignore[assignment]


__all__ = ["SUITE_ID", "LiveTradeBenchEnvAdapter", "harvest_existing_run", "apply_continue_patches"]
