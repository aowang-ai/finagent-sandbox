"""StockBench — daily portfolio decision quality (exam room).

Upstream: https://github.com/ChenYXxxx/stockbench  ·  arXiv:2510.02209

Full official window: 2025-03-01 .. 2025-06-30, DJIA-20, dual-agent llm_decision.
Grok is the LLM backend via an overlay llm_profile (OpenAI-compatible xAI).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping

from adapters.base import (
    AgentAdapter,
    Artifact,
    EnvAdapter,
    Metric,
    ProtocolSpec,
    SuiteResult,
    SuiteStatus,
    skipped_suite,
)

SUITE_ID = "stockbench.daily_sim"
MODULE_REL = "modules/stockbench"
UPSTREAM_CLI = (
    "python -m stockbench.apps.run_backtest --cfg <overlay> "
    "--start 2025-03-01 --end 2025-06-30 --strategy llm_decision "
    "--llm-profile grok --agent-mode dual --offline"
)
DEFAULT_FROM = "2025-03-01"
DEFAULT_TO = "2025-06-30"
DEFAULT_UNIVERSE = [
    "GS", "MSFT", "HD", "V", "SHW", "CAT", "MCD", "UNH", "AXP", "AMGN",
    "TRV", "CRM", "JPM", "IBM", "HON", "BA", "AMZN", "AAPL", "PG", "JNJ",
]


class StockBenchEnvAdapter:
    suite_id = SUITE_ID
    module_dir = MODULE_REL

    def __init__(self, repo_root: str | Path = ".") -> None:
        self.repo_root = Path(repo_root).resolve()
        self.module_path = self.repo_root / MODULE_REL

    def describe(self) -> Mapping[str, Any]:
        return {
            "suite_id": SUITE_ID,
            "role": "exam_room",
            "layer": "environment.daily_sim",
            "task_suite": "single_name_timing / short_horizon_portfolio",
            "module": str(self.module_path),
            "entry": "python -m stockbench.apps.run_backtest",
            "helper": "overlay config llm_profiles.grok → xAI",
            "artifacts": "storage/reports/backtest/",
            "metrics": ["cum_return", "max_drawdown", "sortino", "sharpe", "trades_count"],
            "pitfalls": [
                "POLYGON/FINNHUB missing — official window uses offline_only parquet+cache",
                "summary_llm disabled on overlay to avoid a second LLM product",
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
            data_vintage=protocol.data_vintage or "stockbench parquet+cache offline_only",
            costs=protocol.costs or {"commission_bps": 1.0, "slippage_bps": 2.0},
            extra=dict(protocol.extra),
        )
        proto.extra.setdefault("llm_profile", "grok")
        proto.extra.setdefault("agent_mode", "dual")
        proto.extra.setdefault("data_mode", "offline_only")
        if not proto.extra.get("execute"):
            return skipped_suite(
                SUITE_ID,
                protocol=proto,
                upstream_cli=UPSTREAM_CLI,
                notes=(
                    "wired: set protocol.extra.execute=true to run the official "
                    "2025-03-01..2025-06-30 DJIA-20 dual-agent backtest with Grok "
                    "as the LLM backend (offline_only)."
                ),
            )
        try:
            return self._run_full(proto)
        except Exception as exc:  # noqa: BLE001
            return SuiteResult(
                suite_id=SUITE_ID,
                status=SuiteStatus.ERROR.value,
                protocol=proto,
                notes=f"StockBench full protocol error: {exc}",
                upstream_cli=UPSTREAM_CLI,
            )

    def _run_full(self, proto: ProtocolSpec) -> SuiteResult:
        from finagent.harness.grok import DEFAULT_MODEL_API, refresh_xai_api_key

        src_cfg = self.module_path / "config.yaml"
        if not src_cfg.is_file():
            return skipped_suite(SUITE_ID, protocol=proto, notes="modules/stockbench/config.yaml missing", upstream_cli=UPSTREAM_CLI)

        artifacts = Path(proto.extra.get("artifacts_dir") or (self.repo_root / "artifacts" / "stockbench"))
        artifacts.mkdir(parents=True, exist_ok=True)
        overlay = artifacts / "config.grok.yaml"
        text = src_cfg.read_text(encoding="utf-8")
        grok_block = (
            "\n  grok:\n"
            "    provider: \"openai\"\n"
            "    base_url: \"https://api.x.ai/v1\"\n"
            f"    model: \"{proto.extra.get('model') or DEFAULT_MODEL_API}\"\n"
            f"    backtest_report_model: \"{proto.extra.get('model') or DEFAULT_MODEL_API}\"\n"
            "    auth_required: true\n"
            "    timeout_sec: 180\n"
            "    retry:\n"
            "      max_retries: 3\n"
            "      backoff_factor: 0.5\n"
        )
        if "  grok:" not in text:
            # Insert under llm_profiles:
            text = text.replace("llm_profiles:\n", "llm_profiles:\n" + grok_block, 1)
        text = text.replace("mode: auto", "mode: offline_only", 1)
        text = text.replace("summary_llm: true", "summary_llm: false", 1)
        overlay.write_text(text, encoding="utf-8")

        python = proto.extra.get("python") or os.environ.get("EVAL_PYTHON") or sys_executable()
        run_id = proto.extra.get("run_id") or "GROK_CLI"
        log_path = artifacts / "run_backtest.log"
        cmd = [
            python, "-m", "stockbench.apps.run_backtest",
            "--cfg", str(overlay),
            "--start", proto.date_from or DEFAULT_FROM,
            "--end", proto.date_to or DEFAULT_TO,
            "--strategy", "llm_decision",
            "--run-id", str(run_id),
            "--llm-profile", "grok",
            "--agent-mode", str(proto.extra.get("agent_mode") or "dual"),
            "--offline",
            "--no-summary-llm",
        ]
        if proto.universe:
            cmd.extend(["--symbols", ",".join(proto.universe)])
        env = os.environ.copy()
        key = refresh_xai_api_key()
        if key:
            env["OPENAI_API_KEY"] = key
            env["XAI_API_KEY"] = key
        env["OPENAI_BASE_URL"] = "https://api.x.ai/v1"
        env["PYTHONPATH"] = (
            str(self.repo_root)
            + os.pathsep
            + str(self.module_path)
            + os.pathsep
            + env.get("PYTHONPATH", "")
        )
        env["TA_DATA_MODE"] = "offline_only"
        env["PYTHONUNBUFFERED"] = "1"
        _patch_stockbench_live_key(self.module_path)
        with log_path.open("w", encoding="utf-8") as logf:
            proc = subprocess.run(
                cmd,
                cwd=str(self.module_path),
                env=env,
                stdout=logf,
                stderr=subprocess.STDOUT,
                check=False,
            )
        reports_root = self.module_path / "storage" / "reports" / "backtest"
        metrics_file = _find_metrics_json(reports_root, run_id)
        harvested = _read_metrics(metrics_file) if metrics_file else {}
        status = SuiteStatus.PASS.value if proc.returncode == 0 and harvested else (
            SuiteStatus.ERROR.value if proc.returncode != 0 else SuiteStatus.FAIL.value
        )
        metrics = [
            Metric(name=k, value=v, source=str(metrics_file) if metrics_file else "stockbench")
            for k, v in harvested.items()
            if isinstance(v, (int, float))
        ]
        notes = (
            (f"SMOKE ({proto.extra.get('smoke_sample')}). " if proto.extra.get("smoke") else "")
            + f"Official StockBench window {proto.date_from}..{proto.date_to} "
            f"universe={len(proto.universe)} dual-agent grok overlay. "
            f"returncode={proc.returncode} metrics={metrics_file}. "
            f"POLYGON/FINNHUB absent; offline_only."
        )
        arts = [Artifact(kind="log", path=str(log_path), media_type="text/plain")]
        if metrics_file:
            arts.append(Artifact(kind="metrics_json", path=str(metrics_file), media_type="application/json"))
        return SuiteResult(
            suite_id=SUITE_ID,
            status=status,
            protocol=proto,
            metrics=metrics,
            artifacts=arts,
            traces_path=str(reports_root),
            notes=notes,
            upstream_cli=" ".join(cmd),
        )


def sys_executable() -> str:
    import sys
    return sys.executable


def _patch_stockbench_live_key(module_path: Path) -> None:
    """Re-read ~/.grok/auth.json on each OpenAI client build so OIDC rotation sticks."""

    path = module_path / "stockbench" / "llm" / "llm_client.py"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if "finance-agent-eval-infra live key" in text:
        return
    needle = (
        "    def _get_openai_client(self, cfg: LLMConfig) -> openai.OpenAI:\n"
        "        \"\"\"Get OpenAI official client\"\"\"\n"
        "        if self._openai_client is None:\n"
        "            self._openai_client = openai.OpenAI(\n"
        "                api_key=self.api_key,\n"
        "                base_url=cfg.base_url,\n"
        "                timeout=cfg.timeout_sec\n"
        "            )\n"
        "        return self._openai_client\n"
    )
    if needle not in text:
        return
    replacement = '''    def _get_openai_client(self, cfg: LLMConfig) -> openai.OpenAI:
        """Get OpenAI official client"""
        # finance-agent-eval-infra live key
        key = self.api_key
        try:
            from finagent.harness.grok import refresh_xai_api_key
            key = refresh_xai_api_key() or key
        except Exception:
            pass
        if self._openai_client is None or getattr(self, "_last_api_key", None) != key:
            self._openai_client = openai.OpenAI(
                api_key=key,
                base_url=cfg.base_url,
                timeout=cfg.timeout_sec
            )
            self._last_api_key = key
            self.api_key = key
        return self._openai_client
'''
    path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")


def _find_metrics_json(root: Path, run_id: str) -> Path | None:
    if not root.is_dir():
        return None
    hits = sorted(root.rglob("metrics.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in hits:
        if run_id in str(path):
            return path
    return hits[0] if hits else None


def _read_metrics(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, Any] = {}
    for key in (
        "cum_return", "max_drawdown", "sortino", "sharpe", "volatility_daily",
        "trades_count", "trades_notional", "sortino_annual", "volatility",
    ):
        if key in data and isinstance(data[key], (int, float)):
            out[key] = float(data[key])
    # nested
    for nest in ("strategy", "metrics", "summary"):
        inner = data.get(nest)
        if isinstance(inner, dict):
            for k, v in inner.items():
                if k not in out and isinstance(v, (int, float)):
                    out[k] = float(v)
    return out


def _assert_protocol() -> None:
    _: EnvAdapter = StockBenchEnvAdapter()  # type: ignore[assignment]


__all__ = ["SUITE_ID", "StockBenchEnvAdapter"]
