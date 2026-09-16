# Grok CLI scorecard

- generated_at: `2026-09-16T17:52:01+00:00`
- report_id: `a499edea-5481-41c4-a189-2a9fd61d695a`
- agent: `grok-cli` version `overnight`
- protocol_hash: `sha256:6186fbc9030ede0af2f491e8ec62c1ee70995c7808cdd043ea56e8a6e44bfd70`
- scoring: **parallel scorecard** (kernel=`parallel_scorecard`)
- completeness: `promote` — parallel scorecard complete: all required suites produced a score (ama.multi_market_live, finsaber.long_horizon, stockbench.daily_sim, fintoolbench.tool_compliance, deepfund.fund_arena). Per-suite pass/fail is not a veto.
- live: `finsaber.long_horizon lowvol_sp500_5/2025-01-01_2026-01-01 ticker=? as_of=? bars=? hb_done=30/30 disk_done=30/30 hb_age=3186s STALL`

Per-suite pass/fail is **not** a global veto. FINSABER honesty gates stay on that suite.

| Suite | Tier | Status | Key metrics | Notes |
| --- | --- | --- | --- | --- |
| `ama.multi_market_live` | required | **pass** | n_assets=1.0, n_http_ok=1.0, n_http_calls=1.0 | SMOKE (1 ticker (AAPL) × 1 day 2025-10-22; POST /trading_action/). AMA window 2025-10-22..2025-10-22 on 1 assets. HTTP calls 1/1. News vendor keys missing — prices from Yahoo, news |
| `finsaber.long_horizon` | required | **pass** | n_ticker_runs=1.0, mean_total_return=0.025704983912548274, mean_sharpe_ratio=1.4123311543145172 | SMOKE (1 claimed setup random_sp500_5 / 2024-01-01_2025-01-01 ticker CI, window shrunk to 2024-01-02..2024-02-29; BaseStrategyIso). Claimed FINSABER-2 setups ['random_sp500_5'] win |
| `stockbench.daily_sim` | required | **pass** | cum_return=-4.00009973998694e-05, sharpe=-11.224972160321824, sortino=0.0 | SMOKE (official run_backtest --symbols AAPL --start 2025-03-03 --end 2025-03-04). Official StockBench window 2025-03-03..2025-03-04 universe=1 dual-agent grok overlay. returncode=0 |
| `fintoolbench.tool_compliance` | required | **pass** | n_questions=2.0, n_with_tool_calls=2.0, tir=1.0 | SMOKE (first 2 official JSONL questions + run_relative_eval.py). Question set n=2 tool_calls=2. RapidAPI/akshare not subscribed — tool outputs are Grok-produced.  |
| `deepfund.fund_arena` | required | **pass** | n_days_ok=1.0, n_days_fail=0.0, decision_count=1.0 | SMOKE (1 ticker AAPL × 1 weekday 2025-04-01; main.py --local-db). Chronological DeepFund --local-db 2025-04-01..2025-04-01 universe=['AAPL'] with OpenAI-compatible Grok YAML. days_ |
| `investorbench.decision` | optional | **skip** | — | skip: docker binary not available (official CLI is `docker run … devon warmup|test|eval`); vLLM server not listening on 127.0.0.1:8000 (chat_vllm_endpoint); Qdrant not listening on |
| `livetradebench.live` | optional | **pass** | n_days_completed=2.0, n_days=2.0, n_days_window=23.0 | SMOKE (official backtest_demo.py --stocks AAPL --start-date 2025-10-01 --end-date 2025-10-02). Official examples/backtest_demo.py window 2025-10-01..2025-10-02 stocks=AAPL exchange |
| `finmcp.tool_mcp` | optional | **skip** | — | skip: benchmark_final.json not in git; fetch HuggingFace DianJin/FinMCP-Bench |
| `vals_finance_agent.research` | optional | **fail** | n_finished=2.0, n_ok=0.0, n_fail=2.0 | SMOKE (first 2 public.txt lines via --question-file; --max-turns 8). Official public.txt protocol n=2 harvested n_finished=2 n_ok=0 n_fail=2 n_inflight=0 model=grok/grok-4.20-0309- |
| `finsearchcomp.search` | optional | **fail** | n_chat=2.0, n_total=635.0, n_questions=635.0 | SMOKE (official chat.py --limit 2 then eval.py). Official FinSearchComp chat+eval model=grok-4.20-0309-non-reasoning chat_rc=0 eval_rc=1 n_chat=2 limit=2. config.yaml pointed at xA |
| `openpm.portfolio_pit` | optional | **skip** | — | skip: dataset/panel/price_panel_5m.parquet missing (HF aslcai/OpenPM-Bench or rebuild); dataset/feature_output/feature_output.ndjson missing |

## `ama.multi_market_live`

- status: `pass`
- protocol_hash: `sha256:492abb4d61041724b1fc113cc55566278663d62ca9017b7ce135e483e4150e49`
- window: `2025-10-22` → `2025-10-22` universe=['AAPL']
- upstream: `POST /trading_action/ + harvest action/*_trading_decisions.json`
- traces: `/workspace/finagent-sandbox/artifacts/ama/smoke/action`

| Metric | Value | Unit | Source |
| --- | --- | --- | --- |
| `n_assets` | 1.0 |  | ama |
| `n_http_ok` | 1.0 |  | ama |
| `n_http_calls` | 1.0 |  | ama |
| `mean_total_return` | 0.0 | pct | ama harvest |
| `mean_sharpe_ratio` | 0.0 |  | ama harvest |
| `mean_max_drawdown` | 0.0 | pct | ama harvest |

Artifacts:
- `metrics_json`: `/workspace/finagent-sandbox/artifacts/ama/smoke/ama_metrics.json`
- `decision_json`: `/workspace/finagent-sandbox/artifacts/ama/smoke/action`

SMOKE (1 ticker (AAPL) × 1 day 2025-10-22; POST /trading_action/). AMA window 2025-10-22..2025-10-22 on 1 assets. HTTP calls 1/1. News vendor keys missing — prices from Yahoo, news empty. Server http://127.0.0.1:45255/trading_action/.

## `finsaber.long_horizon`

- status: `pass`
- protocol_hash: `sha256:eed5906193e833d334ecf21965d2c529898c28a562ed1e64776ce4f3d658cd3f`
- window: `2024-01-02` → `2024-02-29` universe=['CI']
- execution_timing: `next_open`
- costs: `{"commission_per_share": 0.0049, "min_commission": 0.99, "max_commission_rate": 0.01, "slippage_perc": 0.0005, "liquidity_cap_pct": 0.025}`
- upstream: `FINSABER(config).run_iterative_tickers(GrokCliStrategyIso)`
- traces: `/workspace/finagent-sandbox/artifacts/finsaber/smoke`

| Metric | Value | Unit | Source |
| --- | --- | --- | --- |
| `n_ticker_runs` | 1.0 |  | finsaber |
| `mean_total_return` | 0.025704983912548274 |  | finsaber |
| `mean_sharpe_ratio` | 1.4123311543145172 |  | finsaber |
| `mean_max_drawdown` | 2.6407408940799035 |  | finsaber |
| `mean_total_commission` | 3.0968 |  | finsaber |

| Gate | Required | Passed | Actual | Threshold |
| --- | --- | --- | --- | --- |
| `execution_timing_next_open` | False | **True** | next_open | eq next_open |
| `costs_enabled` | False | **True** | True | eq True |
| `not_cherry_pick_universe` | False | **True** | claimed | neq cherry_pick |

Artifacts:
- `metrics_json`: `/workspace/finagent-sandbox/artifacts/finsaber/smoke/finsaber_metrics.json`
- `run_config`: `/workspace/finagent-sandbox/artifacts/finsaber/smoke`
- `log`: `/workspace/finagent-sandbox/artifacts/finsaber/smoke/heartbeat.json`

SMOKE (1 claimed setup random_sp500_5 / 2024-01-01_2025-01-01 ticker CI, window shrunk to 2024-01-02..2024-02-29; BaseStrategyIso). Claimed FINSABER-2 setups ['random_sp500_5'] windows ['2024-01-01_2025-01-01'] via BaseStrategyIso. data_root=/workspace/finance-agent-p0/FINSABER/data/sp500_2000_2025_parquet. Honesty gates recorded on this suite only.

## `stockbench.daily_sim`

- status: `pass`
- protocol_hash: `sha256:dcce8cf36535e3abae938814c738030da4f767e23a0a2a2987c025bfdecb6498`
- window: `2025-03-03` → `2025-03-04` universe=['AAPL']
- costs: `{"commission_bps": 1.0, "slippage_bps": 2.0}`
- upstream: `/workspace/finance-agent-p0/FINSABER/.venv/bin/python -m stockbench.apps.run_backtest --cfg /workspace/finagent-sandbox/artifacts/stockbench/smoke/config.grok.yaml --start 2025-03-03 --end 2025-03-04 --strategy llm_decision --run-id GROK_CLI_SMOKE --llm-profile grok --agent-mode dual --offline --no-summary-llm --symbols AAPL`
- traces: `/workspace/finagent-sandbox/modules/stockbench/storage/reports/backtest`

| Metric | Value | Unit | Source |
| --- | --- | --- | --- |
| `cum_return` | -4.00009973998694e-05 |  | /workspace/finagent-sandbox/modules/stockbench/storage/reports/backtest/GROK_CLI_SMOKE_20260916_174714_130802/metrics.json |
| `max_drawdown` | -4.00009973998694e-05 |  | /workspace/finagent-sandbox/modules/stockbench/storage/reports/backtest/GROK_CLI_SMOKE_20260916_174714_130802/metrics.json |
| `sortino` | 0.0 |  | /workspace/finagent-sandbox/modules/stockbench/storage/reports/backtest/GROK_CLI_SMOKE_20260916_174714_130802/metrics.json |
| `sharpe` | -11.224972160321824 |  | /workspace/finagent-sandbox/modules/stockbench/storage/reports/backtest/GROK_CLI_SMOKE_20260916_174714_130802/metrics.json |
| `volatility_daily` | 2.8284976515673105e-05 |  | /workspace/finagent-sandbox/modules/stockbench/storage/reports/backtest/GROK_CLI_SMOKE_20260916_174714_130802/metrics.json |
| `trades_count` | 1.0 |  | /workspace/finagent-sandbox/modules/stockbench/storage/reports/backtest/GROK_CLI_SMOKE_20260916_174714_130802/metrics.json |
| `trades_notional` | 40008.997599480004 |  | /workspace/finagent-sandbox/modules/stockbench/storage/reports/backtest/GROK_CLI_SMOKE_20260916_174714_130802/metrics.json |
| `sortino_annual` | 0.0 |  | /workspace/finagent-sandbox/modules/stockbench/storage/reports/backtest/GROK_CLI_SMOKE_20260916_174714_130802/metrics.json |
| `volatility` | 0.00044901008219863967 |  | /workspace/finagent-sandbox/modules/stockbench/storage/reports/backtest/GROK_CLI_SMOKE_20260916_174714_130802/metrics.json |

Artifacts:
- `log`: `/workspace/finagent-sandbox/artifacts/stockbench/smoke/run_backtest.log`
- `metrics_json`: `/workspace/finagent-sandbox/modules/stockbench/storage/reports/backtest/GROK_CLI_SMOKE_20260916_174714_130802/metrics.json`

SMOKE (official run_backtest --symbols AAPL --start 2025-03-03 --end 2025-03-04). Official StockBench window 2025-03-03..2025-03-04 universe=1 dual-agent grok overlay. returncode=0 metrics=/workspace/finagent-sandbox/modules/stockbench/storage/reports/backtest/GROK_CLI_SMOKE_20260916_174714_130802/metrics.json. POLYGON/FINNHUB absent; offline_only.

## `fintoolbench.tool_compliance`

- status: `pass`
- protocol_hash: `sha256:55d09ab2ca2c360cc3f5c0fccc9cc0f811ffaa350e537ea324986c44ae491673`
- window: `None` → `None` universe=[]
- upstream: `python -u modules/fintoolbench/code_bench/evaluate/run_relative_eval.py --inputs /workspace/finagent-sandbox/artifacts/fintoolbench/smoke/grok_cli.jsonl --output_dir /workspace/finagent-sandbox/artifacts/fintoolbench/smoke/eval`
- traces: `/workspace/finagent-sandbox/artifacts/fintoolbench/smoke/grok_cli.jsonl`

| Metric | Value | Unit | Source |
| --- | --- | --- | --- |
| `n_questions` | 2.0 |  | fintoolbench |
| `n_with_tool_calls` | 2.0 |  | fintoolbench |
| `tir` | 1.0 |  | evaluator |
| `tesr` | 1.0 |  | evaluator |
| `cer` | 1.0 |  | evaluator |
| `soft_score` | 0.25 |  | evaluator |
| `css` | 0.25 |  | evaluator |
| `tmr` | 0.0 |  | evaluator |
| `imr` | 0.0 |  | evaluator |
| `dmr` | 0.0 |  | evaluator |

| Gate | Required | Passed | Actual | Threshold |
| --- | --- | --- | --- | --- |
| `tmr_lte` | False | **True** | 0.0 | lte 1.0 |
| `imr_lte` | False | **True** | 0.0 | lte 1.0 |
| `dmr_lte` | False | **True** | 0.0 | lte 1.0 |

Artifacts:
- `tool_trace`: `/workspace/finagent-sandbox/artifacts/fintoolbench/smoke/grok_cli.jsonl`
- `metrics_json`: `/workspace/finagent-sandbox/artifacts/fintoolbench/smoke/eval`

SMOKE (first 2 official JSONL questions + run_relative_eval.py). Question set n=2 tool_calls=2. RapidAPI/akshare not subscribed — tool outputs are Grok-produced. 

## `deepfund.fund_arena`

- status: `pass`
- protocol_hash: `sha256:d836374bd7730b407ad9cf3cceaceee3e6774224ccbab11063190685567a20db`
- window: `2025-04-01` → `2025-04-01` universe=['AAPL']
- upstream: `python modules/deepfund/src/main.py --config /workspace/finagent-sandbox/artifacts/deepfund/smoke/grok-buffett.yaml --trading-date 2025-04-01 --local-db`
- traces: `/workspace/finagent-sandbox/artifacts/deepfund/smoke/deepfund.db`

| Metric | Value | Unit | Source |
| --- | --- | --- | --- |
| `n_days_ok` | 1.0 |  | deepfund |
| `n_days_fail` | 0.0 |  | deepfund |
| `decision_count` | 1.0 |  | sqlite |
| `signal_count` | 2.0 |  | sqlite |
| `final_total_assets` | 100000.0 |  | sqlite.portfolio |

Artifacts:
- `log`: `/workspace/finagent-sandbox/artifacts/deepfund/smoke/deepfund.log`
- `metrics_json`: `/workspace/finagent-sandbox/artifacts/deepfund/smoke/harvest.json`
- `decision_db`: `/workspace/finagent-sandbox/artifacts/deepfund/smoke/deepfund.db`

SMOKE (1 ticker AAPL × 1 weekday 2025-04-01; main.py --local-db). Chronological DeepFund --local-db 2025-04-01..2025-04-01 universe=['AAPL'] with OpenAI-compatible Grok YAML. days_ok=1 fail=0. db=/workspace/finagent-sandbox/artifacts/deepfund/smoke/deepfund.db. Supabase not used. ALPHA_VANTAGE_API_KEY=absent (yfinance price fallback).

## `investorbench.decision`

- status: `skip`
- protocol_hash: `sha256:cf8e0b47fe6ad3c8c9a58c40cacc3345fa3d967b265bbf52163e13d4367bb8b7`
- window: `2020-10-01` → `2021-05-06` universe=['HON', 'JNJ', 'MSFT', 'NFLX', 'UVV', 'BTC-USD', 'ETH-USD']
- upstream: `docker run -it -v .:/workspace --network host devon warmup && docker run -it -v .:/workspace --network host devon test && docker run -it -v .:/workspace --network host devon eval`

skip: docker binary not available (official CLI is `docker run … devon warmup|test|eval`); vLLM server not listening on 127.0.0.1:8000 (chat_vllm_endpoint); Qdrant not listening on 127.0.0.1:6333 (vector memory); official protocol also needs OPENAI embeddings model text-embedding-3-large (not an xAI model) plus a compiled configs/main.json from Pkl; no smaller official smoke is documented beyond warmup|test|eval. Not inventing a non-docker protocol.

## `livetradebench.live`

- status: `pass`
- protocol_hash: `sha256:8e919171b240c171e694f08a1dec0cc23d3b1a3d53edcec6d0b8aaa211143bfb`
- window: `2025-10-01` → `2025-10-02` universe=['AAPL']
- upstream: `/workspace/finagent-sandbox/venvs/v2_livetrade/bin/python /workspace/finagent-sandbox/modules/livetradebench/examples/backtest_demo.py --exchanges stock --start-date 2025-10-01 --end-date 2025-10-02 --stocks AAPL --stock-count 1`
- traces: `/workspace/finagent-sandbox/artifacts/livetradebench/smoke`

| Metric | Value | Unit | Source |
| --- | --- | --- | --- |
| `n_days` | 2.0 |  | backtest_demo |
| `n_days_completed` | 2.0 |  | backtest_demo |
| `n_days_window` | 23.0 |  | backtest_demo |
| `return_percentage` | 0.4269999999999982 |  | backtest_demo |
| `total_return` | 0.004269999999999982 |  | backtest_demo |

Artifacts:
- `log`: `/workspace/finagent-sandbox/artifacts/livetradebench/smoke/backtest_demo.log`
- `results_json`: `/workspace/finagent-sandbox/artifacts/livetradebench/smoke/backtest_results.json`
- `models_data`: `/workspace/finagent-sandbox/modules/livetradebench/backend/models_data_init.json`

SMOKE (official backtest_demo.py --stocks AAPL --start-date 2025-10-01 --end-date 2025-10-02). Official examples/backtest_demo.py window 2025-10-01..2025-10-02 stocks=AAPL exchanges=stock model=xai/grok-4.20-0309-non-reasoning returncode=0.    • stock/Grok-eval: ✅ allocations applied |  | 🎯 STOCK RESULTS | ---------------------------------------- |    #1 Grok-eval (xai/grok-4.20-0309-non-reasoning): +0.43%  ($1,000.00 → $1,004.27) |  | 🏅 OVERALL BEST | ---------------------------------------- |    Agent:  Grok-eval |    Market: stock |    Return: +0.43% |  | 📊 PERFORMANCE STATS | ---------------------------------------- |    Total Ag

## `finmcp.tool_mcp`

- status: `skip`
- protocol_hash: `sha256:4b60f936d1d34696fc0e57dd2c1ec904913b788b393d85a69971638123afcdee`
- window: `None` → `None` universe=[]
- upstream: `python DianJin-TIR/infer/inference_api.py && python DianJin-TIR/eval/evaluation.py --eval_data_path=<pred.json>`

skip: benchmark_final.json not in git; fetch HuggingFace DianJin/FinMCP-Bench

## `vals_finance_agent.research`

- status: `fail`
- protocol_hash: `sha256:8e38cb5eccbc27f602a57ed869c13df6a81c1a9881bcd2868d18288b16bb9676`
- window: `None` → `None` universe=[]
- upstream: `/workspace/finagent-sandbox/venvs/v2_vals/bin/python -m finance_agent.run_agent --question-file /workspace/finagent-sandbox/artifacts/vals_finance_agent/smoke/public_smoke.txt --model grok/grok-4.20-0309-non-reasoning --parallelism 1 --max-turns 8 --tools parse_html_page retrieve_information`
- traces: `/workspace/finagent-sandbox/modules/vals_finance_agent/logs`

| Metric | Value | Unit | Source |
| --- | --- | --- | --- |
| `n_questions` | 2.0 |  | public.txt |
| `n_finished` | 2.0 |  | q*/result.json |
| `n_ok` | 0.0 |  | q*/result.json |
| `n_fail` | 2.0 |  | q*/result.json |
| `n_inflight` | 0.0 |  | q*/agent.log |
| `n_success` | 0.0 |  | q*/result.json |
| `n_error` | 2.0 |  | q*/result.json |

Artifacts:
- `log`: `/workspace/finagent-sandbox/artifacts/vals_finance_agent/smoke/finance_agent.log`
- `harvest_json`: `/workspace/finagent-sandbox/artifacts/vals_finance_agent/smoke/harvest.json`
- `results_json`: `/workspace/finagent-sandbox/modules/vals_finance_agent/logs/finance/grok-4.20-0309-non-reasoning/2026-09-16_17-50-33_f157e5/results.json`

SMOKE (first 2 public.txt lines via --question-file; --max-turns 8). Official public.txt protocol n=2 harvested n_finished=2 n_ok=0 n_fail=2 n_inflight=0 model=grok/grok-4.20-0309-non-reasoning returncode=0. tools_enabled=['parse_html_page', 'retrieve_information']; tools_skipped=['web_search', 'edgar_search']. CONTINUE complete: unique q*/result.json 2/2 finished. Official accuracy vs gated 537 needs VALS_API_KEY + platform GT (not present); reporting completion counts only. No fake accuracy. TAVILY_API_KEY and/or SEC_EDGAR_API_KEY absent — skipped those tools honestly. tail= | Processing questions: 100%|██████████| 2/2 [01:58<00:00, 61.88s/it] | Processing questions: 100%|██████████| 2/2 [01:58<00:00, 59.03s/it] |  | FAIL Question failed: How has US Steel addressed its planned merger with Nippon Steel and its effect on its business operations? |    Turns: 8 |    Error: [MaxTurnsExceeded] Max turns (8) reached |  |  | FAIL Question failed: How has Netflix's (NASDAQ: N

## `finsearchcomp.search`

- status: `fail`
- protocol_hash: `sha256:3f5c55c1ab41eddeb4677c0d05968f48f1490f050f9169a469723a4abc8fa642`
- window: `None` → `None` universe=['global', 'greater_china']
- upstream: `/workspace/finagent-sandbox/venvs/v2_finsearch/bin/python /workspace/finagent-sandbox/modules/finsearchcomp/finsearchcomp/chat/chat.py --model_name grok-4.20-0309-non-reasoning --input_file /workspace/finagent-sandbox/modules/finsearchcomp/data/finsearchcomp_data.json --output_path /workspace/finagent-sandbox/artifacts/finsearchcomp/smoke/chat.json --limit 2 && /workspace/finagent-sandbox/venvs/v2_finsearch/bin/python /workspace/finagent-sandbox/modules/finsearchcomp/finsearchcomp/eval/eval.py --model_name grok-4.20-0309-non-reasoning --input /workspace/finagent-sandbox/artifacts/finsearchcomp/smoke/chat.json --output /workspace/finagent-sandbox/artifacts/finsearchcomp/smoke/eval.json`
- traces: `/workspace/finagent-sandbox/artifacts/finsearchcomp/smoke`

| Metric | Value | Unit | Source |
| --- | --- | --- | --- |
| `n_questions` | 635.0 |  | chat.json |
| `n_chat` | 2.0 |  | chat.json |
| `n_total` | 635.0 |  | chat.json |
| `n_with_response` | 2.0 |  | chat.json |

Artifacts:
- `chat_log`: `/workspace/finagent-sandbox/artifacts/finsearchcomp/smoke/chat.log`
- `eval_log`: `/workspace/finagent-sandbox/artifacts/finsearchcomp/smoke/eval.log`
- `chat_json`: `/workspace/finagent-sandbox/artifacts/finsearchcomp/smoke/chat.json`

SMOKE (official chat.py --limit 2 then eval.py). Official FinSearchComp chat+eval model=grok-4.20-0309-non-reasoning chat_rc=0 eval_rc=1 n_chat=2 limit=2. config.yaml pointed at xAI; openai_api AzureOpenAI glue-patched to OpenAI(). Traceback (most recent call last): |   File "/workspace/finagent-sandbox/modules/finsearchcomp/finsearchcomp/eval/eval.py", line 382, in <module> |     main() |     ~~~~^^ |   File "/workspace/finagent-sandbox/modules/finsearchcomp/finsearchcomp/eval/eval.py", line 350, in main |     result = process_file(item, model, temp_output) |   File "/workspace/finagent-sandbox/modules/finsearchcomp/finsear

## `openpm.portfolio_pit`

- status: `skip`
- protocol_hash: `sha256:371a1181bceb85772e9a6a2a5d2391783ad09aea7df1fad4c7f6fdb4d0781009`
- window: `2026-03-02` → `2026-03-03` universe=['SP500_PIT']
- execution_timing: `60min_post_open_then_hold`
- upstream: `python -m agents.portfolio --provider llm_tiered --llm-provider openai --model <model> --start-date 2026-03-02 --end-date 2026-05-01 --api-key-env XAI_API_KEY --base-url https://api.x.ai/v1`

skip: dataset/panel/price_panel_5m.parquet missing (HF aslcai/OpenPM-Bench or rebuild); dataset/feature_output/feature_output.ndjson missing

## Live runs

- finsaber.long_horizon lowvol_sp500_5/2025-01-01_2026-01-01 ticker=? as_of=? bars=? hb_done=30/30 disk_done=30/30 hb_age=3186s STALL

## Notes

Parallel scorecard for Grok CLI. Required benches drive completeness; optional benches skip if deps are missing. Per-suite pass/fail is not a veto. backend=api model=grok-4.20-0309-non-reasoning. SMOKE: tiny official samples (same entrypoints).

