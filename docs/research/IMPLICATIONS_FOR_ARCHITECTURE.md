# Implications for architecture

> Superseded: scoring is parallel scorecard (see GOAL.md). FINSABER is not a global kernel.

Research: [`AGENT_PLUG_IN_SURVEY.md`](AGENT_PLUG_IN_SURVEY.md), [`PLUG_IN_MATRIX.md`](PLUG_IN_MATRIX.md). **Do not rewrite adapters in this pass** except leaving stubs as honest `skip`. This note is what to change when we wire for real.

## Keep

These claims in `ARCHITECTURE.md` / `adapters/base.py` matched the evidence:

- We are a **composition layer**. Upstream engines stay source of truth for fills, judges, graphs.
- **Parallel scorecard:** FINSABER honesty is a suite-level metric; AMA / StockBench / DeepFund / FinToolBench are scored alongside it (`evaluate_admission` is completeness only).
- Prefer **subprocess of official CLI** (or HTTP to AMA) over reimplementing engines.
- `ProtocolSpec` hashes the exam paper (dates, universe, vintage, costs, timing), not answers.
- `Observation.raw` / `Decision.raw` and `SuiteResult.traces_path` are the right escape hatches.
- `AmaHttpShim` is the correct depth for AMA (`adapters/ama.py`).

## Change (design, not code yet)

### 1. Stop implying one `decide()` call is the native loop

`ARCHITECTURE.md` sequence diagram shows every Env calling `AgentAdapter.decide`. Evidence: FinToolBench’s official entry **never calls an agent** (`modules/fintoolbench/code_bench/evaluate/run_relative_eval.py`); DeepFund/StockBench official CLIs never import our adapter.

**Change:** document two legal Env modes:

| Mode | When | `decide()` |
| --- | --- | --- |
| **Boundary wrap** | FINSABER `on_data`, AMA HTTP, StockBench `on_bar`, DeepFund injected node | Called at *their* cadence |
| **Artifact compose** | FinToolBench JSONL; DeepFund/StockBench black-box CLI | Called by *us* while producing files, or not at all (harvest-only) |

`EnvAdapter.run` remains the only thing that must return `SuiteResult`. Keep `skipped_suite` until a mode is wired.

### 2. Treat `Decision.action` as AMA-shaped LCD, not a universal enum

Do not extend `Decision` into a union of all upstream objects in this pass. When wiring, **per-Env mappers** (already started as `AmaHttpShim`) must own vocabulary:

| Suite | Mapper target | Source |
| --- | --- | --- |
| AMA | `recommended_action ∈ {BUY,SELL,HOLD}` | `modules/ama/README.md` |
| FINSABER | `framework.buy/sell(date, ticker, price, qty)` | `backtest_framework_iso.py` |
| StockBench | per-symbol `{action: increase\|decrease\|hold\|close, target_cash_amount}` | `decision_agent_v1.txt` |
| DeepFund | `graph.schema.Decision` (`Buy`/`Sell`/`Hold`, `shares`) | `schema.py:Decision` |
| FinToolBench | `tool_calls[{tool_name, step, output}]` + `execution_result` | `metrics_capability.py` |

`Decision.allocations` / `tool_calls` / `raw` stay; EnvAdapters must **fail closed** if they cannot map (HOLD / skip / error), not coerce `increase` → `BUY` silently.

### 3. First-class bridges (implementation order)

Same order as the survey. Still no adapter rewrites now.

1. HTTP server around `AmaHttpShim` + `agents.json` URL.
2. `FinsaberEnvAdapter.run`: `BaseStrategyIso` that calls `decide`; `next_open` + costs; evaluate `HONESTY_GATES` against `run_config.json`. Second arg of `on_data` is **today’s dict** (call site L272), despite stub parameter name `data_loader`.
3. FinToolBench: write JSONL from `decide()`, subprocess `run_relative_eval.py`.
4. StockBench: wrap `on_bar` or document model-only CLI as `notes` (not “our agent”).
5. DeepFund: harvest `--local-db` first; PM inject later.

Hermes/OpenClaw are **AgentAdapter implementations**, not new `suite_id`s.

### 4. Traces: harvest native, don’t invent a mega-schema

Do not require ClawBench Partner Trace or Hermes ShareGPT as the report’s only trace format. Per suite, set `traces_path` / `Artifact.kind`:

| Suite | Native trace | kind (existing or already listed in ARCHITECTURE) |
| --- | --- | --- |
| FINSABER | `trades.csv`, `orders.csv`, `llm_costs.csv` | as today |
| AMA | `action/*_trading_decisions.json` | decision JSON |
| StockBench | detailed trade JSON when enabled | as today |
| DeepFund | `decision` / `signal` tables | `decision_db` |
| FinToolBench | result JSONL `tool_calls` | `tool_trace` |
| Hermes-backed agent (optional extra) | `trajectory_samples.jsonl` | extra artifact, not a suite |

If we later emit ClawBench JSONL, it is an **export**, not admission input.

### 5. `capabilities()` should mean “which contracts this binary can honor”

Today: empty = every suite. Evidence: FinTool needs RapidAPI-shaped tools; FINSABER needs date-level bars; AMA needs HTTP. An OpenClaw Gateway with browser tools is not a FinTool agent.

**Change when wiring:** `capabilities()` returns suite ids the adapter **implemented mappers for**, not marketing willingness. Doctor’s dummy adapter may stay empty.

### 6. Observation: keep LCD, fill `raw` per Env

Do not explode `Observation` into StockBench features + DeepFund `analyst_signals` in v1. Contract: EnvAdapter **must** copy the native payload into `raw` (AMA shim already does). Agents that need dual-agent fields read `raw`. Typed fields stay AMA/FINSABER-shaped (as_of, symbols, prices, news, filings, portfolio, query, tools).

### 7. What not to add

- OpenClaw `AgentHarnessV2` in this repo.
- ClawBench as a global gate or as a sixth required suite.
- A second fill model or Sharpe.
- Forking DeepFund/StockBench prompts into `adapters/`.
- Claiming bitwise paper reproduction (`STATUS.md` already forbids this).

## Tiny doc debt (optional later)

- `ARCHITECTURE.md` table “FINSABER `on_data(date, today_data, framework)`” matches docs/call site; the **stub** still says `data_loader`. Cite both if we mention the symbol.
- `adapters/finsaber.py` wrap-plan already uses `today_data` — keep it; it matches the call site.
- Hermes `batch_runner.py` flags differ between [batch-processing](https://hermes-agent.nousresearch.com/docs/user-guide/features/batch-processing) (`--dataset_file`) and [python-library](https://hermes-agent.nousresearch.com/docs/guides/python-library) (`--input`/`--output`). Unresolved until someone reads that file.

## Suggested ARCHITECTURE.md pointer

Add a short subsection under “One AgentAdapter, many suites” linking here, stating: *LCD is AMA-shaped; each EnvAdapter is a native-surface translator; runtime harnesses (OpenClaw/Hermes) are AgentAdapter backends, not exam rooms.*
