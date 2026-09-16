"""Write reports/<runner>_SCORECARD.md + JSON matching ACCEPTANCE_REPORT.schema.json.

Default runner_name is GROK_CLI so the existing Grok run files stay the
canonical Grok output. Pass runner_name for another harness without
overwriting those files.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from adapters.base import (
    REQUIRED_SUITE_IDS_V1,
    AcceptanceReport,
    SuiteResult,
    SuiteStatus,
)

# Per-suite headline metrics (parallel scorecard — no suite is a veto).
SUITE_METRIC_PREFER: dict[str, tuple[str, ...]] = {
    "ama.multi_market_live": ("n_assets", "n_http_ok", "n_http_calls", "mean_total_return", "mean_sharpe_ratio"),
    "finsaber.long_horizon": ("n_ticker_runs", "mean_total_return", "mean_sharpe_ratio", "mean_max_drawdown"),
    "stockbench.daily_sim": ("cum_return", "sharpe", "sortino", "max_drawdown", "trades_count"),
    "fintoolbench.tool_compliance": ("n_questions", "n_with_tool_calls", "tir", "tesr", "soft_score"),
    "deepfund.fund_arena": ("n_days_ok", "n_days_fail", "decision_count", "final_total_assets"),
    "investorbench.decision": ("cumulative_return", "sharpe_ratio", "n_symbols"),
    "livetradebench.live": ("n_days_completed", "n_days", "n_days_window", "total_return", "sharpe", "max_drawdown"),
    "finmcp.tool_mcp": ("n_samples", "tool_f1", "tool_precision", "tool_recall", "emr"),
    "vals_finance_agent.research": ("n_finished", "n_ok", "n_fail", "n_questions", "accuracy"),
    "finsearchcomp.search": ("n_chat", "n_total", "n_questions", "accuracy", "time_sensitive", "simple_historical", "complex_historical"),
    "openpm.portfolio_pit": ("total_return", "sharpe", "max_drawdown", "beat_all_benchmarks"),
}
GENERIC_PREFER = (
    "n_ticker_runs",
    "n_assets",
    "n_http_ok",
    "n_questions",
    "n_days_ok",
    "sharpe_ratio",
    "sharpe",
    "sortino",
    "total_return",
    "cum_return",
    "mean_total_return",
    "soft_score",
    "tir",
    "max_drawdown",
    "decision_count",
)


def write_scorecard(
    report: AcceptanceReport,
    *,
    repo_root: str | Path = ".",
    runner_name: str = "GROK_CLI",
    md_name: str | None = None,
    json_name: str | None = None,
) -> tuple[Path, Path]:
    stem = (runner_name or "GROK_CLI").strip() or "GROK_CLI"
    md_name = md_name or f"{stem}_SCORECARD.md"
    json_name = json_name or f"{stem}_SCORECARD.json"
    root = Path(repo_root).resolve()
    out_dir = root / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / json_name
    md_path = out_dir / md_name
    payload = report.to_dict()
    live = _live_progress(root)
    if live:
        payload.setdefault("notes", "")
        extra = " Live: " + "; ".join(live)
        if extra.strip() not in str(payload.get("notes") or ""):
            payload["notes"] = (str(payload.get("notes") or "").rstrip() + extra).strip()
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report, repo_root=root, runner_name=stem), encoding="utf-8")
    return md_path, json_path


def render_markdown(
    report: AcceptanceReport,
    *,
    repo_root: str | Path | None = None,
    runner_name: str = "GROK_CLI",
) -> str:
    root = Path(repo_root).resolve() if repo_root is not None else Path(".").resolve()
    live = _live_progress(root)
    stale = _stale_error_suites(report, live)
    title = "Grok CLI scorecard" if runner_name == "GROK_CLI" else f"{runner_name} scorecard"
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- generated_at: `{report.generated_at}`")
    lines.append(f"- report_id: `{report.report_id}`")
    lines.append(f"- agent: `{report.agent.agent_id}` version `{report.agent.version or ''}`")
    lines.append(f"- protocol_hash: `{report.protocol_hash}`")
    lines.append(f"- scoring: **parallel scorecard** (kernel=`{report.admission.kernel}`)")
    lines.append(f"- completeness: `{report.admission.decision}` — {report.admission.rationale}")
    if live:
        lines.append("- live: " + "; ".join(f"`{item}`" for item in live))
    if stale:
        lines.append(
            "- stale_errors: " + ", ".join(f"`{s}`" for s in stale)
            + " (on-disk SuiteResult is error; a live run may still be replacing it)"
        )
    lines.append("")
    lines.append("Per-suite pass/fail is **not** a global veto. FINSABER honesty gates stay on that suite.")
    lines.append("")
    lines.append("| Suite | Status | Key metrics | Notes |")
    lines.append("| --- | --- | --- | --- |")
    for suite in report.suites:
        metrics = _metric_summary(suite)
        note = (suite.notes or "").replace("\n", " ")[:180]
        status = suite.status
        if suite.suite_id in stale:
            status = f"{status} (stale)"
        lines.append(f"| `{suite.suite_id}` | **{status}** | {metrics} | {note} |")
    present = {s.suite_id for s in report.suites}
    # Completeness rows: v1 required only. v2 optional suites appear when
    # present on the report; they are not listed as missing (would HOLD
    # the Grok CLI scorecard forever while stubs skip).
    required = list(report.admission.required_suites or REQUIRED_SUITE_IDS_V1)
    missing = [sid for sid in required if sid not in present]
    for sid in missing:
        lines.append(f"| `{sid}` | **missing** | — | not yet in this scorecard |")
    lines.append("")
    for suite in report.suites:
        lines.append(f"## `{suite.suite_id}`")
        lines.append("")
        lines.append(f"- status: `{suite.status}`")
        if suite.suite_id in stale:
            lines.append("- on-disk result is **stale error**; do not treat as the live run's outcome")
        lines.append(f"- protocol_hash: `{suite.protocol_hash}`")
        proto = suite.protocol
        lines.append(
            f"- window: `{proto.date_from}` → `{proto.date_to}` universe={proto.universe[:12]}"
            + ("…" if len(proto.universe) > 12 else "")
        )
        if proto.execution_timing:
            lines.append(f"- execution_timing: `{proto.execution_timing}`")
        if proto.costs:
            lines.append(f"- costs: `{json.dumps(proto.costs, ensure_ascii=False)}`")
        if suite.upstream_cli:
            lines.append(f"- upstream: `{suite.upstream_cli}`")
        if suite.traces_path:
            lines.append(f"- traces: `{suite.traces_path}`")
        if suite.metrics:
            lines.append("")
            lines.append("| Metric | Value | Unit | Source |")
            lines.append("| --- | --- | --- | --- |")
            for m in suite.metrics:
                lines.append(
                    f"| `{m.name}` | {m.value if m.value is not None else ''} | {m.unit or ''} | {m.source or ''} |"
                )
        if suite.gates:
            lines.append("")
            lines.append("| Gate | Required | Passed | Actual | Threshold |")
            lines.append("| --- | --- | --- | --- | --- |")
            for g in suite.gates:
                lines.append(
                    f"| `{g.gate_id}` | {g.required} | **{g.passed}** | {g.actual} | {g.op} {g.threshold} |"
                )
        if suite.artifacts:
            lines.append("")
            lines.append("Artifacts:")
            for a in suite.artifacts:
                lines.append(f"- `{a.kind}`: `{a.path}`")
        if suite.notes:
            lines.append("")
            lines.append(suite.notes)
        lines.append("")
    if live:
        lines.append("## Live runs")
        lines.append("")
        for item in live:
            lines.append(f"- {item}")
        lines.append("")
    if report.notes:
        lines.append("## Notes")
        lines.append("")
        lines.append(report.notes)
        lines.append("")
    return "\n".join(lines) + "\n"


def _metric_summary(suite: SuiteResult) -> str:
    prefer = SUITE_METRIC_PREFER.get(suite.suite_id, GENERIC_PREFER)
    by_name = {m.name: m for m in suite.metrics}
    bits: list[str] = []
    for name in prefer:
        m = by_name.get(name)
        if m and m.value is not None:
            bits.append(f"{name}={m.value}")
        if len(bits) >= 3:
            break
    if not bits and suite.metrics:
        for m in suite.metrics[:3]:
            bits.append(f"{m.name}={m.value}")
    return ", ".join(bits) if bits else "—"


def _disk_ticker_years(root: Path) -> int:
    n = 0
    for path in (root / "artifacts" / "finsaber").glob("*/*/*/*/metrics.json"):
        setup = path.parent.parent.parent.parent.name
        if setup in {"random_sp500_5", "momentum_sp500_5", "lowvol_sp500_5"}:
            n += 1
    return n


def _live_progress(root: Path) -> list[str]:
    items: list[str] = []
    hb = root / "artifacts" / "finsaber" / "heartbeat.json"
    rec = _read_json(hb)
    if rec:
        age = _age_seconds(rec.get("ts"), hb)
        disk_status = (_read_json(root / "artifacts" / "suite_results" / "finsaber.long_horizon.json") or {}).get(
            "status"
        )
        replacing = disk_status in (None, "", "error", "missing")
        if age is not None and (age < 900 or replacing):
            stall = " STALL" if age >= 900 else ""
            disk_done = _disk_ticker_years(root)
            items.append(
                "finsaber.long_horizon {setup}/{window} ticker={ticker} as_of={as_of} "
                "bars={n_bars} hb_done={n_ticker_done}/{n_ticker_total} "
                "disk_done={disk_done}/30 hb_age={age}s{stall}".format(
                    setup=rec.get("setup") or "?",
                    window=rec.get("window") or "?",
                    ticker=rec.get("ticker") or "?",
                    as_of=rec.get("as_of") or "?",
                    n_bars=rec.get("n_bars") or "?",
                    n_ticker_done=rec.get("n_ticker_done") or "?",
                    n_ticker_total=rec.get("n_ticker_total") or "?",
                    disk_done=disk_done,
                    age=age,
                    stall=stall,
                )
            )
    ft = root / "artifacts" / "fintoolbench" / "heartbeat.json"
    rec = _read_json(ft)
    if rec:
        age = _age_seconds(rec.get("ts"), ft)
        if age is not None and age < 3600:
            stall = " STALL" if age >= 900 else ""
            items.append(
                "fintoolbench.tool_compliance {idx}/{n} qid={qid} hb_age={age}s{stall}".format(
                    idx=rec.get("idx") or "?",
                    n=rec.get("n") or "?",
                    qid=rec.get("qid") or "?",
                    age=age,
                    stall=stall,
                )
            )
    return items


def _stale_error_suites(report: AcceptanceReport, live: list[str]) -> list[str]:
    """Error rows that a fresh heartbeat says are still being replaced."""

    live_ids = {item.split()[0] for item in live}
    return [
        suite.suite_id
        for suite in report.suites
        if suite.status == SuiteStatus.ERROR.value and suite.suite_id in live_ids
    ]


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _age_seconds(raw: Any, path: Path) -> int | None:
    text = str(raw or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt: datetime | None = None
    if text:
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            dt = None
    if dt is None:
        try:
            return int(datetime.now(timezone.utc).timestamp() - path.stat().st_mtime)
        except OSError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int((datetime.now(timezone.utc) - dt).total_seconds())
