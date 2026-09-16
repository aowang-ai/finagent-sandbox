# Optional suite status

Locked coverage: [`GOAL.md`](../../GOAL.md). Completeness (`admission.decision`) for the Grok CLI product scorecard uses the **required five** (`REQUIRED_SUITE_IDS`). Optional ids live in `OPTIONAL_SUITE_IDS` and appear on the same `reports/GROK_CLI_SCORECARD.*` with `tier=optional`. They do not HOLD promote.

Clone with `./scripts/clone_modules.sh`. Doctor **warns** (does not fail) if an optional module is absent.

Historical required `SuiteResult`s and `reports/GROK_CLI_SCORECARD.*` metric values were **not** rewritten this pass.

## 2026-09-14 real-run outcomes (Grok CLI / xAI `grok-4.20-0309-non-reasoning`)

| suite_id | Status | Official entry | What happened |
| --- | --- | --- | --- |
| `investorbench.decision` | **skip** | `docker run … devon warmup\|test\|eval` | docker binary missing; vLLM not on `127.0.0.1:8000`; Qdrant not on `127.0.0.1:6333`; official protocol also wants OpenAI `text-embedding-3-large` (not an xAI model). No non-docker protocol invented. |
| `finmcp.tool_mcp` | **skip** | `DianJin-TIR/infer/inference_api.py` + `eval/evaluation.py` | `benchmark_final.json` present (36 322 369 bytes). Qieman MCP URL + schema missing (`MCP_SERVER_URL`/`QIEMAN_MCP_SERVER_URL` unset; `MCP_SCHEMA_PATH` missing). Not inventing a no-MCP protocol. |
| `vals_finance_agent.research` | **fail** | `python -m finance_agent.run_agent --question-file data/public.txt` | Official public.txt (50). CONTINUE complete. Harvest unique `q*/result.json`: **n_finished=50 n_ok=15 n_fail=35 n_inflight=0**. Tools: `parse_html_page` + `retrieve_information`. `TAVILY_API_KEY` / `SEC_EDGAR_API_KEY` / `VALS_API_KEY` absent (web_search + edgar_search + gated 537 skipped honestly). Fail reasons: 34 `MaxTurnsExceeded` + q025 `AioRpcError` RESOURCE_EXHAUSTED. Workers dead; not restarted. No fake accuracy. Log: `artifacts/vals_finance_agent/finance_agent.log`. |
| `finsearchcomp.search` | **fail** | official `finsearchcomp/chat/chat.py` + `eval/eval.py`, `--limit 0` (all 635; documented) | `config.yaml` pointed at xAI; AzureOpenAI glue-patched to `OpenAI()`. Chat **n_chat=635 / n_total=635** (`n_with_response=635`, live xAI HTTP 200s). Official `eval.py` attempted then crashed at item 4/635: `KeyError: 'tags'` in `get_judge_user_input`. `eval.json` has **n_eval=3** judged rows (T2/T3 scores 0.0). Upstream `data/finsearchcomp_data.json` has **tags=0/635**; argparse has no skip-T1 / tags flag. Not inventing a custom judge. No fake 635-question accuracy. |
| `openpm.portfolio_pit` | **skip** | `python -m agents.portfolio --provider llm_tiered` 2026-03-02..2026-05-01 | Official `llm_tiered` **SIGKILL/OOM** (returncode=-9) loading `dataset/feature_output/feature_output.ndjson` (2.6 GiB → ~7.3 GiB RSS) on this 15 GiB host with 0 swap. Stamp: `artifacts/openpm/oom_sigkill.json`. Not inventing `--max-bars` / universe subset. |
| `livetradebench.live` | **pass** | official `examples/backtest_demo.py` 2025-10-01..2025-11-01 | Official 23-weekday window complete (prior 2 days 2025-10-01..02 + continue 21 days 2025-10-03..31). **n_days_completed=23 / n_days_window=23**, last_date=2025-10-31, final $1008.87, return_percentage=0.887%. Upstream has no portfolio-state resume flag; continue segment cash restarted at $1000. News 429 fail-fast (empty news, allocations still ran). Not a 1-day invention. Log: `artifacts/livetradebench/backtest_demo.log`. |

Harvest / resume of official remaining work: `python scripts/v2_suite_ops.py {progress,harvest,resume}`. EnvAdapters stay in `adapters/{suite}.py`; patches and harvest live in `adapters/v2_ops/`.

## Adapter wiring

| suite_id | Clone | Adapter | Notes |
| --- | --- | --- | --- |
| `investorbench.decision` | `modules/investorbench` ← [felis33/INVESTOR-BENCH](https://github.com/felis33/INVESTOR-BENCH) | `adapters/investorbench.py` | skip names docker/vLLM/Qdrant |
| `livetradebench.live` | `modules/livetradebench` ← [ulab-uiuc/live-trade-bench](https://github.com/ulab-uiuc/live-trade-bench) | `adapters/livetradebench.py` | official backtest_demo; harvest days_completed |
| `finmcp.tool_mcp` | `modules/finmcp` ← [aliyun/qwen-dianjin](https://github.com/aliyun/qwen-dianjin) | `adapters/finmcp.py` | benchmark present; MCP URL/schema missing |
| `vals_finance_agent.research` | `modules/vals_finance_agent` ← [vals-ai/finance-agent](https://github.com/vals-ai/finance-agent) | `adapters/vals_finance_agent.py` | unique-qid harvest of partial public.txt |
| `finsearchcomp.search` | `modules/finsearchcomp` ← [randomtutu/FinSearchComp](https://github.com/randomtutu/FinSearchComp) | `adapters/finsearchcomp.py` | xAI config + official chat+eval limit=0 |
| `openpm.portfolio_pit` | `modules/openpm` ← [aslcai/OpenPM-Bench](https://github.com/aslcai/OpenPM-Bench) | `adapters/openpm.py` | OOM skip after real llm_tiered attempt |

## CONTINUE (2026-09-14 evening) — STEER #10 **final** harvest

Prior Grok (STEER #9 PID 2768377) exited while waiting on q045. Vals workers **dead**. **Did not restart** Vals. Required scorecard + Sep-12 five `SuiteResult`s still untouched.

| suite_id | Continue action | Harvest |
| --- | --- | --- |
| `finsearchcomp.search` | official `chat.py --limit 0` then official `eval.py` judge | **done** n_chat **635/635** n_with_response=635. Judge crashed item 4/635 `KeyError: 'tags'`. n_eval=3. Status **fail**. No custom judge. |
| `vals_finance_agent.research` | official `public.txt`; unique `q*/result.json`; do not restart dead workers | **done** n_finished **50/50** (15 ok / 35 fail / 0 inflight). Status **fail** (complete, 35 errors). Fail: 34 `MaxTurnsExceeded` + q025 `AioRpcError` RESOURCE_EXHAUSTED. |
| `livetradebench.live` | official `backtest_demo.py` window 2025-10-01..2025-11-01 | **done** n_days_completed **23/23** last_date=2025-10-31 ret=0.887%. Status **pass**. |
| `openpm.portfolio_pit` | **skip kept** | no stream/chunk on official `llm_tiered`; OOM stamp 7.3 GiB RSS / 0 swap |
| `finmcp.tool_mcp` / `investorbench.decision` | **skip kept** | Qieman MCP URL+schema missing; docker/vLLM/Qdrant missing |

CONTINUE three targets are finished or honestly blocked. **DONE.**

## What is not done

- Official FinSearchComp judge for all 635 (chat complete; eval.py `KeyError: 'tags'` after 3 — upstream data has tags=0/635, no official flag).
- OpenPM llm_tiered on this 15 GiB host (OOM; no official stream/chunk).
- InvestorBench / FinMCP (missing docker/vLLM/Qdrant / Qieman MCP).
- Claude/Codex runners, Herculean, PortBench.
- Vals official accuracy vs gated 537 (`VALS_API_KEY` + platform GT absent; public.txt 50 reported as completion counts only).

`--suites all` (default) is the required five. `--suites optional` runs the optional six. Both land on `reports/GROK_CLI_SCORECARD.*` with a required/optional tier.
