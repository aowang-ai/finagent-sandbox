"""Adapter-local smoke shrinks. Official entrypoints stay; samples shrink.

`protocol.extra["smoke"]=true` plus existing knobs (dates, universe,
`--limit`, n_questions). Does not invent a second protocol.
"""

from __future__ import annotations

from adapters.base import ProtocolSpec

# 1–3 questions / one-to-few days / one ticker. Runtime minutes, not overnight.
SMOKE_N_QUESTIONS = 2


def is_smoke(protocol: ProtocolSpec) -> bool:
    return bool((protocol.extra or {}).get("smoke"))


def apply_smoke_protocol(proto: ProtocolSpec) -> ProtocolSpec:
    """Mutate an official ProtocolSpec in place for a tiny honest sample."""

    extra = dict(proto.extra or {})
    extra["smoke"] = True
    sid = proto.suite_id

    if sid == "ama.multi_market_live":
        proto.universe = ["AAPL"]
        proto.date_from = "2025-10-22"
        proto.date_to = "2025-10-22"
        extra["smoke_sample"] = "1 ticker (AAPL) × 1 day 2025-10-22; POST /trading_action/"
    elif sid == "finsaber.long_horizon":
        extra["setups"] = ["random_sp500_5"]
        extra["windows"] = ["2024-01-01_2025-01-01"]
        extra["tickers"] = ["CI"]
        proto.universe = ["CI"]
        proto.date_from = "2024-01-02"
        proto.date_to = "2024-02-29"
        extra["smoke_sample"] = (
            "1 claimed setup random_sp500_5 / 2024-01-01_2025-01-01 ticker CI, "
            "window shrunk to 2024-01-02..2024-02-29; BaseStrategyIso"
        )
    elif sid == "stockbench.daily_sim":
        proto.universe = ["AAPL"]
        proto.date_from = "2025-03-03"
        proto.date_to = "2025-03-04"
        extra["run_id"] = extra.get("run_id") or "GROK_CLI_SMOKE"
        extra["smoke_sample"] = (
            "official run_backtest --symbols AAPL --start 2025-03-03 --end 2025-03-04"
        )
    elif sid == "fintoolbench.tool_compliance":
        extra["n_questions"] = SMOKE_N_QUESTIONS
        extra["smoke_sample"] = f"first {SMOKE_N_QUESTIONS} official JSONL questions + run_relative_eval.py"
    elif sid == "deepfund.fund_arena":
        proto.universe = ["AAPL"]
        proto.date_from = "2025-04-01"
        proto.date_to = "2025-04-01"
        extra["exp_name"] = extra.get("exp_name") or "grok-cli-buffett-smoke"
        extra["smoke_sample"] = "1 ticker AAPL × 1 weekday 2025-04-01; main.py --local-db"
    elif sid == "investorbench.decision":
        extra["smoke_sample"] = (
            "no smaller official smoke than docker devon warmup|test|eval; skip if docker/vLLM/Qdrant missing"
        )
    elif sid == "livetradebench.live":
        proto.universe = ["AAPL"]
        proto.date_from = "2025-10-01"
        proto.date_to = "2025-10-02"
        extra["n_days"] = 2
        extra["smoke_sample"] = (
            "official backtest_demo.py --stocks AAPL --start-date 2025-10-01 --end-date 2025-10-02"
        )
    elif sid == "finmcp.tool_mcp":
        extra["n_samples"] = SMOKE_N_QUESTIONS
        extra["smoke_sample"] = (
            f"n_samples={SMOKE_N_QUESTIONS} if Qieman MCP present; else honest skip"
        )
    elif sid == "vals_finance_agent.research":
        extra["n_questions"] = SMOKE_N_QUESTIONS
        extra["n_questions_public"] = SMOKE_N_QUESTIONS
        extra["max_turns"] = extra.get("max_turns") or 8
        extra["parallelism"] = extra.get("parallelism") or 1
        extra["smoke_sample"] = (
            f"first {SMOKE_N_QUESTIONS} public.txt lines via --question-file; --max-turns 8"
        )
    elif sid == "finsearchcomp.search":
        extra["n_questions"] = SMOKE_N_QUESTIONS
        extra["limit"] = SMOKE_N_QUESTIONS
        extra["smoke_sample"] = f"official chat.py --limit {SMOKE_N_QUESTIONS} then eval.py"
    elif sid == "openpm.portfolio_pit":
        proto.date_from = "2026-03-02"
        proto.date_to = "2026-03-03"
        extra["smoke_sample"] = (
            "official llm_tiered date shrink does not avoid 2.6GiB ndjson load; skip if missing panel or OOM"
        )
    else:
        extra["smoke_sample"] = "smoke=true; no suite-specific shrink table"

    proto.extra = extra
    return proto


def smoke_notes_prefix(proto: ProtocolSpec) -> str:
    if not is_smoke(proto):
        return ""
    sample = proto.extra.get("smoke_sample") or "tiny sample"
    return f"SMOKE ({sample}). "
