"""Official protocol pins for each suite (full protocol, not smoke)."""

from __future__ import annotations

from adapters.base import ProtocolSpec

AMA_CRYPTO = [
    "BTC", "ETH", "ADA", "SOL", "DOT", "LINK", "UNI", "MATIC", "AVAX", "ATOM",
]
AMA_STOCKS = [
    "TSLA", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META",
    "NFLX", "AMD", "INTC", "BMRN", "MRNA",
]
AMA_ASSETS = AMA_CRYPTO + AMA_STOCKS

# In-repo official batch window (modules/ama/testbed/get_action.sh).
AMA_DATE_FROM = "2025-10-22"
AMA_DATE_TO = "2025-12-06"

STOCKBENCH_DATE_FROM = "2025-03-01"
STOCKBENCH_DATE_TO = "2025-06-30"
STOCKBENCH_UNIVERSE = [
    "GS", "MSFT", "HD", "V", "SHW", "CAT", "MCD", "UNH", "AXP", "AMGN",
    "TRV", "CRM", "JPM", "IBM", "HON", "BA", "AMZN", "AAPL", "PG", "JNJ",
]

# FINSABER-2 claimed setups from examples/experiments/manifests (not cherry_pick).
FINSABER_WINDOWS = {
    "2024-01-01_2025-01-01": ("2024-01-01", "2025-01-01"),
    "2025-01-01_2026-01-01": ("2025-01-01", "2026-01-01"),
}
FINSABER_SELECTIONS = {
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

FINSABER_COSTS = {
    "commission_per_share": 0.0049,
    "min_commission": 0.99,
    "max_commission_rate": 0.01,
    "slippage_perc": 0.0005,
    "liquidity_cap_pct": 0.025,
}

DEEPFUND_TICKERS = ["AAPL", "AXP", "BAC", "KO", "CVX"]
# Chronological paper-style window: example log is 2025-04-08; run a trading month.
DEEPFUND_DATE_FROM = "2025-04-01"
DEEPFUND_DATE_TO = "2025-04-30"

# v2 — README / paper defaults. Adapters skip until a full protocol run is wired.
INVESTORBENCH_UNIVERSE = ["HON", "JNJ", "MSFT", "NFLX", "UVV", "BTC-USD", "ETH-USD"]
INVESTORBENCH_DATE_FROM = "2020-10-01"
INVESTORBENCH_DATE_TO = "2021-05-06"
INVESTORBENCH_WARMUP_FROM = "2020-07-01"
INVESTORBENCH_WARMUP_TO = "2020-09-30"

LIVETRADEBENCH_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "JPM", "V", "JNJ", "UNH", "PG",
    "KO", "XOM", "CAT", "WMT", "META", "TSLA", "AMZN",
    "POLYMARKET",
]
LIVETRADEBENCH_N_DAYS = 50

FINMCP_N_SAMPLES = 613
FINMCP_N_MCPS = 65

VALS_N_QUESTIONS_PUBLIC = 50
VALS_N_QUESTIONS_FULL = 537
VALS_TOOLS = [
    "web_search", "edgar_search", "parse_html_page", "retrieve_information",
]

FINSEARCHCOMP_N_QUESTIONS = 635
FINSEARCHCOMP_TASKS = [
    "time_sensitive_data_fetching",
    "simple_historical_lookup",
    "complex_historical_investigation",
]

OPENPM_DATE_FROM = "2026-03-02"
OPENPM_DATE_TO = "2026-05-01"


def ama_protocol() -> ProtocolSpec:
    return ProtocolSpec(
        suite_id="ama.multi_market_live",
        date_from=AMA_DATE_FROM,
        date_to=AMA_DATE_TO,
        universe=list(AMA_ASSETS),
        data_vintage="ama.testbed.paper_trading+yahoo",
        extra={"model": "grok-cli", "agent": "GrokCli"},
    )


def finsaber_protocol() -> ProtocolSpec:
    return ProtocolSpec(
        suite_id="finsaber.long_horizon",
        date_from="2024-01-01",
        date_to="2026-01-01",
        universe=sorted({t for sel in FINSABER_SELECTIONS.values() for w in sel.values() for t in w}),
        data_vintage="FINSABER-2 sp500_2000_2025_parquet price+news",
        costs=dict(FINSABER_COSTS),
        execution_timing="next_open",
        extra={"setups": list(FINSABER_SELECTIONS), "windows": list(FINSABER_WINDOWS)},
    )


def stockbench_protocol() -> ProtocolSpec:
    return ProtocolSpec(
        suite_id="stockbench.daily_sim",
        date_from=STOCKBENCH_DATE_FROM,
        date_to=STOCKBENCH_DATE_TO,
        universe=list(STOCKBENCH_UNIVERSE),
        data_vintage="stockbench.storage.parquet+cache offline_only",
        costs={"commission_bps": 1.0, "slippage_bps": 2.0},
        extra={"llm_profile": "grok", "agent_mode": "dual", "data_mode": "offline_only"},
    )


def fintool_protocol() -> ProtocolSpec:
    return ProtocolSpec(
        suite_id="fintoolbench.tool_compliance",
        date_from=None,
        date_to=None,
        universe=[],
        data_vintage="tools_all_annotated.jsonl + select_data_real_remove_duplicates.jsonl",
        extra={
            "questions": "modules/fintoolbench/data/question/select_data_real_remove_duplicates.jsonl",
            "n_questions": 295,
        },
    )


def deepfund_protocol() -> ProtocolSpec:
    return ProtocolSpec(
        suite_id="deepfund.fund_arena",
        date_from=DEEPFUND_DATE_FROM,
        date_to=DEEPFUND_DATE_TO,
        universe=list(DEEPFUND_TICKERS),
        data_vintage="deepfund local sqlite chronological",
        extra={"config": "grok-buffett", "local_db": True},
    )


def investorbench_protocol() -> ProtocolSpec:
    return ProtocolSpec(
        suite_id="investorbench.decision",
        date_from=INVESTORBENCH_DATE_FROM,
        date_to=INVESTORBENCH_DATE_TO,
        universe=list(INVESTORBENCH_UNIVERSE),
        data_vintage="investorbench data/{hon,jnj,msft,nflx,uvv,btc,eth}.json",
        extra={
            "warmup_from": INVESTORBENCH_WARMUP_FROM,
            "warmup_to": INVESTORBENCH_WARMUP_TO,
            "assets": "equities+crypto",
        },
    )


def livetradebench_protocol() -> ProtocolSpec:
    return ProtocolSpec(
        suite_id="livetradebench.live",
        date_from=None,
        date_to=None,
        universe=list(LIVETRADEBENCH_UNIVERSE),
        data_vintage="live yfinance + polymarket CLOB + news/reddit",
        extra={
            "n_days": LIVETRADEBENCH_N_DAYS,
            "markets": ["us_equities", "polymarket"],
            "license": "PolyForm-Noncommercial-1.0.0",
        },
    )


def finmcp_protocol() -> ProtocolSpec:
    return ProtocolSpec(
        suite_id="finmcp.tool_mcp",
        date_from=None,
        date_to=None,
        universe=[],
        data_vintage="DianJin/FinMCP-Bench 613 samples / 65 MCPs (HF, not vendored)",
        extra={
            "n_samples": FINMCP_N_SAMPLES,
            "n_mcps": FINMCP_N_MCPS,
            "splits": ["single_tool", "multi_tool", "multi_turn"],
            "dataset": "https://huggingface.co/datasets/DianJin/FinMCP-Bench",
        },
    )


def vals_finance_agent_protocol() -> ProtocolSpec:
    return ProtocolSpec(
        suite_id="vals_finance_agent.research",
        date_from=None,
        date_to=None,
        universe=[],
        data_vintage="vals-ai/finance-agent data/public.txt (50 public; 537 gated)",
        extra={
            "n_questions_public": VALS_N_QUESTIONS_PUBLIC,
            "n_questions_full": VALS_N_QUESTIONS_FULL,
            "tools": list(VALS_TOOLS),
            "questions": "modules/vals_finance_agent/data/public.txt",
        },
    )


def finsearchcomp_protocol() -> ProtocolSpec:
    return ProtocolSpec(
        suite_id="finsearchcomp.search",
        date_from=None,
        date_to=None,
        universe=["global", "greater_china"],
        data_vintage="data/finsearchcomp_data.json (635) + akshare split (594)",
        extra={
            "n_questions": FINSEARCHCOMP_N_QUESTIONS,
            "tasks": list(FINSEARCHCOMP_TASKS),
            "questions": "modules/finsearchcomp/data/finsearchcomp_data.json",
        },
    )


def openpm_protocol() -> ProtocolSpec:
    return ProtocolSpec(
        suite_id="openpm.portfolio_pit",
        date_from=OPENPM_DATE_FROM,
        date_to=OPENPM_DATE_TO,
        universe=["SP500_PIT"],
        data_vintage="OpenPM-Bench PIT S&P 500 5m panel + wikipedia_historical membership",
        execution_timing="60min_post_open_then_hold",
        extra={
            "provider": "llm_tiered",
            "rebalance": "once",
            "pit_membership": True,
            "risk": "balanced",
            "dataset": "https://huggingface.co/datasets/aslcai/OpenPM-Bench",
        },
    )
