# DONE — Smoke eval: full pipeline, small samples

Repo: `aowang-ai/finagent-sandbox` only. `finance-agent-eval-infra` untouched.

Author: Ao Wang `<aowang-ai@users.noreply.github.com>`.

Log: `logs/smoke_eval.log` (gitignored). Dumps: `artifacts/suite_results/grok-cli/{suite}.json`. Scorecard: `reports/GROK_CLI_SCORECARD.*`.

Entry: `PYTHONPATH=src python -m finagent.cli --harness grok-cli --smoke --suites <all 11 ids>`.

Flow proven: `HarnessFactory(grok-cli) → BenchFactory → (subprocess | FinMCP Trial sandbox.exec_sync) → SuiteResult dump → scorecard compose`. `--smoke` sets `protocol.extra["smoke"]=true` and shrinks **existing** knobs (dates, universe, `--limit`, `n_questions`). Official entrypoints unchanged. Full-eval leftover `stockbench.apps.run_backtest` PID 3854573 was killed first.

## Checklist

- [x] Full-eval leftovers dead (stockbench 3854573 SIGTERM).
- [x] `--smoke` on `python -m finagent.cli`; adapter-local shrink; same official CLIs.
- [x] All 11 benches attempted; dumps under `artifacts/suite_results/grok-cli/`.
- [x] Scorecard written with `tier=required|optional`. Completeness `promote` (required five all scored).
- [x] Honest skip on docker / Qieman MCP / missing OpenPM panel. No fake passes.
- [x] First FINSABER 5-day window failed (`Not enough data`); re-ran 2024-01-02..2024-02-29 (1 ticker) → pass.
- [x] FinMCP `LocalProcessSandbox` in `protocol.extra["_sandbox"]` stripped so scorecard JSON hash does not crash.

## Per-suite

| Suite | Tier | Status | Sample | Notes |
| --- | --- | --- | --- | --- |
| `ama.multi_market_live` | required | **pass** | 1 ticker AAPL × 1 day 2025-10-22 | Official `POST /trading_action/` (port bind fallback). HTTP 1/1. |
| `finsaber.long_horizon` | required | **pass** | 1 claimed setup `random_sp500_5`, ticker CI, 2024-01-02..2024-02-29 | Official `FINSABER.run_iterative_tickers(GrokCliStrategyIso)`. n_ticker_runs=1. Honesty gates on this suite only. |
| `stockbench.daily_sim` | required | **pass** | `--symbols AAPL --start 2025-03-03 --end 2025-03-04` | Official `python -m stockbench.apps.run_backtest` dual-agent grok overlay, offline_only. |
| `fintoolbench.tool_compliance` | required | **pass** | first 2 official JSONL questions | Grok JSONL then official `run_relative_eval.py`. n_questions=2, n_with_tool_calls=2. |
| `deepfund.fund_arena` | required | **pass** | 1 ticker AAPL × 1 weekday 2025-04-01 | Official `main.py --local-db`. days_ok=1. |
| `investorbench.decision` | optional | **skip** | no smaller official smoke than docker `devon warmup\|test\|eval` | docker / vLLM:8000 / Qdrant:6333 missing. Not inventing a non-docker protocol. |
| `livetradebench.live` | optional | **pass** | `--stocks AAPL --start-date 2025-10-01 --end-date 2025-10-02` | Official `examples/backtest_demo.py`. n_days_completed=2. |
| `finmcp.tool_mcp` | optional | **skip** | n_samples=2 if Qieman MCP present | `benchmark_final.json` not vendored; Qieman MCP URL+schema unset. Not inventing a no-MCP protocol. Trial `local-process` path was entered (then skip). |
| `vals_finance_agent.research` | optional | **fail** | first 2 `public.txt` lines, `--max-turns 8` | Official `finance_agent.run_agent --question-file`. n_finished=2 n_ok=0 n_fail=2. TAVILY/SEC_EDGAR skipped honestly. No fake accuracy. |
| `finsearchcomp.search` | optional | **fail** | official `chat.py --limit 2` then `eval.py` | n_chat=2 chat_rc=0; judge `eval.py` rc=1 (`KeyError: 'tags'` — upstream data has no tags). Not inventing a custom judge. |
| `openpm.portfolio_pit` | optional | **skip** | date shrink cannot avoid 2.6GiB ndjson load | `price_panel_5m.parquet` and `feature_output.ndjson` missing. Not inventing `--max-bars`. |

## Runtime

- First pass (AMA → LiveTrade, crash on FinMCP compose): ~2 min.
- Resume (FINSABER longer window + FinMCP skip + Vals + FinSearch + OpenPM): ~2 min.
- Wall clock minutes, not overnight.

## Command

```
PYTHONPATH=src python -m finagent.cli --harness grok-cli --smoke \
  --suites ama.multi_market_live,finsaber.long_horizon,stockbench.daily_sim,fintoolbench.tool_compliance,deepfund.fund_arena,investorbench.decision,livetradebench.live,finmcp.tool_mcp,vals_finance_agent.research,finsearchcomp.search,openpm.portfolio_pit
```
