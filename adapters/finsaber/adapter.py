"""FINSABER — long-horizon, survivorship-aware exam room (not a global veto).

Upstream: https://github.com/waylonli/FINSABER  ·  arXiv:2505.07078  ·  KDD 2026

Native surface: subclass BaseStrategyIso.on_data → framework.buy/sell.
Honesty gates (next_open, costs, not cherry_pick) are **suite metrics**, not
an admission-kernel veto.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from adapters.base import (
    AgentAdapter,
    Artifact,
    EnvAdapter,
    GateResult,
    Metric,
    Observation,
    ProtocolSpec,
    SuiteResult,
    SuiteStatus,
    compare,
    skipped_suite,
)

SUITE_ID = "finsaber.long_horizon"
MODULE_REL = "modules/finsaber"
UPSTREAM_ENTRY = "FINSABER(config).run_iterative_tickers(GrokCliStrategyIso)"

DEFAULT_COSTS = {
    "commission_per_share": 0.0049,
    "min_commission": 0.99,
    "max_commission_rate": 0.01,
    "slippage_perc": 0.0005,
    "liquidity_cap_pct": 0.025,
}

CLAIMED_WINDOWS = {
    "2024-01-01_2025-01-01": ("2024-01-01", "2025-01-01"),
    "2025-01-01_2026-01-01": ("2025-01-01", "2026-01-01"),
}
CLAIMED_SELECTIONS = {
    "random_sp500_5": {
        "2024-01-01_2025-01-01": ["CI", "EIX", "INTC", "MCK", "PNC"],
        "2025-01-01_2026-01-01": ["ATO", "IP", "LOW", "NDSN", "TAP"],
    },
    "momentum_sp500_5": {
        "2024-01-01_2025-01-01": ["INTC", "IT", "NRG", "PANW", "PGR"],
        "2025-01-01_2026-01-01": ["NCLH", "PLTR", "TPL", "UAL", "VST"],
    },
    "lowvol_sp500_5": {
        "2024-01-01_2025-01-01": ["BRK-B", "CB", "KMB", "MRK", "PG"],
        "2025-01-01_2026-01-01": ["CME", "FRT", "K", "MA", "REG"],
    },
}

# Prefer FINSABER_DATA_ROOT. The /workspace/finance-agent-p0 path is a
# documented local fallback default only, not a required layout.
DATA_ROOT_CANDIDATES = (
    os.environ.get("FINSABER_DATA_ROOT"),
    "/workspace/finance-agent-p0/FINSABER/data/sp500_2000_2025_parquet",
    "modules/finsaber/data/sp500_2000_2025_parquet",
)


def evaluate_honesty_gates(
    *,
    execution_timing: str,
    costs: Mapping[str, Any],
    setup_name: str,
) -> list[GateResult]:
    """Suite-level honesty metrics. Not a global admission veto."""

    costs_on = bool(
        float(costs.get("commission_per_share") or 0) > 0
        and float(costs.get("slippage_perc") or 0) > 0
        and float(costs.get("liquidity_cap_pct") or 0) > 0
    )
    universe_kind = "cherry_pick" if "cherry_pick" in (setup_name or "") else "claimed"
    specs = [
        ("execution_timing_next_open", "execution_timing", "eq", "next_open", execution_timing,
         "date-level text must not fill at the same close unless justified"),
        ("costs_enabled", "costs.enabled", "eq", True, costs_on,
         "commission + slippage + liquidity cap must be on for an honest long-horizon exam"),
        ("not_cherry_pick_universe", "universe.kind", "neq", "cherry_pick", universe_kind,
         "cherry_pick_* setups are debug rooms, not the long-horizon protocol"),
    ]
    gates: list[GateResult] = []
    for gate_id, metric, op, threshold, actual, rationale in specs:
        gates.append(
            GateResult(
                gate_id=gate_id,
                metric=metric,
                op=op,
                threshold=threshold,
                actual=actual,
                passed=compare(op, actual, threshold),
                required=False,  # suite metric, not a global veto
                rationale=rationale,
            )
        )
    return gates


# Default unevaluated checklist (doctor / skip path).
HONESTY_GATES = evaluate_honesty_gates(
    execution_timing="next_open",
    costs=DEFAULT_COSTS,
    setup_name="claimed",
)


class FinsaberEnvAdapter:
    """Long-horizon exam room. Honesty gates are suite metrics, not a kernel."""

    suite_id = SUITE_ID
    module_dir = MODULE_REL

    def __init__(self, repo_root: str | Path = ".") -> None:
        self.repo_root = Path(repo_root).resolve()
        self.module_path = self.repo_root / MODULE_REL

    def describe(self) -> Mapping[str, Any]:
        return {
            "suite_id": SUITE_ID,
            "role": "exam_room",
            "layer": "environment.historical_backtest",
            "task_suite": "long_horizon_anti_bias",
            "module": str(self.module_path),
            "entry": UPSTREAM_ENTRY,
            "package": "PYTHONPATH=modules/finsaber",
            "dataset": "FINSABER_DATA_ROOT or sibling finance-agent-p0 parquet",
            "metrics": [
                "final_value",
                "total_return",
                "annual_return",
                "sharpe_ratio",
                "max_drawdown",
                "total_commission",
                "total_slippage",
            ],
            "honesty_gates": [g.gate_id for g in HONESTY_GATES],
            "honesty_policy": "suite metrics; do not veto other suites",
            "pitfalls": [
                "filings partitions may be absent; price+news still official FINSABER-2 modalities",
                "LLM-per-bar on 2024-2026 claimed setups is the overnight volume path",
            ],
            "wired": True,
        }

    def run(self, agent: AgentAdapter, protocol: ProtocolSpec) -> SuiteResult:
        extra = dict(protocol.extra)
        extra.setdefault("setup_name", "claimed_sp500_5")
        proto = ProtocolSpec(
            suite_id=SUITE_ID,
            date_from=protocol.date_from or "2024-01-01",
            date_to=protocol.date_to or "2026-01-01",
            universe=list(protocol.universe),
            data_vintage=protocol.data_vintage or "FINSABER-2 parquet price+news",
            costs=protocol.costs or dict(DEFAULT_COSTS),
            execution_timing=protocol.execution_timing or "next_open",
            extra=extra,
        )
        gates = evaluate_honesty_gates(
            execution_timing=proto.execution_timing or "",
            costs=proto.costs,
            setup_name=str(extra.get("setup_name") or ""),
        )
        if not extra.get("execute"):
            result = skipped_suite(
                SUITE_ID,
                protocol=proto,
                upstream_cli=UPSTREAM_ENTRY,
                notes=(
                    "wired: set protocol.extra.execute=true to wrap Grok as "
                    "BaseStrategyIso.on_data and run claimed FINSABER-2 setups "
                    "(random/momentum/lowvol, not cherry_pick). Honesty gates are "
                    "suite metrics, not a global veto."
                ),
            )
            result.gates = gates
            return result
        try:
            result = self._run_full(agent, proto)
            result.gates = gates
            return result
        except Exception as exc:  # noqa: BLE001
            import traceback

            artifacts = Path(extra.get("artifacts_dir") or (self.repo_root / "artifacts" / "finsaber"))
            artifacts.mkdir(parents=True, exist_ok=True)
            err_path = artifacts / "error.txt"
            err_path.write_text(traceback.format_exc(), encoding="utf-8")
            return SuiteResult(
                suite_id=SUITE_ID,
                status=SuiteStatus.ERROR.value,
                protocol=proto,
                gates=gates,
                artifacts=[Artifact(kind="log", path=str(err_path), media_type="text/plain")],
                notes=f"FINSABER full protocol error: {exc}",
                upstream_cli=UPSTREAM_ENTRY,
            )

    def _run_full(self, agent: AgentAdapter, proto: ProtocolSpec) -> SuiteResult:
        data_root = _resolve_data_root(self.repo_root, proto.extra.get("data_root"))
        if data_root is None:
            return SuiteResult(
                suite_id=SUITE_ID,
                status=SuiteStatus.SKIP.value,
                protocol=proto,
                notes=(
                    "FINSABER-2 parquet not found. Set FINSABER_DATA_ROOT. "
                    "Looked at sibling finance-agent-p0 and modules/finsaber/data."
                ),
                upstream_cli=UPSTREAM_ENTRY,
            )

        module_root = str(self.module_path)
        if module_root not in sys.path:
            sys.path.insert(0, module_root)

        from backtest.data_util.finsaber_parquet_dataset import FinsaberParquetDataset
        from backtest.finsaber import FINSABER
        from backtest.strategy.timing_llm.base_strategy_iso import BaseStrategyIso

        artifacts = Path(proto.extra.get("artifacts_dir") or (self.repo_root / "artifacts" / "finsaber"))
        artifacts.mkdir(parents=True, exist_ok=True)

        strategy_cls = _make_strategy_class(agent, BaseStrategyIso)
        setups = proto.extra.get("setups") or list(CLAIMED_SELECTIONS)
        windows = proto.extra.get("windows") or list(CLAIMED_WINDOWS)
        ticker_filter = {str(t) for t in (proto.extra.get("tickers") or []) if t}
        smoke = bool(proto.extra.get("smoke"))
        all_metrics: dict[str, Any] = {}
        tickers_used: list[str] = []
        hb_path = artifacts / "heartbeat.json"
        progress_path = artifacts / "progress.jsonl"
        strategy_cls._hb_path = hb_path  # type: ignore[attr-defined]
        n_done = 0

        def _tickers_for(setup: str, window_key: str) -> list[str]:
            sel_map = CLAIMED_SELECTIONS.get(str(setup)) or {}
            names = list(sel_map.get(window_key) or [])
            if ticker_filter:
                filtered = [t for t in names if t in ticker_filter]
                if filtered:
                    return filtered
            return names

        n_total = sum(
            len(_tickers_for(str(s), w))
            for s in setups
            if str(s) in CLAIMED_SELECTIONS
            for w in windows
            if w in CLAIMED_SELECTIONS[str(s)]
        )

        for setup in setups:
            sel = CLAIMED_SELECTIONS.get(str(setup))
            if not sel:
                continue
            for window_key in windows:
                if window_key not in CLAIMED_WINDOWS or window_key not in sel:
                    continue
                date_from, date_to = CLAIMED_WINDOWS[window_key]
                if smoke:
                    date_from = proto.date_from or date_from
                    date_to = proto.date_to or date_to
                tickers = _tickers_for(str(setup), window_key)
                tickers_used.extend(tickers)
                strategy_cls._hb_meta = {  # type: ignore[attr-defined]
                    "setup": str(setup),
                    "window": window_key,
                    "tickers": tickers,
                    "n_ticker_done": n_done,
                    "n_ticker_total": n_total,
                }
                _write_heartbeat(
                    hb_path,
                    setup=str(setup),
                    window=window_key,
                    ticker=tickers[0] if tickers else None,
                    phase="window_start",
                    n_ticker_done=n_done,
                    n_ticker_total=n_total,
                )
                print(
                    f"[finsaber] start {setup}/{window_key} tickers={tickers} "
                    f"done={n_done}/{n_total}",
                    flush=True,
                )
                loader = FinsaberParquetDataset(
                    data_root,
                    start_date=date_from,
                    end_date=date_to,
                    tickers=tickers,
                    modalities=("price", "news"),
                )
                out_dir = artifacts / str(setup) / window_key
                out_dir.mkdir(parents=True, exist_ok=True)
                config = {
                    "tickers": tickers,
                    "date_from": date_from,
                    "date_to": date_to,
                    "cash": 100000.0,
                    "risk_free_rate": 0.03,
                    "commission_per_share": proto.costs.get("commission_per_share", 0.0049),
                    "min_commission": proto.costs.get("min_commission", 0.99),
                    "max_commission_rate": proto.costs.get("max_commission_rate", 0.01),
                    "execution_timing": proto.execution_timing or "next_open",
                    "slippage_perc": proto.costs.get("slippage_perc", 0.0005),
                    "liquidity_cap_pct": proto.costs.get("liquidity_cap_pct", 0.025),
                    "silence": True,
                    "setup_name": str(setup),
                    "save_results": True,
                    "result_output_dir": str(out_dir),
                    "data_loader": loader,
                    "checkpoint_results": True,
                    "resume_from_checkpoint": not smoke,
                }
                engine = FINSABER(config)
                # Upstream auto_resolve_params does strat_params.items() with no None-guard.
                metrics = engine.run_iterative_tickers(
                    strategy_cls,
                    strat_params={"symbol": "$symbol", "tickers": "$tickers"},
                    tickers=tickers,
                    delist_check=True,
                )
                all_metrics[f"{setup}/{window_key}"] = metrics
                n_done += len(tickers)
                rec = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "setup": str(setup),
                    "window": window_key,
                    "tickers": tickers,
                    "n_ticker_done": n_done,
                    "n_ticker_total": n_total,
                    "checkpoint_dir": str(out_dir / "checkpoints"),
                }
                with progress_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, default=str) + "\n")
                _write_heartbeat(
                    hb_path,
                    setup=str(setup),
                    window=window_key,
                    phase="window_done",
                    n_ticker_done=n_done,
                    n_ticker_total=n_total,
                )
                print(
                    f"[finsaber] done {setup}/{window_key} tickers={list((metrics or {}).keys()) if isinstance(metrics, dict) else metrics} "
                    f"done={n_done}/{n_total}",
                    flush=True,
                )

        summary_path = artifacts / "finsaber_metrics.json"
        summary_path.write_text(json.dumps(all_metrics, indent=2, default=str), encoding="utf-8")
        flat = _flatten_metrics(all_metrics)
        proto.universe = sorted(set(tickers_used) or proto.universe)
        n_ticker_runs = int(flat.get("n_ticker_runs") or 0)
        status = SuiteStatus.PASS.value if n_ticker_runs else SuiteStatus.FAIL.value
        return SuiteResult(
            suite_id=SUITE_ID,
            status=status,
            protocol=proto,
            metrics=[
                Metric(name="n_ticker_runs", value=float(n_ticker_runs), source="finsaber"),
                Metric(name="mean_total_return", value=flat.get("mean_total_return"), higher_is_better=True, source="finsaber"),
                Metric(name="mean_sharpe_ratio", value=flat.get("mean_sharpe_ratio"), higher_is_better=True, source="finsaber"),
                Metric(name="mean_max_drawdown", value=flat.get("mean_max_drawdown"), higher_is_better=False, source="finsaber"),
                Metric(name="mean_total_commission", value=flat.get("mean_total_commission"), source="finsaber"),
            ],
            artifacts=[
                Artifact(kind="metrics_json", path=str(summary_path), media_type="application/json"),
                Artifact(kind="run_config", path=str(artifacts), media_type="application/json"),
                Artifact(kind="log", path=str(hb_path), media_type="application/json"),
            ],
            traces_path=str(artifacts),
            notes=(
                (f"SMOKE ({proto.extra.get('smoke_sample')}). " if smoke else "")
                + f"Claimed FINSABER-2 setups {setups} windows {windows} via BaseStrategyIso. "
                f"data_root={data_root}. Honesty gates recorded on this suite only."
            ),
            upstream_cli=UPSTREAM_ENTRY,
        )


def _write_heartbeat(path: Path | None, **kwargs: Any) -> None:
    if path is None:
        return
    rec = {"ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), **kwargs}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, default=str), encoding="utf-8")
    except OSError:
        pass


def _make_strategy_class(agent: AgentAdapter, base_cls: type) -> type:
    class GrokCliStrategyIso(base_cls):  # type: ignore[misc, valid-type]
        def __init__(self, **kwargs: Any) -> None:
            super().__init__()
            self._agent = agent
            self._ticker = kwargs.get("symbol") or kwargs.get("ticker")
            if isinstance(kwargs.get("tickers"), list) and kwargs["tickers"]:
                self._ticker = self._ticker or kwargs["tickers"][0]
            self._n_bars = 0
            try:
                self.disable_logger()
            except Exception:
                pass

        def on_data(self, date, today_data, framework):
            ticker = self._ticker
            if not ticker:
                return None
            day = date.isoformat() if hasattr(date, "isoformat") else str(date)
            self._n_bars += 1
            if self._n_bars == 1 or self._n_bars % 10 == 0:
                meta = getattr(type(self), "_hb_meta", {}) or {}
                _write_heartbeat(
                    getattr(type(self), "_hb_path", None),
                    setup=meta.get("setup"),
                    window=meta.get("window"),
                    ticker=ticker,
                    as_of=day,
                    n_bars=self._n_bars,
                    phase="on_data",
                    n_ticker_done=meta.get("n_ticker_done"),
                    n_ticker_total=meta.get("n_ticker_total"),
                )
                if self._n_bars == 1:
                    print(f"[finsaber] ticker {ticker} {meta.get('setup')}/{meta.get('window')} start {day}", flush=True)
            price_map = {}
            news_map = {}
            filings: dict[str, Any] = {}
            data = today_data if isinstance(today_data, dict) else {}
            raw_price = (data.get("price") or {}).get(ticker) if isinstance(data.get("price"), dict) else None
            if isinstance(raw_price, dict):
                price_map[ticker] = raw_price.get("adjusted_close") or raw_price.get("close")
            elif raw_price is not None:
                price_map[ticker] = raw_price
            news_blob = data.get("news") if isinstance(data.get("news"), dict) else {}
            news = news_blob.get(ticker) if news_blob else None
            if news:
                news_map[ticker] = news if isinstance(news, str) else str(news)[:4000]
            fk_blob = data.get("filing_k") if isinstance(data.get("filing_k"), dict) else {}
            fq_blob = data.get("filing_q") if isinstance(data.get("filing_q"), dict) else {}
            fk = fk_blob.get(ticker) if fk_blob else None
            fq = fq_blob.get(ticker) if fq_blob else None
            if fk:
                filings["10k"] = str(fk)[:3000]
            if fq:
                filings["10q"] = str(fq)[:3000]
            cash = getattr(framework, "cash", None)
            portfolio = {"cash": cash, "positions": getattr(framework, "portfolio", {})}
            obs = Observation(
                as_of=day,
                symbols=[ticker],
                prices=price_map,
                news=news_map,
                filings=filings,
                portfolio=portfolio,
                raw={"date": day, "ticker": ticker},
            )
            decision = self._agent.decide(obs)
            px = price_map.get(ticker)
            if px is None:
                return None
            try:
                px_f = float(px)
            except (TypeError, ValueError):
                return None
            action = (decision.action or "HOLD").upper()
            if action == "BUY":
                framework.buy(date, ticker, px_f, -1)
            elif action == "SELL":
                held = 0
                pos = getattr(framework, "portfolio", {}).get(ticker) or {}
                held = int(pos.get("quantity") or 0)
                if held:
                    framework.sell(date, ticker, px_f, held)
            return None

    GrokCliStrategyIso.__name__ = "GrokCliStrategyIso"
    return GrokCliStrategyIso


def _resolve_data_root(repo_root: Path, override: Any) -> Path | None:
    candidates = [override, *DATA_ROOT_CANDIDATES]
    for raw in candidates:
        if not raw:
            continue
        path = Path(str(raw))
        if not path.is_absolute():
            path = repo_root / path
        if (path / "price_daily").is_dir():
            return path
    return None


def _flatten_metrics(all_metrics: dict[str, Any]) -> dict[str, float | None]:
    rows: list[dict[str, Any]] = []
    for block in all_metrics.values():
        if not isinstance(block, dict):
            continue
        for ticker_metrics in block.values():
            if isinstance(ticker_metrics, dict) and "total_return" in ticker_metrics:
                rows.append(ticker_metrics)
            elif isinstance(ticker_metrics, dict):
                # window -> ticker -> metrics
                for inner in ticker_metrics.values():
                    if isinstance(inner, dict) and "total_return" in inner:
                        rows.append(inner)

    def mean(key: str) -> float | None:
        vals = []
        for r in rows:
            v = r.get(key)
            if isinstance(v, (int, float)):
                vals.append(float(v))
        return sum(vals) / len(vals) if vals else None

    return {
        "n_ticker_runs": float(len(rows)),
        "mean_total_return": mean("total_return"),
        "mean_sharpe_ratio": mean("sharpe_ratio"),
        "mean_max_drawdown": mean("max_drawdown"),
        "mean_total_commission": mean("total_commission"),
    }


def _assert_protocol() -> None:
    _: EnvAdapter = FinsaberEnvAdapter()  # type: ignore[assignment]


__all__ = ["SUITE_ID", "HONESTY_GATES", "FinsaberEnvAdapter", "evaluate_honesty_gates"]
