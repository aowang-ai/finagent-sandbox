"""LiveTradeBench patches, harvest, and official resume.

Not an EnvAdapter. `adapters.livetradebench` invokes examples/backtest_demo.py.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from ..base import Artifact, Metric, ProtocolSpec, SuiteResult, SuiteStatus
from ..v2_runtime import (
    apply_text_patch,
    artifacts_dir,
    load_json,
    python_imports_ok,
    repo_venv_python,
    run_logged,
    skip_message,
    tail_text,
    uv_pip_install,
    xai_env,
)

SUITE_ID = "livetradebench.live"
MODULE_REL = "modules/livetradebench"
UPSTREAM_CLI = (
    "python examples/backtest_demo.py --exchanges stock "
    "--start-date 2025-10-01 --end-date 2025-11-01"
)
DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "JPM", "V", "JNJ", "UNH", "PG",
    "KO", "XOM", "CAT", "WMT", "META", "TSLA", "AMZN",
]
DEFAULT_FROM = "2025-10-01"
DEFAULT_TO = "2025-11-01"
CONTINUE_FROM = "2025-10-03"
VENV_NAME = "v2_livetrade"


def module_path(repo_root: Path) -> Path:
    return repo_root / MODULE_REL


def hard_blockers(mod: Path) -> list[str]:
    blockers: list[str] = []
    if not mod.is_dir():
        blockers.append("modules/livetradebench missing (run scripts/clone_modules.sh)")
    if not (mod / "examples" / "backtest_demo.py").is_file():
        blockers.append("examples/backtest_demo.py missing (official offline entry)")
    if not (mod / "live_trade_bench" / "systems").is_dir():
        blockers.append("live_trade_bench/systems missing")
    return blockers


def skip_notes(mod: Path, *, dry: bool) -> str:
    extras = [
        "paper live protocol is ~50-day dual-market; execute uses official "
        "examples/backtest_demo.py defaults 2025-10-01..2025-11-01"
    ]
    return skip_message(hard_blockers(mod), dry=dry, extras=extras)


def ensure_install(python: str) -> None:
    if python_imports_ok(python, "yfinance", "litellm", "dotenv", "requests"):
        return
    print("[livetrade] installing runtime deps", flush=True)
    uv_pip_install(
        python,
        "yfinance",
        "litellm",
        "python-dotenv",
        "requests",
        "beautifulsoup4",
        "tenacity",
        "fastapi",
        "uvicorn",
    )


def patch_yfinance_scalar(mod: Path) -> None:
    apply_text_patch(
        mod / "live_trade_bench" / "fetchers" / "stock_fetcher.py",
        marker="finance-agent-eval-infra yfinance scalar",
        needle=(
            "        if df.empty:\n"
            "            print(f\"No data for {ticker} from {start_date} to {end_date}.\")\n"
            "        return df\n"
        ),
        replacement=(
            "        if df.empty:\n"
            "            print(f\"No data for {ticker} from {start_date} to {end_date}.\")\n"
            "        # finance-agent-eval-infra yfinance scalar\n"
            "        try:\n"
            "            if getattr(df, \"columns\", None) is not None and getattr(df.columns, \"nlevels\", 1) > 1:\n"
            "                df.columns = df.columns.get_level_values(0)\n"
            "        except Exception:\n"
            "            pass\n"
            "        return df\n"
        ),
        label="livetrade",
    )


def patch_backtest_models(mod: Path, model: str) -> None:
    path = mod / "examples" / "backtest_demo.py"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if "finance-agent-eval-infra grok model" in text:
        return
    needle = (
        "    # Filter to GPT + Anthropic only\n"
        "    models = [\n"
        "        (name, model_id)\n"
        "        for name, model_id in all_models\n"
        "        if model_id.startswith(\"openai/\") or model_id.startswith(\"anthropic/\")\n"
        "    ]\n"
    )
    replacement = (
        "    # finance-agent-eval-infra grok model\n"
        "    import os as _os\n"
        "    _eval_model = _os.environ.get(\"LTB_EVAL_MODEL\") or "
        + json.dumps(model)
        + "\n"
        "    models = [(\"Grok-eval\", _eval_model)]\n"
    )
    if needle not in text:
        return
    path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
    print(f"[livetrade] patched backtest_demo.py models → {model}", flush=True)


def patch_news_failfast(mod: Path) -> None:
    apply_text_patch(
        mod / "live_trade_bench" / "fetchers" / "news_fetcher.py",
        marker="finance-agent-eval-infra news fail-fast",
        needle=(
            "            try:\n"
            "                resp = self.make_request(url, headers=html_headers, timeout=15)\n"
            "                # Use resp.text instead of resp.content to handle gzip encoding properly\n"
            "                soup = BeautifulSoup(resp.text, \"html.parser\")\n"
            "            except Exception as e:\n"
            "                print(f\"Request/parse failed: {e}\")\n"
            "                break\n"
        ),
        replacement=(
            "            try:\n"
            "                # finance-agent-eval-infra news fail-fast\n"
            "                import requests as _req\n"
            "                self._rate_limit_delay()\n"
            "                resp = _req.get(url, headers=html_headers, timeout=8)\n"
            "                if getattr(resp, \"status_code\", None) == 429:\n"
            "                    print(\"Request/parse failed: HTTP 429 (fail-fast empty news)\")\n"
            "                    break\n"
            "                soup = BeautifulSoup(resp.text, \"html.parser\")\n"
            "            except Exception as e:\n"
            "                print(f\"Request/parse failed: {e}\")\n"
            "                break\n"
        ),
        label="livetrade",
    )


def apply_continue_patches(repo_root: str | Path = ".", model: str | None = None) -> None:
    from runners.grok import DEFAULT_MODEL_API

    root = Path(repo_root).resolve()
    mod = module_path(root)
    patch_yfinance_scalar(mod)
    patch_backtest_models(mod, model or f"xai/{DEFAULT_MODEL_API}")
    patch_news_failfast(mod)


def harvest_one_log(log_path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not log_path.is_file():
        return out
    text = log_path.read_text(encoding="utf-8", errors="replace")
    applied = re.findall(r"stock/Grok-eval: ✅ allocations applied", text)
    if not applied:
        applied = re.findall(r"allocations applied", text)
    out["n_days_completed"] = float(len(applied))
    day_marks = re.findall(r"=== Day (\d+)/(\d+) ===", text)
    if day_marks:
        last_day, window = int(day_marks[-1][0]), int(day_marks[-1][1])
        out["n_days_started"] = float(last_day)
        out["n_days_window"] = float(window)
    dates = re.findall(r"===== 📆 (\d{4}-\d{2}-\d{2}) =====", text)
    if dates:
        out["dates_started"] = dates
        out["n_dates_started"] = float(len(dates))
    values = re.findall(r"New Value: \$([0-9,]+\.\d+)", text)
    if values:
        try:
            out["final_value"] = float(values[-1].replace(",", ""))
        except ValueError:
            pass
        out["initial_value"] = 1000.0
        out["return_percentage"] = (
            (out["final_value"] - out["initial_value"]) / out["initial_value"] * 100.0
        )
    if "n_days_completed" in out:
        out["n_days"] = out["n_days_completed"]
    return out


def harvest_backtest(log_path: Path, models_data: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    rows = load_json(models_data)
    if isinstance(rows, list) and rows:
        row = rows[0] if isinstance(rows[0], dict) else {}
        port = row.get("portfolio") if isinstance(row.get("portfolio"), dict) else {}
        init = port.get("initialCash") or port.get("initial_cash")
        final = port.get("totalValue") or port.get("total_value")
        if isinstance(init, (int, float)) and isinstance(final, (int, float)) and init:
            out["initial_value"] = float(init)
            out["final_value"] = float(final)
            out["return_percentage"] = (float(final) - float(init)) / float(init) * 100.0
        hist = row.get("allocationHistory") or row.get("allocation_history") or []
        if isinstance(hist, list) and hist:
            out["n_days_hist"] = float(len(hist))
    prior = log_path.with_name("backtest_demo_prior.log")
    continue_log = log_path.with_name("backtest_demo_continue.log")
    if continue_log.is_file() and prior.is_file():
        log_files = [prior, continue_log]
    elif continue_log.is_file():
        log_files = [continue_log]
    elif prior.is_file() and log_path.is_file() and prior.resolve() != log_path.resolve():
        log_files = [prior, log_path]
    else:
        log_files = [p for p in (log_path, prior, continue_log) if p.is_file()]
    parts = [harvest_one_log(p) for p in log_files]
    n_done = 0.0
    dates: list[str] = []
    last_part: dict[str, Any] = {}
    for part in parts:
        n_done += float(part.get("n_days_completed") or 0)
        dates.extend(list(part.get("dates_started") or []))
        if part.get("final_value") is not None:
            last_part = part
        elif not last_part:
            last_part = part
    if n_done:
        out["n_days_completed"] = n_done
        out["n_days"] = n_done
    out["n_days_window"] = 23.0
    if dates:
        out["n_dates_started"] = float(len(dates))
        out["last_date"] = dates[-1]
    if "final_value" not in out and "final_value" in last_part:
        out["final_value"] = last_part["final_value"]
        out.setdefault("initial_value", last_part.get("initial_value") or 1000.0)
        if out.get("initial_value"):
            out["return_percentage"] = (
                (out["final_value"] - out["initial_value"]) / out["initial_value"] * 100.0
            )
    if "n_days_started" in last_part:
        out["n_days_started"] = last_part["n_days_started"]
    return out


def harvest_existing_run(repo_root: str | Path = ".") -> SuiteResult:
    """SuiteResult from official backtest_demo.py (partial or full window; no rerun)."""

    from runners.grok import DEFAULT_MODEL_API

    root = Path(repo_root).resolve()
    mod = module_path(root)
    artifacts = artifacts_dir(root, "livetradebench")
    log_path = artifacts / "backtest_demo.log"
    results_out = artifacts / "backtest_results.json"
    models_data = mod / "backend" / "models_data_init.json"
    python = repo_venv_python(root, VENV_NAME)
    model = f"xai/{DEFAULT_MODEL_API}"
    proto = ProtocolSpec(
        suite_id=SUITE_ID,
        date_from=DEFAULT_FROM,
        date_to=DEFAULT_TO,
        universe=list(DEFAULT_UNIVERSE),
        data_vintage="official backtest_demo.py replay (yfinance)",
        extra={
            "n_days": 50,
            "markets": ["us_equities"],
            "license": "PolyForm-Noncommercial-1.0.0",
            "protocol_entry": "examples/backtest_demo.py",
            "execute": True,
            "artifacts_dir": str(artifacts),
            "python": python,
            "model": model,
            "harvest": "official_window",
        },
    )
    harvested = harvest_backtest(log_path, models_data)
    results_out.write_text(json.dumps(harvested, indent=2), encoding="utf-8")
    n_done = harvested.get("n_days_completed") or harvested.get("n_days") or 0
    window = harvested.get("n_days_window") or 23
    ret = harvested.get("return_percentage")
    window_done = float(n_done) >= float(window)
    proto.extra["harvest"] = "official_window_complete" if window_done else "mid_window"
    status = (
        SuiteStatus.PASS.value
        if window_done
        else SuiteStatus.FAIL.value
        if n_done
        else SuiteStatus.ERROR.value
    )
    metrics: list[Metric] = [
        Metric(name="n_days", value=float(n_done), source="backtest_demo.log"),
        Metric(name="n_days_completed", value=float(n_done), source="backtest_demo.log"),
        Metric(name="n_days_window", value=float(window), source="backtest_demo.log"),
    ]
    if isinstance(ret, (int, float)):
        metrics.append(Metric(name="return_percentage", value=float(ret), source="backtest_demo.log"))
        metrics.append(Metric(name="total_return", value=float(ret) / 100.0, source="backtest_demo.log"))
    if window_done:
        remain_txt = (
            "Official 23-weekday window complete (prior 2 days 2025-10-01..02 + "
            "continue 21 days 2025-10-03..31). Upstream has no portfolio-state "
            "resume flag; continue segment cash restarted at $1000. "
            "News 429 fail-fast (empty news, allocations still ran). "
        )
    else:
        remain_txt = (
            "Remaining days use official --start-date/--end-date (upstream has no "
            "portfolio-state resume flag; cash restarts at $1000 on continue segment). "
        )
    notes = (
        f"Official examples/backtest_demo.py window {DEFAULT_FROM}..{DEFAULT_TO} "
        f"(demo defaults, not a 1-day invention) exchanges=stock model={model}. "
        f"Continue harvest n_days_completed={int(n_done)}/{int(window)} "
        f"last_date={harvested.get('last_date')}. {remain_txt}"
        f"log={log_path}. Live 50-day dual-market not run in-session. "
        + tail_text(log_path, 12).replace("\n", " | ")[:400]
    )
    cmd = (
        f"{python} {mod / 'examples' / 'backtest_demo.py'} "
        f"--exchanges stock --start-date {DEFAULT_FROM} --end-date {DEFAULT_TO}"
    )
    return SuiteResult(
        suite_id=SUITE_ID,
        status=status,
        protocol=proto,
        metrics=metrics,
        artifacts=[
            Artifact(kind="log", path=str(log_path), media_type="text/plain"),
            Artifact(kind="results_json", path=str(results_out), media_type="application/json"),
        ],
        traces_path=str(artifacts),
        notes=notes,
        upstream_cli=cmd,
    )


def progress_snapshot(repo_root: Path) -> dict[str, Any]:
    n = 0
    last = None
    for name in ("backtest_demo_prior.log", "backtest_demo_continue.log"):
        path = repo_root / "artifacts" / "livetradebench" / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        n += len(re.findall(r"allocations applied", text))
        dates = re.findall(r"===== 📆 (\d{4}-\d{2}-\d{2}) =====", text)
        if dates:
            last = dates[-1]
    return {"n_days_completed": n, "last_date": last, "n_days_window": 23}


def resume_official(repo_root: str | Path = ".") -> int:
    """Continue official backtest_demo.py remaining trading days (2025-10-03..2025-11-01)."""

    from runners.grok import DEFAULT_MODEL_API, refresh_xai_api_key

    root = Path(repo_root).resolve()
    key = refresh_xai_api_key(force=True)
    model = f"xai/{DEFAULT_MODEL_API}"
    apply_continue_patches(root, model=model)
    python = repo_venv_python(root, VENV_NAME)
    mod = module_path(root)
    artifacts = artifacts_dir(root, "livetradebench")
    prior = artifacts / "backtest_demo_prior.log"
    old = artifacts / "backtest_demo.log"
    if old.is_file() and not prior.is_file():
        shutil.copy2(old, prior)
        print(f"[livetrade] preserved prior log -> {prior}", flush=True)
    log_path = artifacts / "backtest_demo_continue.log"
    stocks = ",".join(DEFAULT_UNIVERSE)
    cmd = [
        python,
        str(mod / "examples" / "backtest_demo.py"),
        "--exchanges",
        "stock",
        "--start-date",
        CONTINUE_FROM,
        "--end-date",
        DEFAULT_TO,
        "--stocks",
        stocks,
        "--stock-count",
        str(len(DEFAULT_UNIVERSE)),
    ]
    env = xai_env(pythonpath_dirs=[mod, root])
    if key:
        env["X_AI_API_KEY"] = key
        env["XAI_API_KEY"] = key
        env["OPENAI_API_KEY"] = key
        env["OPENAI_BASE_URL"] = "https://api.x.ai/v1"
    env["LTB_PARALLELISM"] = "1"
    env["LTB_EVAL_MODEL"] = model
    print(
        f"[livetrade] continuing official window {CONTINUE_FROM}..{DEFAULT_TO} model={model}",
        flush=True,
    )
    proc = run_logged(cmd, cwd=mod, env=env, log_path=log_path, append=True)
    shutil.copy2(log_path, old)
    print(f"[livetrade] backtest_demo rc={proc.returncode}", flush=True)
    return int(proc.returncode)
