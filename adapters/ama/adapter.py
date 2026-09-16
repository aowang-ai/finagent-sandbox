"""AMA (Agent Market Arena) — live / near-live multi-market exam room.

Upstream: https://github.com/The-FinAI/Agent_Market_Arena  ·  arXiv:2510.11695

Native surface: HTTP `POST /trading_action/` (see AmaHttpShim + adapters/ama/http.py).
Full protocol: README asset universe + in-repo testbed window (get_action.sh dates).
"""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

from adapters.base import (
    AgentAdapter,
    Artifact,
    Decision,
    EnvAdapter,
    Metric,
    Observation,
    ProtocolSpec,
    SuiteResult,
    SuiteStatus,
    skipped_suite,
)

SUITE_ID = "ama.multi_market_live"
MODULE_REL = "modules/ama"
UPSTREAM_CLI = "POST /trading_action/ + harvest action/*_trading_decisions.json"

CRYPTO = ["BTC", "ETH", "ADA", "SOL", "DOT", "LINK", "UNI", "MATIC", "AVAX", "ATOM"]
STOCKS = [
    "TSLA", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META",
    "NFLX", "AMD", "INTC", "BMRN", "MRNA",
]
DEFAULT_ASSETS = CRYPTO + STOCKS
DEFAULT_FROM = "2025-10-22"
DEFAULT_TO = "2025-12-06"


class AmaHttpShim:
    """In-process translation of AMA's POST /trading_action/ onto AgentAdapter."""

    def __init__(self, agent: AgentAdapter) -> None:
        self.agent = agent

    def handle(self, payload: dict[str, Any]) -> dict[str, str]:
        symbols = list(payload.get("symbol") or [])
        obs = Observation(
            as_of=str(payload.get("date") or ""),
            symbols=symbols,
            prices=dict(payload.get("price") or {}),
            news=dict(payload.get("news") or {}),
            filings={"10k": payload.get("10k") or {}, "10q": payload.get("10q") or {}},
            raw={
                "history_price": payload.get("history_price") or {},
                "model": payload.get("model"),
                "date": payload.get("date"),
            },
        )
        decision: Decision = self.agent.decide(obs)
        action = (decision.action or "HOLD").upper()
        if action not in {"BUY", "SELL", "HOLD"}:
            action = "HOLD"
        return {"recommended_action": action, "reasoning": decision.reasoning}


class AmaEnvAdapter:
    """Serve decide() at POST /trading_action/ and run the official window."""

    suite_id = SUITE_ID
    module_dir = MODULE_REL

    def __init__(self, repo_root: str | Path = ".") -> None:
        self.repo_root = Path(repo_root).resolve()
        self.module_path = self.repo_root / MODULE_REL

    def describe(self) -> Mapping[str, Any]:
        return {
            "suite_id": SUITE_ID,
            "role": "exam_room",
            "layer": "environment.live_paper",
            "task_suite": "multi_market_live",
            "module": str(self.module_path),
            "entry": "adapters/ama/http.py → POST /trading_action/",
            "analysis": "harvest action JSON + yahoo prices (get_return.py needs news APIs)",
            "agent_contract": "POST /trading_action/ → {recommended_action, reasoning}",
            "assets": {"crypto": CRYPTO, "stocks": STOCKS},
            "metrics": [
                "total_return",
                "ann_return",
                "ann_vol",
                "sharpe_ratio",
                "max_drawdown",
            ],
            "pitfalls": [
                "official get_daily_news.py needs CryptoNews/Finnhub/NewsData keys",
                "get_return.py hardcodes asset/model/agent lists",
                "live news/price drift: pin as-of date in ProtocolSpec",
            ],
            "wired": True,
        }

    def run(self, agent: AgentAdapter, protocol: ProtocolSpec) -> SuiteResult:
        proto = ProtocolSpec(
            suite_id=SUITE_ID,
            date_from=protocol.date_from or DEFAULT_FROM,
            date_to=protocol.date_to or DEFAULT_TO,
            universe=list(protocol.universe or DEFAULT_ASSETS),
            data_vintage=protocol.data_vintage or "ama.testbed + yahoo closes",
            extra=dict(protocol.extra),
        )
        if not proto.extra.get("execute"):
            return skipped_suite(
                SUITE_ID,
                protocol=proto,
                upstream_cli=UPSTREAM_CLI,
                notes=(
                    "wired: set protocol.extra.execute=true to serve Grok at "
                    "POST /trading_action/ and run the full AMA asset×date window. "
                    "Doctor stays skip."
                ),
            )
        try:
            return self._run_full(agent, proto)
        except Exception as exc:  # noqa: BLE001
            return SuiteResult(
                suite_id=SUITE_ID,
                status=SuiteStatus.ERROR.value,
                protocol=proto,
                notes=f"AMA full protocol error: {exc}",
                upstream_cli=UPSTREAM_CLI,
            )

    def _run_full(self, agent: AgentAdapter, proto: ProtocolSpec) -> SuiteResult:
        from adapters.ama.http import AmaHttpServer
        from adapters.ama.yahoo import fetch_daily_bars, is_crypto, price_on_or_before

        artifacts_root = Path(proto.extra.get("artifacts_dir") or (self.repo_root / "artifacts" / "ama"))
        action_dir = artifacts_root / "action"
        data_dir = artifacts_root / "data"
        action_dir.mkdir(parents=True, exist_ok=True)
        data_dir.mkdir(parents=True, exist_ok=True)

        port = int(proto.extra.get("port") or 8765)
        server = AmaHttpServer(agent, port=port)
        url = server.start()
        try:
            self._write_agents_json(url)
            assets = list(proto.universe)
            date_from = proto.date_from or DEFAULT_FROM
            date_to = proto.date_to or DEFAULT_TO
            dates = _date_range(date_from, date_to)
            per_asset_metrics: list[dict[str, Any]] = []
            n_calls = 0
            n_ok = 0
            for asset in assets:
                series = fetch_daily_bars(asset, date_from, date_to)
                paper: dict[str, Any] = {}
                recs: list[dict[str, Any]] = []
                for day in dates:
                    px = price_on_or_before(series, day)
                    paper[day] = {
                        "prices": px,
                        "news": [""],
                        "momentum": "neutral",
                    }
                    if px is None:
                        continue
                    hist = [
                        {"date": d, "price": series[d]}
                        for d in sorted(series) if d < day
                    ][-10:]
                    payload = {
                        "date": day,
                        "price": {asset: px},
                        "news": {asset: "No news available (news vendor keys missing; price-only protocol)."},
                        "symbol": [asset],
                        "model": proto.extra.get("model", "grok-cli"),
                        "history_price": {asset: hist},
                    }
                    n_calls += 1
                    try:
                        result = _post_json(url, payload)
                        n_ok += 1
                    except Exception as exc:  # noqa: BLE001
                        result = {"recommended_action": "HOLD", "reasoning": f"http error: {exc}"}
                    recs.append(
                        {
                            "date": day,
                            "price": px,
                            "recommended_action": result.get("recommended_action", "HOLD"),
                            "news_count": 0,
                            "sentiment": "neutral",
                            "news": payload["news"][asset],
                            "reasoning": result.get("reasoning", ""),
                        }
                    )
                (data_dir / f"paper_trading_{asset}.json").write_text(
                    json.dumps(paper, indent=2), encoding="utf-8"
                )
                decision_path = action_dir / f"GrokCli_{asset}_grok_cli_trading_decisions.json"
                decision_path.write_text(
                    json.dumps(
                        {
                            "status": "success",
                            "start_date": date_from,
                            "end_date": date_to,
                            "model": "grok-cli",
                            "recommendations": recs,
                        },
                        indent=2,
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                metrics = _simulate_returns(recs, series, crypto=is_crypto(asset))
                metrics["asset"] = asset
                per_asset_metrics.append(metrics)
        finally:
            server.stop()

        summary_path = artifacts_root / "ama_metrics.json"
        summary_path.write_text(json.dumps(per_asset_metrics, indent=2), encoding="utf-8")
        agg = _aggregate(per_asset_metrics)
        status = SuiteStatus.PASS.value if n_ok > 0 else SuiteStatus.FAIL.value
        notes = (
            f"Full AMA window {proto.date_from}..{proto.date_to} on {len(proto.universe)} assets. "
            f"HTTP calls {n_ok}/{n_calls}. News vendor keys missing — prices from Yahoo, news empty. "
            f"Server {url}."
        )
        return SuiteResult(
            suite_id=SUITE_ID,
            status=status,
            protocol=proto,
            metrics=[
                Metric(name="n_assets", value=float(len(proto.universe)), source="ama"),
                Metric(name="n_http_ok", value=float(n_ok), source="ama"),
                Metric(name="n_http_calls", value=float(n_calls), source="ama"),
                Metric(name="mean_total_return", value=agg.get("mean_total_return"), unit="pct", higher_is_better=True, source="ama harvest"),
                Metric(name="mean_sharpe_ratio", value=agg.get("mean_sharpe_ratio"), higher_is_better=True, source="ama harvest"),
                Metric(name="mean_max_drawdown", value=agg.get("mean_max_drawdown"), unit="pct", higher_is_better=False, source="ama harvest"),
            ],
            artifacts=[
                Artifact(kind="metrics_json", path=str(summary_path), media_type="application/json"),
                Artifact(kind="decision_json", path=str(action_dir), media_type="application/json"),
            ],
            traces_path=str(action_dir),
            notes=notes,
            upstream_cli=UPSTREAM_CLI,
        )

    def _write_agents_json(self, url: str) -> None:
        cfg_dir = self.module_path / "testbed" / "configs"
        if not cfg_dir.is_dir():
            return
        payload = {"agents": [{"name": "GrokCli", "url": url}]}
        (cfg_dir / "agents.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        (cfg_dir / "agents.grok_cli.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _post_json(url: str, payload: dict[str, Any], timeout: int = 180) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _date_range(start: str, end: str) -> list[str]:
    cur = datetime.strptime(start, "%Y-%m-%d").date()
    last = datetime.strptime(end, "%Y-%m-%d").date()
    out: list[str] = []
    while cur <= last:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def _simulate_returns(
    recs: list[dict[str, Any]],
    series: dict[str, float],
    *,
    crypto: bool,
    initial: float = 100000.0,
    fee: float = 0.0005,
) -> dict[str, float]:
    """Aggressive AMA book: HOLD flattens, BUY long, SELL short. Matches get_return.py aggressive."""

    if not recs:
        return {"total_return": 0.0, "ann_return": 0.0, "ann_vol": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0}
    rec_map = {r["date"]: r for r in recs}
    dates = sorted(rec_map)
    capital = initial
    position = "FLAT"
    entry = 0.0
    path: list[float] = []
    last = capital
    for day in dates:
        px = rec_map[day].get("price")
        if px is None:
            px = series.get(day)
        if px is None:
            path.append(last)
            continue
        px = float(px)
        daily = capital
        if position == "LONG" and entry:
            daily = capital * (px / entry)
        elif position == "SHORT" and entry:
            daily = capital * (1 + (entry - px) / entry)
        action = rec_map[day].get("recommended_action", "HOLD")
        if action == "HOLD":
            if position == "LONG" and entry:
                capital *= (1 + (px - entry) / entry) * (1 - fee)
            elif position == "SHORT" and entry:
                capital *= (1 + (entry - px) / entry) * (1 - fee)
            position, entry = "FLAT", 0.0
            daily = capital
        elif action == "BUY":
            if position == "SHORT" and entry:
                capital *= (1 + (entry - px) / entry) * (1 - fee)
                position, entry = "FLAT", 0.0
            if position == "FLAT":
                position, entry = "LONG", px
                capital *= 1 - fee
                daily = capital
        elif action == "SELL":
            if position == "LONG" and entry:
                capital *= (1 + (px - entry) / entry) * (1 - fee)
                position, entry = "FLAT", 0.0
            if position == "FLAT":
                position, entry = "SHORT", px
                capital *= 1 - fee
                daily = capital
        path.append(daily)
        last = daily
    if not path:
        return {"total_return": 0.0, "ann_return": 0.0, "ann_vol": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0}
    total_return = (path[-1] - path[0]) / path[0] * 100 if path[0] else 0.0
    rets = []
    for a, b in zip(path, path[1:]):
        rets.append((b - a) / a if a else 0.0)
    n = len(rets) or 1
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / n if n else 0.0
    std = math.sqrt(var)
    ann = 365 if crypto else 252
    ann_vol = std * math.sqrt(ann) * 100
    if n > 1 and path[0] > 0:
        ann_return = ((path[-1] / path[0]) ** (ann / n) - 1) * 100
    else:
        ann_return = total_return
    sharpe = (mean / std) * math.sqrt(ann) if std else 0.0
    peak = path[0]
    mdd = 0.0
    for v in path:
        peak = max(peak, v)
        if peak:
            mdd = min(mdd, (v - peak) / peak)
    return {
        "total_return": total_return,
        "ann_return": ann_return,
        "ann_vol": ann_vol,
        "sharpe_ratio": sharpe,
        "max_drawdown": mdd * 100,
    }


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    if not rows:
        return {"mean_total_return": None, "mean_sharpe_ratio": None, "mean_max_drawdown": None}

    def mean(key: str) -> float:
        vals = [float(r[key]) for r in rows if r.get(key) is not None]
        return sum(vals) / len(vals) if vals else 0.0

    return {
        "mean_total_return": mean("total_return"),
        "mean_sharpe_ratio": mean("sharpe_ratio"),
        "mean_max_drawdown": mean("max_drawdown"),
    }


def _assert_protocol() -> None:
    _: EnvAdapter = AmaEnvAdapter()  # type: ignore[assignment]


__all__ = ["SUITE_ID", "AmaEnvAdapter", "AmaHttpShim"]
