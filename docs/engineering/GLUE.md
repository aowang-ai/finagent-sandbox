# Glue

This repo prefers composing upstream CLIs. It does **not** pretend every suite is a pure `AgentAdapter.decide` wrap. Known glue stays here so ARCHITECTURE.md can stay honest.

## How each suite is actually wired

| Suite | Ideal LCD | Reality |
| --- | --- | --- |
| FINSABER | `BaseStrategyIso.on_data` → `decide()` | Yes: strategy wrapper calls `agent.decide`. Dataset via `FINSABER_DATA_ROOT` (documented fallback `/workspace/finance-agent-p0/FINSABER/data/sp500_2000_2025_parquet`). Honesty gates are suite-local. |
| AMA | HTTP `POST /trading_action/` → `decide()` | Yes: `AmaHttpShim` + in-process server. PnL harvest uses Yahoo when news vendors are missing. |
| FinToolBench | `decide()` emits result JSONL; official evaluator | Yes: Grok tool-use loop, then `run_relative_eval.py`. RapidAPI/akshare not subscribed — **tool outputs are Grok-produced**. |
| StockBench | `on_bar` → `decide()` | **No.** Official CLI + YAML overlay. `run()` does `_ = agent`. Dual-agent `llm_decision` with a grok `llm_profile`. |
| DeepFund | PM node → `decide()` | **No.** Official `main.py --local-db` with Grok YAML. `run()` does `_ = agent`. The gitignored clone is patched at run time. |

## DeepFund upstream patches

`adapters/deepfund/adapter.py` patches the cloned module before `main.py` (do **not** expand these in a cleanup pass):

- OpenAI-compatible `base_url` (xAI) in `llm/provider.py` — upstream `LLMConfig` rejects unknown YAML keys
- live API key refresh in `llm/inference.py`
- SQLite `DB_PATH` override
- yfinance price methods + router fallback when Alpha Vantage is absent
- LangGraph concurrent `FundState` last-value reducers / analyst error returns (`InvalidUpdateError` on `exp_name`)

These are glue, not upstream. The clone is gitignored; patches are not committed as a fork.

## StockBench

Overlay config (`artifacts/stockbench/config.grok.yaml`) plus an optional live-key patch. The `AgentAdapter` argument is unused. Official window is offline parquet+cache.

## FinToolBench

Open release is eval + questions + tool manifest — no agent runtime. We emit JSONL; the evaluator is official. When RapidAPI/akshare are absent, tool `output` fields are model-produced.

## Optional-suite official-protocol glue

Optional EnvAdapters live in `adapters/{suite}/adapter.py` and stay **protocol → official CLI → SuiteResult**. Shared subprocess / xAI env / skip notes / text patches are in `adapters/_ops/runtime.py`. Resume, harvest, and upstream monkeypatches live in `adapters/<bench>/ops.py` so adapter bodies do not mix exam-room flow with campaign glue.

| Suite | Official entry | Glue |
| --- | --- | --- |
| FinSearchComp | `chat.py --limit 0` + `eval.py` | AzureOpenAI → OpenAI(); grok route; resume/append chat+eval; judge `answer_score` parse |
| Vals Finance Agent | `finance_agent.run_agent --question-file data/public.txt` | skip finished `q*/result.json`; 429 retry cap 100→8; xAI `.env` + model_library yaml |
| LiveTradeBench | `examples/backtest_demo.py` 2025-10-01..2025-11-01 | Grok-eval model filter; yfinance MultiIndex scalar; news 429 fail-fast |
| OpenPM | `python -m agents.portfolio --provider llm_tiered` | BYOK xAI; OOM/SIGKILL stamp is an honest skip, not a subset flag |
| FinMCP | `DianJin-TIR/infer` + `eval/evaluation.py` | skip unless Qieman MCP URL + schema exist |
| InvestorBench | docker `devon warmup\|test\|eval` | skip unless docker + vLLM:8000 + Qdrant:6333 |

Progress / harvest / resume of in-flight official runs: `python cli/optional_suite_ops.py {progress,harvest,resume}`. Blockers: [`OPTIONAL_SUITE_STATUS.md`](OPTIONAL_SUITE_STATUS.md).

## AMA harvest

`get_return.py` expects news APIs this environment often lacks. Harvest is HTTP decision files + Yahoo prices; empty news is a documented protocol gap, not a silent rewrite of AMA.
