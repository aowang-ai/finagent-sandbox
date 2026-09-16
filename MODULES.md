# Upstream modules

Local clones sit under `modules/` (gitignored). Fetch with `./scripts/clone_modules.sh` (v1 five + v2 six). Doctor prints `origin` + `HEAD` when `.git` exists. v2 modules are optional: doctor warns if they are missing.

This document is a map of **official entrypoints**, not a reproduction guide. Install hints are upstream's; we do not vendor their dependency trees.

---

## StockBench

| | |
| --- | --- |
| Path | `modules/stockbench` |
| Upstream | https://github.com/ChenYXxxx/stockbench |
| Paper | https://arxiv.org/abs/2510.02209 |
| Site | https://stockbench.github.io/ |
| Role | Daily portfolio decision quality · **exam room** (`stockbench.daily_sim`) |
| License | Apache-2.0 |

### Install hint

```bash
cd modules/stockbench
conda create -n stockbench python=3.11 && conda activate stockbench
pip install -r requirements.txt
# live fetch only: POLYGON_API_KEY, FINNHUB_API_KEY, OPENAI_API_KEY
```

Python 3.10+ (README says 3.11). Core deps: pandas, numpy, pyarrow, typer, PyYAML, openai, finnhub-python.

### Official entry

```bash
bash scripts/run_benchmark.sh \
  --start-date 2025-03-01 --end-date 2025-06-30 --llm-profile openai
# execs:
python -m stockbench.apps.run_backtest --cfg config.yaml \
  --start ... --end ... --strategy llm_decision --run-id ... \
  --llm-profile ... --agent-mode dual
```

`--help` is implemented on the shell wrapper and on the typer app.

### Metrics it emits

Written under `storage/reports/backtest/`:

- `cum_return`, `max_drawdown`, `sortino`, `volatility_daily`
- annualized `sharpe`, `sortino_annual`, `volatility`
- `trades_count`, `trades_notional`
- optional vs benchmark: tracking error, information ratio, beta, corr
- default benchmark type in `config.yaml`: `per_symbol_buy_and_hold`; also SPY

Universe default: DJIA top-20 by weight (`config.yaml` `symbols_universe`). Dual-agent: fundamental filter → decision agent.

### Known pitfalls

- **API keys** for anything not already in `storage/`. Doctor must not need them. Prefer `--data-mode offline_only` / `--offline` once caches exist.
- `storage/parquet` + `storage/cache` are huge; gitignored. Do not commit.
- Default window is **months**, not the long-horizon honesty exam.
- "Contamination-free because post-2024" is a paper claim, not something this infra verifies.
- `summary_llm: true` in config will call an LLM after the backtest — disable for cheap smokes.

Adapter stub: `adapters/stockbench.py`.

---

## AMA — Agent Market Arena

| | |
| --- | --- |
| Path | `modules/ama` |
| Upstream | https://github.com/The-FinAI/Agent_Market_Arena |
| Paper | https://arxiv.org/abs/2510.11695 |
| Role | Live / near-live multi-market · **exam room** (`ama.multi_market_live`) |

The clone is the **testbed** (HTTP orchestration), not a batteries-included agent zoo.

### Install hint

No `pyproject.toml`. Testbed scripts are plain Python + `requests` / `pandas` / `numpy` / `scipy`. Put keys in `testbed/.env.local` (OpenAI, Anthropic, Gemini, Together, CryptoNews, Finnhub, NewsData, …). **Doctor does not source this file.**

### Official entry

Cwd = `modules/ama/testbed`:

```bash
python get_daily_action.py BTC 2025-01-15 gpt-4o
./get_action.sh                 # batch over ASSETS / MODELS / dates
./auto_daily_action.sh run      # daily pipeline; `setup` installs cron at 00:01 UTC
python get_return.py            # PnL table from action/*.json
```

Agent contract — each agent **must already be an HTTP server**:

```
POST /trading_action/
body: {date, price, news, symbol, model, 10k, 10q, history_price}
resp: {recommended_action: BUY|SELL|HOLD, reasoning}
```

Register URLs in `testbed/configs/agents.json`. Models in `testbed/configs/models.json`.

### Metrics it emits

From `get_return.py`: `total_return` (%), `ann_return`, `ann_vol`, `sharpe_ratio`, `max_drawdown`. Two bookkeeping variants (HOLD keeps position vs flatten). Decision files: `action/{agent}_{asset}_{model}_trading_decisions.json`.

Assets: crypto (BTC, ETH, ADA, SOL, …) and US names (TSLA, AAPL, … BMRN, MRNA).

### Known pitfalls

- Nothing runs until agents are listening. `AmaHttpShim` in `adapters/ama.py` is the in-process translation; a later PR should FastAPI-wrap it.
- `get_return.py` **hardcodes** asset / model / agent lists in `main()` — harvest by editing or importing functions, not by assuming flags.
- Live news/price **drift**. Protocol must pin as-of date and the `paper_trading_*.json` vintage.
- Cron `auto_daily_action.sh setup` is a production footgun; do not enable in CI.

Adapter stub: `adapters/ama.py`.

---

## DeepFund

| | |
| --- | --- |
| Path | `modules/deepfund` |
| Upstream | https://github.com/HKUSTDial/DeepFund |
| Paper | https://arxiv.org/abs/2505.11065 · NeurIPS 2025 D&B ("Time Travel is Cheating") |
| Role | Fund / portfolio live arena + traces · **exam room** (`deepfund.fund_arena`) |
| Python | ≥ 3.11 |

### Install hint

```bash
cd modules/deepfund
conda env create -f environment.yml    # or: uv sync && source .venv/bin/activate
cp .env.example .env                   # LLM + optional Supabase
cd src && python database/sqlite_setup.py
```

Deps (from `pyproject.toml`): pyyaml, pandas, langgraph, langchain-* , supabase, yfinance, pydantic.

### Official entry

```bash
cd modules/deepfund/src
python main.py --config config/exp/buffett.yaml --trading-date YYYY-MM-DD --local-db
```

`--help` works if deps are installed. `--local-db` selects SQLite; **Supabase is the default** otherwise.

Analysts (see `TECHNICAL_GUIDE.md`): `company_news`, `fundamental`, `insider`, `macroeconomic`, `policy`, `technical`. Planner mode in YAML toggles orchestration vs parallel.

### Metrics it emits

Not a single Sharpe file. Four tables (`src/database/sqlite_schema.dbml`):

| Table | What to harvest |
| --- | --- |
| `config` | `exp_name`, tickers, llm, planner flag |
| `portfolio` | `trading_date`, `cashflow`, `total_assets`, `positions` |
| `decision` | `ticker`, `action`, `shares`, `price`, `justification`, `llm_prompt` |
| `signal` | `analyst`, `signal`, `justification` |

Public demo leaderboard: https://deepfund.paradoox.ai/ — that is **their** product, not ours.

### Known pitfalls

- **Chronological `trading-date` per `exp_name`.** Going backwards raises `RuntimeError`.
- `fundamental` / `macroeconomic` analysts may fetch **latest** data even when `--trading-date` is historical (documented in `TECHNICAL_GUIDE.md`). Record this on the protocol or disable those analysts for historical replay.
- The project **does not trade**.
- `exp_name` is a unique experiment id; changing YAML without changing it mixes traces.

Adapter stub: `adapters/deepfund.py`.

---

## FinToolBench

| | |
| --- | --- |
| Path | `modules/fintoolbench` |
| Upstream | https://github.com/Double-wk/FinToolBench |
| Paper | https://arxiv.org/abs/2603.08262 |
| Role | Tool-call correctness + finance compliance · **exam room** (`fintoolbench.tool_compliance`) |

Open release = **evaluation pipeline + 760-tool manifest + 295 questions**. Full agent runtime is not included.

### Install hint

```bash
cd modules/fintoolbench
pip install -r requirements.txt
# optional, needs a logged-in RapidAPI browser session:
python -u code_bench/tools/tools_rapidapi_subscribe_url.py
```

`requirements.txt` is a pinned freeze (akshare, datasets, httpx, …). Do not install it for doctor.

### Official entry

```bash
python -u code_bench/evaluate/run_relative_eval.py \
  --inputs data/result/result/result_model_name_full.jsonl \
  --output_dir data/eval/relative_model
```

Writes `<setting>_results.jsonl`, `<setting>_metrics.json`, `all_metrics.json`.

Questions: `data/question/select_data_real_remove_duplicates.jsonl` (166 single-tool + 129 multi-tool).
Manifest: `tools/tools_all_annotated.jsonl` with `financial_tags` (`timeliness`, `intent_type`, `regulatory_domains`).

### Metrics it emits

Capability (higher is better):

| Key | Name |
| --- | --- |
| `tir` | Tool Invocation Rate |
| `tesr` | Tool Execution Success Rate |
| `cer` | Conditional Execution Rate |
| `soft_score` | LLM-judge / exact match |
| `css` | correctness given successful execution |

Compliance **mismatch** rates (lower is better): `tmr` timeliness, `imr` intent, `dmr` domain.

### Known pitfalls

- We must **emit** the result JSONL; the evaluator does not call the agent.
- RapidAPI endpoints **drift**. Protocol must pin eval date + manifest hash.
- SoftScore and TMR/IMR/DMR use a judge LLM (`COMPLIANCE_JUDGE_MODEL` / `JUDGE_MODEL`). Not a doctor concern.
- Gates on TMR/IMR/DMR must be `lte`, not `gte`.
- `--headless` vs visible browser on the subscribe helper.

Adapter stub: `adapters/fintoolbench.py`.

---

## FINSABER

| | |
| --- | --- |
| Path | `modules/finsaber` |
| Upstream | https://github.com/waylonli/FINSABER |
| Paper | https://arxiv.org/abs/2505.07078 · KDD 2026 |
| Docs | https://waylonli.github.io/FINSABER/ |
| Dataset | https://huggingface.co/datasets/finsaber-team/FINSABER-V2-Data |
| Role | Long-horizon, survivorship-aware exam room (`finsaber.long_horizon`) — **suite among equals** | |
| Package | PyPI `finsaber` 2.x · Python ≥ 3.10 · Apache-2.0 |

### Install hint

```bash
pip install finsaber
# or local:
cd modules/finsaber && pip install -e ".[dev,research]"
```

Set `FINSABER_DATA_ROOT` to the parquet directory (must contain `price_daily/`). A documented local fallback is `/workspace/finance-agent-p0/FINSABER/data/sp500_2000_2025_parquet`. **Do not** `git lfs` / HuggingFace-download the parquet set for doctor.

Branch: `main` = FINSABER-2 (parquet, costs, `next_open`). `reproduce` = FINSABER-1 paper numbers. This infra targets **main**.

### Official entry

There is no required CLI. Packaged API:

```python
from finsaber import FINSABERBt, FinsaberParquetDataset
from finsaber.strategy.timing import BuyAndHoldStrategy

data = FinsaberParquetDataset("/path/to/sp500_2000_2025_parquet")
config = {
    "data_loader": data,
    "tickers": ["AAPL"],
    "date_from": "2024-01-02",
    "date_to": "2024-01-10",
    "setup_name": "demo_buy_hold",
    "execution_timing": "next_open",
    "slippage_perc": 0.0005,
    "liquidity_cap_pct": 0.025,
    "save_results": True,
    "silence": True,
}
results = FINSABERBt(config).run_iterative_tickers(BuyAndHoldStrategy)
```

LLM-style agents use the Python-native engine `FINSABER` + `BaseStrategyIso.on_data`. Research launchers (not the installable core): `examples/experiments/run_finsaber2_benchmarks.py`, `examples/custom_dataset_example.py`.

### Metrics it emits

Under `backtest/output/<setup>/<strategy>/` (also `run_config.json`, `run_manifest.json`, `run_summary.csv`):

`final_value`, `total_return`, `annual_return`, `annual_volatility`, `sharpe_ratio`, `sortino_ratio`, `max_drawdown`, `total_commission`, `total_slippage`, `total_llm_cost`, `total_trading_cost`.

Per window/ticker: `equity_curve.csv`, `trades.csv`, `orders.csv`, `rejected_orders.csv`, `llm_costs.csv`.

`total_return` / `annual_return` / `annual_volatility` are **fractions** in artifacts (`0.12` = 12%).

### Known pitfalls

- **`cherry_pick_*` setups are debug rooms, never the long-horizon protocol.** They overstate LLM traders.
- Default fill for date-level text: `next_open`. `same_close` is look-ahead unless timestamps prove availability.
- Selectors must rank inside the training / prior window only (universe look-ahead).
- Adjusted OHLC for fills; **raw volume** for liquidity caps.
- This pass does **not** claim bitwise paper reproduction. FINSABER-1 vs FINSABER-2 are different exams.
- `backtest/output/` in the clone may contain research pickles; gitignored.

Honesty gates this infra will enforce when wired (`adapters/finsaber.py`): next_open, costs enabled, not cherry-pick.

Adapter stub: `adapters/finsaber.py`.

---

## How they become one infra

| Question we want to ask | Suite | Scorecard role |
| --- | --- | --- |
| Did it only look good because of look-ahead, survivors, or zero costs? | FINSABER | suite among equals (honesty gates on this suite) |
| Can it rebalance a 20-name book day by day for a few months? | StockBench | suite among equals |
| Does it still decide on live crypto + names with news? | AMA | suite among equals |
| Can a fund graph leave an auditable decision trace? | DeepFund | suite among equals |
| Does it pick the right tool on time, with the right intent and domain? | FinToolBench | suite among equals |
| Can it decide across stocks / crypto / ETFs in InvestorBench's env? | InvestorBench | v2 optional |
| Does live multi-market allocation (stocks + Polymarket) still work? | LiveTradeBench | v2 optional |
| Does it orchestrate real MCP financial tools? | FinMCP-Bench | v2 optional |
| Can it research SEC filings with tools? | Vals Finance Agent | v2 optional |
| Can it fetch time-sensitive figures and investigate historically? | FinSearchComp | v2 optional |
| Can it size a PIT S&P 500 book with an audit trail? | OpenPM | v2 optional (preferred over PortBench) |

One `AgentAdapter` is the unit under test. Each suite is an exam room. `admission.decision` is completeness only — FINSABER does not veto the others. v2 suites are optional (`PLANNED_SUITE_IDS_V2`) until a full protocol run exists. See `GOAL.md` and `ARCHITECTURE.md`. Compose is not pure everywhere: `docs/engineering/GLUE.md`.

---

## InvestorBench

| | |
| --- | --- |
| Path | `modules/investorbench` |
| Upstream | https://github.com/felis33/INVESTOR-BENCH |
| Paper | https://arxiv.org/abs/2412.18174 · ACL 2025 |
| Role | Cross-asset decision · **exam room** (`investorbench.decision`) · v2 optional |
| License | MIT |
| Clone HEAD | `87e0f7b` (recorded at expand; re-check with doctor) |

### Install hint

Docker eval image (`devon`) + Qdrant + optional vLLM. Credentials in `.env`: `OPENAI_API_KEY` (embeddings), `HUGGING_FACE_HUB_TOKEN`. GuardRails token only for closed models.

### Official entry

```bash
docker build -t devon -f Dockerfile .
docker run -p 6333:6333 qdrant/qdrant
docker run -it -v .:/workspace --network host devon warmup
docker run -it -v .:/workspace --network host devon test
docker run -it -v .:/workspace --network host devon eval
# equivalent typer: python run.py warmup|test|eval --config-path configs/main.json
```

### Metrics it emits

`results/<run_name>/<chat_model>/<trading_symbols>/metrics` — cumulative return and Sharpe (single-asset vs multi-asset helpers in `run.py`).

In-clone env data: `data/{hon,jnj,msft,nflx,uvv,btc,eth}.json`. README equity window 2020-10-01 .. 2021-05-06 (warmup 2020-07-01 .. 2020-09-30). Crypto and ETF windows are separate.

### Known pitfalls

- Full protocol is a multi-month backtest plus vLLM/Qdrant. Not burned in this pass.
- ETF window is documented; no ETF json ships in `data/`.
- Adapter stub: `adapters/investorbench.py` (honest skip).

---

## LiveTradeBench

| | |
| --- | --- |
| Path | `modules/livetradebench` |
| Upstream | https://github.com/ulab-uiuc/live-trade-bench |
| Paper | https://arxiv.org/abs/2511.03628 |
| Site | https://trade-bench.live |
| Role | Live US equities + Polymarket · **exam room** (`livetradebench.live`) · v2 optional |
| License | PolyForm Noncommercial 1.0.0 (`LICENSE.COMMERCIAL` for commercial) |

### Install hint

```bash
pip install live-trade-bench
# or: poetry install
export OPENAI_API_KEY=...
```

### Official entry

Python API (no required CLI):

```python
from live_trade_bench.systems import StockPortfolioSystem, PolymarketPortfolioSystem
system = StockPortfolioSystem.get_instance()
system.add_agent(name="GrokCli", initial_cash=10000.0, model_name="...")
system.initialize_for_live()
system.run_cycle()
system.get_all_agent_performance()
```

Paper default: **50-day live** eval, dual market.

### Metrics it emits

Per-agent performance from the system: return / risk (harvest `get_all_agent_performance()`). Ticker map in `live_trade_bench/fetchers/constants.py`.

### Known pitfalls

- Live feeds; not an offline backtest (paper design).
- Non-commercial license unless you have a commercial grant.
- Adapter stub: `adapters/livetradebench.py` (honest skip).

---

## FinMCP-Bench

| | |
| --- | --- |
| Path | `modules/finmcp` (clone of [aliyun/qwen-dianjin](https://github.com/aliyun/qwen-dianjin); suite lives in `DianJin-TIR/`) |
| Upstream | https://github.com/aliyun/qwen-dianjin |
| Paper | https://arxiv.org/abs/2603.24943 · ICASSP 2026 |
| Dataset | https://huggingface.co/datasets/DianJin/FinMCP-Bench |
| Role | MCP tool orchestration · **exam room** (`finmcp.tool_mcp`) · v2 optional |
| License | MIT (hub). Dataset CC-BY-NC-SA-4.0. |

### Official entry

```bash
cd modules/finmcp/DianJin-TIR
python infer/inference_api.py
python eval/evaluation.py --eval_data_path=<pred.json>
```

613 samples, 65 real MCPs, three splits (single-tool / multi-tool / multi-turn). Metrics: Tool Precision, Recall, F1, EMR (`consist`).

### Known pitfalls

- `Benchmark/benchmark_final.json` is **not in git** — fetch the HF dataset.
- Qieman MCP Server URL + `MCP_SCHEMA` required for a real tool loop.
- Adapter stub: `adapters/finmcp.py` (honest skip).

---

## Vals Finance Agent Benchmark

| | |
| --- | --- |
| Path | `modules/vals_finance_agent` |
| Upstream | https://github.com/vals-ai/finance-agent |
| Paper | https://arxiv.org/abs/2508.00828 |
| Site | https://www.vals.ai/benchmarks/finance_agent |
| Role | Expert SEC/research + tools · **exam room** (`vals_finance_agent.research`) · v2 optional |
| License | MIT |

### Official entry

```bash
make install && source .venv/bin/activate
finance-agent --question-file data/public.txt --model <model>
```

Tools: `web_search` (Tavily), `edgar_search`, `parse_html_page`, `retrieve_information`. Public clone: `data/public.txt` (50 questions). Full suite: **537** gated questions on platform.vals.ai (`VALS_API_KEY`).

### Known pitfalls

- Platform access is gated. Do not pretend the 50 public questions are the official 537.
- Needs Tavily + SEC-API keys for tools.
- Adapter stub: `adapters/vals_finance_agent.py` (honest skip).

---

## FinSearchComp

| | |
| --- | --- |
| Path | `modules/finsearchcomp` |
| Upstream | https://github.com/randomtutu/FinSearchComp |
| Paper | https://arxiv.org/abs/2509.13160 |
| Dataset | https://huggingface.co/datasets/ByteSeedXpert/FinSearchComp |
| Role | Time-sensitive financial search · **exam room** (`finsearchcomp.search`) · v2 optional |
| License | CC-BY-4.0 |

### Official entry

```bash
python finsearchcomp/chat/chat.py \
  --model_name gemini-2.5-flash \
  --input_file data/finsearchcomp_data.json \
  --output_path result/chat-result/chat.json
python finsearchcomp/eval/eval.py \
  --model_name gemini-2.5-flash \
  --input finsearchcomp/result/chat-result/chat.json \
  --output finsearchcomp/result/eval-result/eval.json
```

635 questions; tasks: time-sensitive fetch, simple historical lookup, complex historical investigation. AkShare-compatible split: `data/finsearchcomp_akshare_version.json` (594).

### Known pitfalls

- API keys in `finsearchcomp/config/config.yaml`. Judge LLM for eval.
- Time-sensitive GT depends on AkShare / snapshots going stale.
- Adapter stub: `adapters/finsearchcomp.py` (honest skip).

---

## OpenPM-Bench

| | |
| --- | --- |
| Path | `modules/openpm` |
| Upstream | https://github.com/aslcai/OpenPM-Bench |
| Dataset | https://huggingface.co/datasets/aslcai/OpenPM-Bench |
| Role | PIT portfolio + honesty audit trail · **exam room** (`openpm.portfolio_pit`) · v2 optional |
| License | Apache-2.0 |

Preferred over PortBench (`GOAL.md`). Do not add PortBench as required.

### Official entry

```bash
python -m agents.portfolio --provider llm_tiered \
  --llm-provider openrouter --model deepseek/deepseek-v3.2 \
  --start-date 2026-03-02 --end-date 2026-05-01
```

Canonical README window example: 2026-03-02 .. 2026-05-01, `--rebalance once`, `--pit-membership` on, risk `balanced`. Writes `evaluations/*.json` (metrics, contamination certificate, bias checklist, attribution) plus a provenance manifest.

### Known pitfalls

- `dataset/panel/price_panel_5m.parquet` is gitignored; download HF or rebuild (IEX HIST native parser + FRED/Finnhub/SEC).
- Deterministic baselines need no API key **if the panel exists**. LLM path is BYOK.
- Adapter stub: `adapters/openpm.py` (honest skip).

