"""DeepFund — fund/portfolio arena + decision traces (exam room).

Upstream: https://github.com/HKUSTDial/DeepFund  ·  arXiv:2505.11065  ·  NeurIPS'25

Prefer harvest: chronological `main.py --local-db` with Grok as the YAML LLM.
PM inject is only used if harvest cannot bind Grok as the harness LLM.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
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

SUITE_ID = "deepfund.fund_arena"
MODULE_REL = "modules/deepfund"
UPSTREAM_CLI = (
    "python modules/deepfund/src/main.py --config {config} "
    "--trading-date {date} --local-db"
)
DEFAULT_FROM = "2025-04-01"
DEFAULT_TO = "2025-04-30"
DEFAULT_TICKERS = ["AAPL", "AXP", "BAC", "KO", "CVX"]


class DeepFundEnvAdapter:
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
            "task_suite": "fund_portfolio",
            "module": str(self.module_path),
            "entry": "python src/main.py --config grok-buffett.yaml --trading-date YYYY-MM-DD --local-db",
            "db_setup": "python src/database/sqlite_setup.py",
            "tables": ["config", "portfolio", "decision", "signal"],
            "metrics": ["portfolio.total_assets", "decision_count", "signal_count"],
            "pitfalls": [
                "trading-date must be chronological per exp_name",
                "fundamental/macro may ignore historical as-of",
                "Supabase default — we force --local-db",
                "ALPHA_VANTAGE_API_KEY often absent — prices fall back to yfinance",
                "parallel analysts that return full FundState raise InvalidUpdateError on exp_name",
            ],
            "wired": True,
        }

    def run(self, agent: AgentAdapter, protocol: ProtocolSpec) -> SuiteResult:
        _ = agent
        proto = ProtocolSpec(
            suite_id=SUITE_ID,
            date_from=protocol.date_from or DEFAULT_FROM,
            date_to=protocol.date_to or DEFAULT_TO,
            universe=list(protocol.universe or DEFAULT_TICKERS),
            data_vintage=protocol.data_vintage or "deepfund local sqlite",
            extra=dict(protocol.extra),
        )
        if not proto.extra.get("execute"):
            return skipped_suite(
                SUITE_ID,
                protocol=proto,
                upstream_cli=UPSTREAM_CLI.format(
                    config="artifacts/deepfund/grok-buffett.yaml",
                    date=proto.date_from,
                ),
                notes=(
                    "wired: set protocol.extra.execute=true to run chronological "
                    "main.py --local-db with Grok as the YAML LLM and harvest SQLite traces."
                ),
            )
        try:
            return self._run_full(proto)
        except Exception as exc:  # noqa: BLE001
            return SuiteResult(
                suite_id=SUITE_ID,
                status=SuiteStatus.ERROR.value,
                protocol=proto,
                notes=f"DeepFund full protocol error: {exc}",
                upstream_cli=UPSTREAM_CLI,
            )

    def _run_full(self, proto: ProtocolSpec) -> SuiteResult:
        from finagent.harness.grok import DEFAULT_MODEL_API, refresh_xai_api_key

        src = self.module_path / "src"
        artifacts = Path(proto.extra.get("artifacts_dir") or (self.repo_root / "artifacts" / "deepfund"))
        artifacts.mkdir(parents=True, exist_ok=True)
        yaml_path = artifacts / "grok-buffett.yaml"
        yaml_path.write_text(
            _grok_yaml(
                exp_name=str(proto.extra.get("exp_name") or "grok-cli-buffett"),
                tickers=proto.universe,
                model=str(proto.extra.get("model") or DEFAULT_MODEL_API),
            ),
            encoding="utf-8",
        )
        python = proto.extra.get("python") or os.environ.get("EVAL_PYTHON") or sys.executable
        env = os.environ.copy()
        key = refresh_xai_api_key(force=True)
        if key:
            env["OPENAI_API_KEY"] = key
            env["XAI_API_KEY"] = key
        # ChatOpenAI/OpenAI SDK pick this up when YAML provider is OpenAI.
        env["OPENAI_BASE_URL"] = "https://api.x.ai/v1"
        env["OPENAI_API_BASE"] = "https://api.x.ai/v1"
        db_path = artifacts / "deepfund.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # Previous error runs leave leftover rows; official protocol is a clean month.
        if db_path.is_file():
            db_path.unlink()
        env["DB_PATH"] = str(db_path)
        env["PYTHONPATH"] = (
            str(self.repo_root) + os.pathsep + str(src) + os.pathsep + env.get("PYTHONPATH", "")
        )
        env["PYTHONUNBUFFERED"] = "1"
        _ensure_openai_compatible_provider(src, env["OPENAI_BASE_URL"])
        _patch_deepfund_live_key(src)
        _ensure_sqlite_db_path(src)
        _patch_yfinance_price_methods(src)
        _patch_router_price_fallback(src)
        _patch_langgraph_concurrent_state(src)

        setup = subprocess.run(
            [python, "database/sqlite_setup.py"],
            cwd=str(src),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        log_path = artifacts / "deepfund.log"
        with log_path.open("w", encoding="utf-8") as logf:
            logf.write(setup.stdout or "")
            logf.write(setup.stderr or "")
            n_ok = 0
            n_fail = 0
            if setup.returncode != 0:
                n_fail = 1
                logf.write(
                    f"\nsqlite_setup rc={setup.returncode}; aborting chronological loop\n"
                )
            else:
                for day in _weekdays(proto.date_from or DEFAULT_FROM, proto.date_to or DEFAULT_TO):
                    proc = subprocess.run(
                        [
                            python, "main.py",
                            "--config", str(yaml_path),
                            "--trading-date", day,
                            "--local-db",
                        ],
                        cwd=str(src),
                        env=env,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    logf.write(f"\n=== {day} rc={proc.returncode} ===\n")
                    logf.write(proc.stdout or "")
                    logf.write(proc.stderr or "")
                    if proc.returncode == 0:
                        n_ok += 1
                        continue
                    n_fail += 1
                    err = f"{proc.stderr or ''}{proc.stdout or ''}"
                    if "403" in err or "401" in err:
                        key = refresh_xai_api_key(force=True)
                        if key:
                            env["OPENAI_API_KEY"] = key
                            env["XAI_API_KEY"] = key
                    if "chronological" in err.lower():
                        break
                    if n_ok == 0 and _is_irrecoverable_setup_error(err):
                        logf.write("\nirrecoverable setup error; aborting chronological loop\n")
                        break

        configured_db = Path(env["DB_PATH"]) if env.get("DB_PATH") else None
        db_path = configured_db if configured_db and configured_db.is_file() else None
        harvested = _harvest_sqlite(db_path) if db_path else {}
        status = SuiteStatus.PASS.value if n_ok else (
            SuiteStatus.ERROR.value if n_fail else SuiteStatus.FAIL.value
        )
        metrics = [
            Metric(name="n_days_ok", value=float(n_ok), source="deepfund"),
            Metric(name="n_days_fail", value=float(n_fail), source="deepfund"),
            Metric(name="decision_count", value=float(harvested.get("decision_count") or 0), source="sqlite"),
            Metric(name="signal_count", value=float(harvested.get("signal_count") or 0), source="sqlite"),
            Metric(
                name="final_total_assets",
                value=harvested.get("final_total_assets"),
                source="sqlite.portfolio",
            ),
        ]
        harvest_path = artifacts / "harvest.json"
        harvest_path.write_text(json.dumps(harvested, indent=2, default=str), encoding="utf-8")
        av = "present" if os.environ.get("ALPHA_VANTAGE_API_KEY") else "absent (yfinance price fallback)"
        notes = (
            f"Chronological DeepFund --local-db {proto.date_from}..{proto.date_to} "
            f"with OpenAI-compatible Grok YAML. days_ok={n_ok} fail={n_fail}. "
            f"db={db_path}. Supabase not used. ALPHA_VANTAGE_API_KEY={av}."
        )
        arts = [
            Artifact(kind="log", path=str(log_path), media_type="text/plain"),
            Artifact(kind="metrics_json", path=str(harvest_path), media_type="application/json"),
        ]
        if db_path:
            arts.append(Artifact(kind="decision_db", path=str(db_path), media_type="application/vnd.sqlite3"))
        return SuiteResult(
            suite_id=SUITE_ID,
            status=status,
            protocol=proto,
            metrics=metrics,
            artifacts=arts,
            traces_path=str(db_path) if db_path else str(log_path),
            notes=notes,
            upstream_cli=UPSTREAM_CLI.format(config=str(yaml_path), date=proto.date_from),
        )


def _ensure_openai_compatible_provider(src: Path, base_url: str) -> None:
    """Point DeepFund's OpenAI provider at an OpenAI-compatible base URL (xAI).

    Upstream LLMConfig(**yaml['llm']) rejects unknown keys, so base_url cannot
    live in the experiment YAML. Patch provider.py in the cloned module (gitignored).
    """

    path = src / "llm" / "provider.py"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    needle = (
        "            Provider.OPENAI: ModelConfig(\n"
        "                model_class=ChatOpenAI,\n"
        "                env_key=\"OPENAI_API_KEY\",\n"
        "            ),"
    )
    if "env_key=\"OPENAI_API_KEY\",\n                base_url=" in text:
        return
    if needle not in text:
        return
    if "import os" not in text.split("class Provider", 1)[0]:
        text = text.replace("from typing import Optional, Type", "import os\nfrom typing import Optional, Type", 1)
    replacement = (
        "            Provider.OPENAI: ModelConfig(\n"
        "                model_class=ChatOpenAI,\n"
        "                env_key=\"OPENAI_API_KEY\",\n"
        f"                base_url=os.getenv(\"OPENAI_BASE_URL\") or os.getenv(\"OPENAI_API_BASE\") or \"{base_url}\",\n"
        "            ),"
    )
    path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")


def _patch_deepfund_live_key(src: Path) -> None:
    path = src / "llm" / "inference.py"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if "finance-agent-eval-infra live key" in text:
        return
    needle = "        api_key = os.getenv(model_config.env_key)\n"
    if needle not in text:
        return
    replacement = (
        "        api_key = os.getenv(model_config.env_key)\n"
        "        # finance-agent-eval-infra live key\n"
        "        try:\n"
        "            from finagent.harness.grok import refresh_xai_api_key\n"
        "            api_key = refresh_xai_api_key() or api_key\n"
        "        except Exception:\n"
        "            pass\n"
    )
    path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")


def _ensure_sqlite_db_path(src: Path) -> None:
    """Keep DB_PATH usable when the env var is unset (upstream load_dotenv can leave None)."""

    path = src / "database" / "sqlite_setup.py"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if 'os.getenv("DB_PATH") or _DEFAULT_DB' in text:
        return
    old = 'DB_PATH = os.getenv("DB_PATH")\n'
    if old not in text:
        return
    replacement = (
        '_DEFAULT_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "example", "deepfund.db"))\n'
        'DB_PATH = os.getenv("DB_PATH") or _DEFAULT_DB\n'
    )
    path.write_text(text.replace(old, replacement, 1), encoding="utf-8")


def _patch_yfinance_price_methods(src: Path) -> None:
    """Upstream YFinanceAPI only implements news. Add as-of daily prices."""

    path = src / "apis" / "yfinance" / "api.py"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if "finance-agent-eval-infra yfinance prices" in text:
        return
    extra = '''

    # finance-agent-eval-infra yfinance prices
    def get_daily_candles_df(self, ticker: str, trading_date):
        import pandas as pd
        from datetime import timedelta
        if hasattr(trading_date, "strftime"):
            end = trading_date
        else:
            end = datetime.strptime(str(trading_date)[:10], "%Y-%m-%d")
        start = end - timedelta(days=400)
        hist = yf.Ticker(str(ticker)).history(
            start=start.strftime("%Y-%m-%d"),
            end=(end + timedelta(days=1)).strftime("%Y-%m-%d"),
            auto_adjust=True,
        )
        if hist is None or hist.empty:
            return pd.DataFrame()
        hist = hist.rename(columns={str(c): str(c).lower() for c in hist.columns})
        return hist

    def get_last_close_price(self, ticker: str, trading_date):
        df = self.get_daily_candles_df(ticker, trading_date)
        if df is None or df.empty or "close" not in df.columns:
            return None
        return float(df["close"].iloc[-1])
'''
    path.write_text(text + extra, encoding="utf-8")


def _patch_router_price_fallback(src: Path) -> None:
    """Fall back to yfinance when Alpha Vantage is missing or errors."""

    path = src / "apis" / "router.py"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if "finance-agent-eval-infra price fallback" in text:
        return
    old = '''    def get_us_stock_daily_candles_df(self, ticker, trading_date):
        return self.api.get_daily_candles_df(ticker, trading_date)
    
    def get_us_stock_last_close_price(self, ticker, trading_date):
        """Get the last close price for a ticker"""
        return self.api.get_last_close_price(ticker, trading_date)
'''
    new = '''    def get_us_stock_daily_candles_df(self, ticker, trading_date):
        # finance-agent-eval-infra price fallback
        try:
            df = self.api.get_daily_candles_df(ticker, trading_date)
            if df is not None and getattr(df, "empty", False) is False:
                return df
        except Exception:
            df = None
        if not isinstance(self.api, YFinanceAPI):
            return YFinanceAPI().get_daily_candles_df(ticker, trading_date)
        return df

    def get_us_stock_last_close_price(self, ticker, trading_date):
        """Get the last close price for a ticker"""
        # finance-agent-eval-infra price fallback
        price = None
        try:
            price = self.api.get_last_close_price(ticker, trading_date)
        except Exception:
            price = None
        if price is None and not isinstance(self.api, YFinanceAPI):
            price = YFinanceAPI().get_last_close_price(ticker, trading_date)
        return price
'''
    if old not in text:
        return
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _patch_langgraph_concurrent_state(src: Path) -> None:
    """Fix LangGraph InvalidUpdateError on parallel analyst fan-in.

    Upstream analysts `return state` on fetch errors. All four Buffett analysts
    start from START in one step, so echoing LastValue keys (`exp_name`, ticker,
    portfolio, …) raises:

        InvalidUpdateError: At key 'exp_name': Can receive only one value per step

    Two layers (cloned module is gitignored; this re-applies every execute):
    1. Last-write-wins Annotated reducers on FundState LastValue channels.
    2. Error paths return a partial `analyst_signals` update only.
    """

    _patch_fundstate_last_value_reducers(src / "graph" / "schema.py")
    analysts_dir = src / "agents" / "analysts"
    if analysts_dir.is_dir():
        for path in sorted(analysts_dir.glob("*.py")):
            if path.name == "__init__.py":
                continue
            _patch_analyst_error_return(path)


def _patch_fundstate_last_value_reducers(path: Path) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if "finance-agent-eval-infra last-value reducer" in text:
        return
    if "class FundState(TypedDict):" not in text:
        return
    helper = (
        "def _last_value(left, right):\n"
        '    """finance-agent-eval-infra last-value reducer for concurrent graph updates."""\n'
        "    return right if right is not None else left\n\n\n"
    )
    text = text.replace("class FundState(TypedDict):", helper + "class FundState(TypedDict):", 1)
    replacements = (
        (
            '    exp_name: str = Field(description="Experiment name.")',
            "    exp_name: Annotated[str, _last_value]",
        ),
        (
            '    trading_date: datetime = Field(description="Trading date.")',
            "    trading_date: Annotated[datetime, _last_value]",
        ),
        (
            '    ticker: str = Field(description="Ticker in-the-flow.")',
            "    ticker: Annotated[str, _last_value]",
        ),
        (
            '    llm_config: Dict[str, Any] = Field(description="LLM configuration.")',
            "    llm_config: Annotated[Dict[str, Any], _last_value]",
        ),
        (
            '    portfolio: Portfolio = Field(description="Portfolio for the fund.")',
            "    portfolio: Annotated[Portfolio, _last_value]",
        ),
        (
            '    num_tickers: int = Field(description="Number of tickers in the fund.")',
            "    num_tickers: Annotated[int, _last_value]",
        ),
        (
            "    decision: Decision",
            "    decision: Annotated[Decision, _last_value]",
        ),
    )
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")


def _patch_analyst_error_return(path: Path) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if "finance-agent-eval-infra analyst error update" in text:
        return
    old = "        return state\n"
    if old not in text:
        return
    new = (
        "        # finance-agent-eval-infra analyst error update\n"
        "        # Partial update only: returning full FundState from parallel\n"
        "        # analyst nodes raises InvalidUpdateError on LastValue keys (exp_name).\n"
        '        return {"analyst_signals": []}\n'
    )
    path.write_text(text.replace(old, new), encoding="utf-8")


def _is_irrecoverable_setup_error(err: str) -> bool:
    blob = (err or "").lower()
    if any(tok in blob for tok in ("401", "403", "429", "rate limit")):
        return False
    return any(
        tok in blob
        for tok in (
            "modulenotfounderror",
            "importerror",
            "expected str, bytes or os.pathlike",
            "sqlite_setup",
        )
    )


def _grok_yaml(*, exp_name: str, tickers: list[str], model: str) -> str:
    tick = "\n".join(f"  - {t}" for t in tickers)
    # LLMConfig only accepts provider/model/(temperature/max_retries). Base URL is env.
    return (
        f'exp_name: "{exp_name}"\n'
        "cashflow: 100000\n"
        "tickers:\n"
        f"{tick}\n"
        "workflow_analysts:\n"
        "  - technical\n"
        "  - insider\n"
        "  - company_news\n"
        "  - policy\n"
        "llm:\n"
        '  provider: "OpenAI"\n'
        f'  model: "{model}"\n'
    )


def _weekdays(start: str, end: str) -> list[str]:
    cur = datetime.strptime(start, "%Y-%m-%d").date()
    last = datetime.strptime(end, "%Y-%m-%d").date()
    out: list[str] = []
    while cur <= last:
        if cur.weekday() < 5:
            out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def _find_sqlite(src: Path) -> Path | None:
    candidates = [
        src / "example" / "deepfund.db",
        src / "deepfund.db",
        src / "database" / "deepfund.db",
        src / "assets" / "deepfund.db",
    ]
    for path in src.rglob("*.db"):
        candidates.append(path)
    existing = [p for p in candidates if p.is_file()]
    if not existing:
        return None
    existing.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return existing[0]


def _harvest_sqlite(db_path: Path) -> dict[str, Any]:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    out: dict[str, Any] = {"db": str(db_path)}
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table, key in (("decision", "decision_count"), ("signal", "signal_count"), ("portfolio", "portfolio_count")):
            if table in tables:
                out[key] = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if "portfolio" in tables:
            cols = [r[1] for r in con.execute("PRAGMA table_info(portfolio)")]
            order = "trading_date" if "trading_date" in cols else cols[0]
            row = con.execute(f"SELECT * FROM portfolio ORDER BY {order} DESC LIMIT 1").fetchone()
            if row:
                mapping = dict(row)
                for cand in ("total_assets", "total_asset", "assets"):
                    if cand in mapping:
                        try:
                            out["final_total_assets"] = float(mapping[cand])
                        except (TypeError, ValueError):
                            pass
        if "decision" in tables:
            sample = con.execute("SELECT * FROM decision LIMIT 5").fetchall()
            out["decision_sample"] = [dict(r) for r in sample]
    finally:
        con.close()
    return out


def _assert_protocol() -> None:
    _: EnvAdapter = DeepFundEnvAdapter()  # type: ignore[assignment]


__all__ = ["SUITE_ID", "DeepFundEnvAdapter"]
