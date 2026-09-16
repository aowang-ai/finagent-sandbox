# Agent plug-in survey

> Superseded: scoring is parallel scorecard (see GOAL.md). FINSABER is not a global kernel.

**Question:** when I already have an agent, how do I plug it into an evaluation system?

**Date:** 2026-09-12. **Rule:** every major claim cites a URL fetched this session or a local `path:symbol`. Nothing here is an invented API.

## Method

- **OpenClaw / ClawBench / Hermes:** official docs and GitHub READMEs fetched over HTTP. No local clone of those repos (they are large). If a URL 404s, it is marked.
- **Finance modules:** read under `modules/` (gitignored clones already present).
- **TradingAgents:** README only (`https://github.com/TauricResearch/TradingAgents`). Not cloned.
- **Cost labels** (`S`/`M`/`L`/`XL`) are engineering estimates from surface complexity, not measured person-days.

Citation form: `[label](url)` for fetched pages; `` `path:symbol` `` for local code.

---

## 中文结论（先读这段）

**Runtime harness ≠ eval harness。** OpenClaw 文档里 *harness* 是「一轮 agent turn 的底层执行器」；ClawBench（仓库 URL 仍是 `openclaw/shellbench`）才是评测。Hermes 的循环在 `AIAgent.run_conversation()`；评测/数据出口是 ShareGPT JSONL + `batch_runner.py`，不是一个「把任意 agent 送进我们考场」的官方入口。

**野外真实插拔面只有五类：** HTTP 协议、策略子类、轨迹 JSONL、框架节点注册、封闭工作流（只能换模型）。五个 `modules/*` 各自占一类，**没有**一个 LCD 能让 OpenClaw/Hermes 原样坐完全部考试。

**对本仓库的含义：** `AgentAdapter.decide(Observation) → Decision` 是有用的最低公分母（最接近 AMA 的 BUY/SELL/HOLD），但相对 StockBench 的 per-symbol `increase|decrease|hold|close`、FINSABER 的 `framework.buy/sell`、FinToolBench 的多步 `tool_calls`、DeepFund 的 LangGraph 日循环，它过度简化。正确做法是 **每个考场保留官方循环，在边界翻译**，而不是让 `decide()` 假装拥有所有循环。

推荐先做的桥（工程顺序）：① AMA HTTP shim ② FINSABER `BaseStrategyIso` 包装（长周期诚实套件，不是全局内核）③ FinToolBench JSONL 发射器 ④ StockBench `on_bar` 翻译 ⑤ DeepFund 只收割 traces 或替换 PM 节点。OpenClaw `AgentHarnessV2` 是**他们的**运行时插件面，不是我们的考场入口。

---

## 1. Runtime harness vs eval harness

A **runtime harness** owns one prepared model loop: prompt in, tool calls, finished turn out. OpenClaw states this in two places that agree:

> An **agent harness** is the low level executor for one prepared OpenClaw agent turn. It is not a model provider, not a channel, and not a tool registry.  
> — [docs.openclaw.ai/plugins/sdk-agent-harness](https://docs.openclaw.ai/plugins/sdk-agent-harness)

> An **agent runtime** owns one prepared model loop: it receives the prompt, drives model output, handles native tool calls, and returns the finished turn to OpenClaw. […] A **harness** is the implementation that provides an agent runtime (code term).  
> — [docs.openclaw.ai/concepts/agent-runtimes](https://docs.openclaw.ai/concepts/agent-runtimes)

An **eval harness** owns the exam: tasks, isolation, scoring, reliability stats. ClawBench (published at `github.com/openclaw/shellbench`) scores *from execution traces*, not just final output, and publishes a partner JSONL interchange so a third-party runner can be scored without embedding OpenClaw ([README](https://github.com/openclaw/shellbench), [PARTNER_TRACE_SPEC.md](https://raw.githubusercontent.com/openclaw/shellbench/main/PARTNER_TRACE_SPEC.md)).

Hermes uses the word *loop* / *AIAgent* for the runtime ([agent-loop docs](https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop)) and *trajectory* / *batch_runner* for offline capture ([trajectory-format](https://hermes-agent.nousresearch.com/docs/developer-guide/trajectory-format)). Its `evals/` tree is **product regression probes** (gateway, compaction, token accounting), not a public “bring your agent” bench. Requesting `https://raw.githubusercontent.com/NousResearch/hermes-agent/main/evals/README.md` returned **404**; the directory listing exists at [github.com/NousResearch/hermes-agent/tree/main/evals](https://github.com/NousResearch/hermes-agent/tree/main/evals).

This finance repo is an **eval composition layer**, not a runtime: `ARCHITECTURE.md` says we wrap upstream engines and harvest official artifacts. Confusing the two layers is how a personal assistant (OpenClaw/Hermes) gets mistaken for an exam room.

---

## 2. Personal / general agent runtimes

### 2.1 OpenClaw

**What “harness” means to them:** runtime turn executor. Register `AgentHarnessV2` via `api.registerAgentHarness`; implement `supports(ctx)` and `async runAttempt(params)` ([registration](https://docs.openclaw.ai/plugins/sdk-agent-harness/registration)). Core still owns provider/model, auth (unless `authBootstrap: "harness"`), transcript file, workspace, sandbox, tool policy, channel delivery, fallback ([core-ownership](https://docs.openclaw.ai/plugins/sdk-agent-harness/core-ownership)).

Do **not** register a harness just to add an LLM API — that is a [provider plugin](https://docs.openclaw.ai/plugins/sdk-provider-plugins) (`api.registerProvider` + catalog). Docs: “Third-party harness installation is experimental. Prefer provider plugins until you need a native session runtime.” ([sdk-agent-harness](https://docs.openclaw.ai/plugins/sdk-agent-harness))

**How a third party attaches a custom model/runtime/agent:**

| Intent | Official surface | Citation |
| --- | --- | --- |
| New LLM HTTP API | Provider plugin (`registerProvider`, `catalog`, optional `resolveDynamicModel`) | [sdk-provider-plugins](https://docs.openclaw.ai/plugins/sdk-provider-plugins) |
| Native session runtime (Codex-like daemon) | `AgentHarnessV2.runAttempt` | [registration](https://docs.openclaw.ai/plugins/sdk-agent-harness/registration) |
| Skills / tools | Plugin SDK + ClawHub | [openclaw README](https://github.com/openclaw/openclaw) |

**How they export trajectories / traces:** OpenClaw transcript is the compatibility layer for history, search, `/new`/`/reset` ([sessions-and-results](https://docs.openclaw.ai/plugins/sdk-agent-harness/sessions-and-results)). For **eval**, ClawBench wants Partner Trace Spec JSONL: `harness`, `model`, `config`, `plugins`, `skills`, `prompts`, `transcript.messages[]` with `tool_calls`, `artifacts`, `redaction` ([PARTNER_TRACE_SPEC.md](https://raw.githubusercontent.com/openclaw/shellbench/main/PARTNER_TRACE_SPEC.md)). Minimum fallback is `trace_id` + `transcript.messages`.

**Official “bring your agent to our bench” path:** **yes, for ClawBench**, not for OpenClaw-the-assistant. ClawBench README: “If you're building an agent framework and want your runs scored by ClawBench, you don't need to integrate with OpenClaw — you just emit traces in this format.” ([shellbench README](https://github.com/openclaw/shellbench))

**Naming conflict (do not paper over):**

- Fetched repo URL: `https://github.com/openclaw/shellbench` (page title “openclaw/shellbench”, README H1 **ClawBench**).
- Same README clone line: `git clone git@github.com:openclaw/clawbench.git && cd clawbench`.
- I did **not** verify whether `github.com/openclaw/clawbench` exists as a separate repo or redirect. Treat `shellbench` as the URL that loaded; treat **ClawBench** as the product name in that README.

OpenClaw product README: “Models and agent harnesses (Claude, Codex, local models) are plugins you can swap without changing anything else.” ([github.com/openclaw/openclaw](https://github.com/openclaw/openclaw))

### 2.2 Hermes Agent (Nous)

**What “harness” means to them:** they rarely use *harness*. The runtime is `AIAgent`; `run_agent.py` is a facade; the loop is `agent/conversation_loop.py` ([agent-loop](https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop), [architecture](https://hermes-agent.nousresearch.com/docs/developer-guide/architecture)). Two entry points:

```python
response = agent.chat("...")
result = agent.run_conversation(user_message="...", system_message=None, conversation_history=None, task_id="...")
```

`chat()` wraps `run_conversation()` and returns `final_response`. Internal messages are OpenAI-style `role`/`content`/`tool_calls`. Default iteration budget 500 (`agent.max_turns`). Tools: sequential if one, thread pool if many ([agent-loop](https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop)).

**How a third party attaches a custom model/runtime/agent:**

| Intent | Official surface | Citation |
| --- | --- | --- |
| OpenAI-compatible endpoint | Custom provider, or plugin under `plugins/model-providers/<name>/` calling `register_provider(profile)` | [adding-providers](https://hermes-agent.nousresearch.com/docs/developer-guide/adding-providers) |
| Native non-OpenAI protocol | New `api_mode` + `agent/<provider>_adapter.py` | same |
| Embed in your app | `from run_agent import AIAgent` (no supported PyPI wheel) | [python-library](https://hermes-agent.nousresearch.com/docs/guides/python-library) |
| Tools / MCP / skills | `enabled_toolsets` / `disabled_toolsets`; MCP docs; agentskills.io | [architecture](https://hermes-agent.nousresearch.com/docs/developer-guide/architecture), [README](https://github.com/NousResearch/hermes-agent) |

**How they export trajectories:** ShareGPT-compatible JSONL ([trajectory-format](https://hermes-agent.nousresearch.com/docs/developer-guide/trajectory-format)):

| File | When |
| --- | --- |
| `trajectory_samples.jsonl` | `completed=True` |
| `failed_trajectories.jsonl` | `completed=False` |

CLI/interactive record: `{conversations, timestamp, model, completed}`. Batch runner adds `prompt_index`, `metadata`, `api_calls`, `toolsets_used`, `tool_stats`. Batch docs show `conversations[].from` / `.value` (ShareGPT) ([batch-processing](https://hermes-agent.nousresearch.com/docs/user-guide/features/batch-processing)). The agent loop internally uses OpenAI `role`/`content`. **Two shapes exist; do not assume they are identical without a converter.** Session DB (`~/.hermes/state.db`) is separate: “Batch runner and RL trajectories are NOT stored here” ([session-storage](https://hermes-agent.nousresearch.com/docs/developer-guide/session-storage)).

Enable: `AIAgent(..., save_trajectories=True)` ([python-library](https://hermes-agent.nousresearch.com/docs/guides/python-library)). Batch:

```text
python batch_runner.py --dataset_file=data/eval_suite.jsonl --run_name=eval_gpt4 --model=openai/gpt-4o
```

Python-library page also shows `python batch_runner.py --input prompts.jsonl --output results.jsonl`. Flag names **differ between pages**; I did not run `batch_runner.py --help`. Treat `--dataset_file` / `--run_name` as the batch-processing page contract and `--input` / `--output` as the library page shorthand, unresolved without source.

**Official “bring your agent to our bench” path:** **no public partner-agent admission.** `evals/` is first-party runtime tests. Trajectory JSONL is for training/debug/RL, not a scored finance exam. Hermes can *be* the agent under someone else’s bench (library + FastAPI example is the closest plug).

Hermes FastAPI sample is an HTTP agent:

```python
@app.post("/chat")
async def chat(request: ChatRequest):
    agent = AIAgent(...)
    return {"response": agent.chat(request.message)}
```

([python-library](https://hermes-agent.nousresearch.com/docs/guides/python-library)) — same pattern as AMA, different path and body.

### 2.3 Optional contrast (only what is needed)

**LangGraph (as used here, not a generic “AgentAdapter” page):** DeepFund compiles `StateGraph(FundState)` and registers nodes through `AgentRegistry.register_agent` (`modules/deepfund/src/graph/workflow.py:AgentWorkflow`, `modules/deepfund/src/agents/registry.py:AgentRegistry`). TradingAgents README: `TradingAgentsGraph().propagate(ticker, date)` returns a decision; LLM is swapped via `config["llm_provider"]` ([TradingAgents README](https://github.com/TauricResearch/TradingAgents)). I did **not** fetch LangGraph’s own `AgentAdapter` class docs.

**MCP:** OpenClaw harnesses report a native MCP inventory ([sdk-agent-harness](https://docs.openclaw.ai/plugins/sdk-agent-harness)); Hermes has `tools/mcp_tool.py` and MCP docs ([architecture](https://hermes-agent.nousresearch.com/docs/developer-guide/architecture)). MCP is a **tool adapter**, not an eval admission API.

**OpenAI Agents SDK tracing:** not fetched this session; not required once ClawBench Partner Trace + Hermes JSONL cover the “export traces for offline scoring” pattern.

---

## 3. Finance modules under `modules/`

For each: who owns the loop, native plug-in surface, can OpenClaw/Hermes sit it without rewriting.

### 3.1 AMA — HTTP protocol

**Loop owner:** the testbed (`modules/ama/README.md`). Agents must already be HTTP servers. Orchestrator: `modules/ama/testbed/get_daily_action.py:call_single_trading_api`.

**Native plug-in surface:** `POST /trading_action/`

Request (README + `call_single_trading_api` payload):

```json
{"date": "...", "price": {"BTC": 45000}, "news": {"BTC": "..."}, "symbol": ["BTC"], "model": "gpt-4o", "10k": {}, "10q": {}, "history_price": {}}
```

Response:

```json
{"recommended_action": "BUY|SELL|HOLD", "reasoning": "..."}
```

Register URL in `modules/ama/testbed/configs/agents.json`. Decisions written to `action/{identifier}_{symbol}_{model}_trading_decisions.json` (`save_decision_to_json`). PnL: `get_return.py`.

**OpenClaw/Hermes without rewriting?** Not as a Gateway/CLI process. **Yes if wrapped as that HTTP contract.** Hermes already documents FastAPI embedding. Our stub `adapters/ama.py:AmaHttpShim.handle` maps the POST body onto `Observation` / `Decision`. That is the cheapest official-shaped bridge.

Caveats from local code: `trading_strategy` is computed then immediately set `trading_strategy = False` so it is never sent (`get_daily_action.py:call_single_trading_api`). `current_position` is read but commented out of the payload. Do not invent those fields as required.

### 3.2 FINSABER — strategy subclass (suite among equals)

**Loop owner:** FINSABER engine. Strategy only answers “what order now?”; fills, costs, artifacts are the framework (`modules/finsaber/docs/strategies.md`).

**Native plug-in surface (LLM-style):** subclass `BaseStrategyIso`, implement `on_data`, call `framework.buy` / `framework.sell`.

**Conflict — second parameter name:**

| Source | Signature / call |
| --- | --- |
| Stub | `modules/finsaber/backtest/strategy/timing_llm/base_strategy_iso.py:BaseStrategyIso.on_data` → `(self, date, data_loader, framework)` |
| Actual call | `modules/finsaber/backtest/toolkit/backtest_framework_iso.py` line 272: `strategy.on_data(date, self.data_loader.get_data_by_date(date), self)` |
| Docs + FinMem + tests | `(date, today_data, framework)` — `modules/finsaber/README.md`, `docs/strategies.md`, `llm_traders/finsaber_strategies/finmem.py:FinMemStrategy.on_data` |

The **object passed is today’s dict** (`price` / `news` / filings), not the loader. The stub’s name `data_loader` is misleading. Packaged re-export: `modules/finsaber/finsaber/strategy/timing_llm/base_strategy_iso.py` star-imports the backtest stub.

Orders: `framework.buy(date, ticker, price, quantity)` / `sell(...)` (`backtest_framework_iso.py`). `quantity=-1` means all-in / full-exit (`docs/strategies.md`). Default fill `next_open`. Backtrader path (`BaseStrategy.next` + `FINSABERBt`) is a second surface; README says LLM agents use Python-native `FINSABER`.

FinMem-like: already a `BaseStrategyIso` that calls `self.agent.step(...)` then `framework.buy/sell` (`finmem.py`). That is the FINSABER-native shape.

**OpenClaw/Hermes without rewriting?** No. Must wrap: each `on_data` builds a prompt from `today_data`, calls `AIAgent.chat` / OpenClaw turn, maps BUY/SELL/HOLD onto `framework.buy/sell`. They do not own fills.

### 3.3 StockBench — dual-agent loop inside *their* backtest

**Loop owner:** StockBench backtest. Daily `Strategy.on_bar(ctx) -> List[Dict]` (`modules/stockbench/stockbench/backtest/strategies/llm_decision.py:Strategy.on_bar`). `ctx` keys documented in that docstring: `date, symbols, open_map/open_price_map, ref_price_map, portfolio, cfg, datasets, rejected_orders`.

Dual-agent: `decide_batch_dual_agent` in `stockbench/agents/dual_agent_llm.py` — filter agent then decision agent. Actions in the decision prompt: `increase | hold | decrease | close` plus `target_cash_amount` (`stockbench/agents/prompts/decision_agent_v1.txt`). Official CLI: `scripts/run_benchmark.sh` → `python -m stockbench.apps.run_backtest --strategy llm_decision --agent-mode dual` (`MODULES.md`, README).

**Native plug-in surface:** (1) replace or wrap `Strategy.on_bar`; or (2) black-box the official CLI and only swap `--llm-profile` (that tests *their* prompts + your model, not your agent).

**OpenClaw/Hermes without rewriting?** No. Vocabulary is not BUY/SELL/HOLD. Observation would need the feature bundle + portfolio + decision history. `Decision.allocations` is closer than `Decision.action`, still missing `target_cash_amount` / `close`.

### 3.4 DeepFund — closed LangGraph workflow

**Loop owner:** them. `AgentWorkflow.run` iterates tickers, `workflow.invoke(state)`, updates portfolio, writes SQLite/Supabase (`modules/deepfund/src/graph/workflow.py:AgentWorkflow`). Entry: `python main.py --config ... --trading-date YYYY-MM-DD [--local-db]` (`README.md`). **Does not trade** (README). Chronological `trading-date` per `exp_name`.

**Native plug-in surface:**

1. `AgentRegistry.register_agent(key, agent_func, agent_doc)` (`agents/registry.py:AgentRegistry.register_agent`) — documented as “How to add a new analyst?” (`TECHNICAL_GUIDE.md`).
2. YAML `llm.provider` / `llm.model` — swap backbone only.
3. Harvest `config` / `portfolio` / `decision` / `signal` tables.

PM output schema: `graph/schema.py:Decision` with `action: Action` (`Buy`/`Sell`/`Hold` — **title case**, `graph/constants.py:Action`), `shares`, `price`, `justification`. Analysts emit `Signal` Bullish/Bearish/Neutral (`TECHNICAL_GUIDE.md`).

**OpenClaw/Hermes without rewriting?** No. Graph owns analysts + PM + APIs. To inject an external agent you replace `portfolio_agent` (or an analyst) with a node that calls `decide()`. Black-box path: same YAML LLM, scrape DB — that is **not** “your OpenClaw agent sat the exam.”

Time-travel pitfall (must stay on the protocol): fundamental / macroeconomic analysts “can only retrieve the latest data” (`TECHNICAL_GUIDE.md` Remarks).

### 3.5 FinToolBench — JSONL eval (no agent runtime in the open release)

**Loop owner:** **you** (the agent). README: open release is evaluation pipeline + 760-tool manifest + 295 questions; “Full agent training/build scripts and other internal components are not included.” (`modules/fintoolbench/README.md`)

**Native plug-in surface:** emit a result JSONL, then:

```text
python -u code_bench/evaluate/run_relative_eval.py --inputs <result.jsonl> --output_dir ...
```

Evaluator (`code_bench/evaluate/evaluator.py`):

- index key `id` (falls back to line index)
- question: `question` or `query` (`extract_question`)
- answer: `execution_result` or `answer` (`extract_answer`)
- gold: `ground_truth`
- tools: `tool_calls[]` with `step`, `tool_name`, `output` (`metrics_capability.py:extract_tool_fields` / `normalize_tool_calls`)

Questions file `data/question/select_data_real_remove_duplicates.jsonl` uses `original_idx`, `question`, `answer`, `select_tools` — **no `id` field on the rows I read**. A producer should set `id` (or accept positional ids). Manifest: `tools/tools_all_annotated.jsonl` with `financial_tags.timeliness|intent_type|regulatory_domains`.

Metrics: TIR/TESR/CER/SoftScore/CSS (higher better); TMR/IMR/DMR mismatch rates (lower better). RapidAPI drift → pin eval date + manifest hash.

**OpenClaw/Hermes without rewriting?** Closest of the five if you constrain tools to the 760-card manifest and dump traces as this JSONL. Still a rewrite of the tool surface: Hermes/OpenClaw tools ≠ RapidAPI/AkShare cards. `Decision.tool_calls` is an untyped `list[dict]` — too loose until we specify FinTool fields.

### 3.6 TradingAgents (optional, README only)

Not in `modules/`. README: LangGraph firm (analysts, researchers, trader, risk, PM). Plug-in is `TradingAgentsGraph.propagate("NVDA", "2026-01-15")` and `config["llm_provider"]`. Persistence: `~/.tradingagents/memory/trading_memory.md`. Same family as DeepFund: **closed workflow, swap LLM, not swap agent.** ([README](https://github.com/TauricResearch/TradingAgents))

---

## 4. Plug-in patterns in the wild

| Pattern | What you implement | Systems |
| --- | --- | --- |
| **HTTP protocol** | Serve a documented POST; eval owns dates/data | AMA; Hermes FastAPI sample (generic `/chat`) |
| **Strategy subclass** | `on_data` / `on_bar` / `next`; engine owns fills | FINSABER `BaseStrategyIso`; StockBench `Strategy.on_bar`; FINSABER Backtrader `BaseStrategy.next` |
| **Trajectory JSONL** | Agent runs elsewhere; eval scores files | Hermes ShareGPT JSONL; ClawBench Partner Trace; FinToolBench result JSONL |
| **Framework-specific adapter** | Register a node / provider / harness with *their* SDK | OpenClaw `AgentHarnessV2` + provider plugins; Hermes `register_provider`; DeepFund `AgentRegistry.register_agent` |
| **Closed workflow** | Only YAML/model config; harvest traces | DeepFund `main.py`; TradingAgents `propagate`; StockBench `--llm-profile` black-box |

OpenClaw the product is a **framework-specific adapter** (runtime) plus ClawBench **trajectory JSONL** (eval). Hermes is a **runtime library** plus **trajectory JSONL**. Neither is a finance exam room.

---

## 5. Concrete recipes: Agent X → this infra

### Hermes Agent

1. Implement `AgentAdapter.decide` as: format `Observation` into a user message (disable terminal/browser; `skip_memory=True`, `quiet_mode=True`, low `max_iterations`), call `AIAgent.chat` / `run_conversation`, parse BUY/SELL/HOLD or tool JSON from `final_response` ([python-library](https://hermes-agent.nousresearch.com/docs/guides/python-library)).
2. **AMA:** wrap that adapter with `AmaHttpShim` (or FastAPI) at `POST /trading_action/`; add URL to `agents.json`.
3. **FINSABER suite:** `class HermesIso(BaseStrategyIso)` → in `on_data` build obs from `today_data`, `decide()`, `framework.buy/sell`.
4. **FinToolBench:** run Hermes with a toolset that is *only* the FinTool manifest (not Hermes’ 70+ tools), write JSONL, `run_relative_eval.py`.
5. **StockBench / DeepFund:** do not send Hermes in raw; translate `on_bar` / replace PM node, or admit you only swapped models.
6. Optional: `save_trajectories=True` and attach JSONL as `SuiteResult.traces_path` / `Artifact(kind="tool_trace")`. Hermes JSONL is **not** ClawBench Partner Trace and **not** FinTool result JSONL.

### OpenClaw

OpenClaw is a personal Gateway, not an exam candidate API.

- **Do not** implement `AgentHarnessV2` inside this repo to “be OpenClaw.” That SPI is for replacing OpenClaw’s turn executor ([sdk-agent-harness](https://docs.openclaw.ai/plugins/sdk-agent-harness)).
- **Do** expose a tiny HTTP service (same AMA contract) that, internally, may call OpenClaw if you must — still a rewrite at the boundary.
- **ClawBench** scores OpenClaw-like traces. Our admission report wants FINSABER honesty + harvested suite artifacts (`ACCEPTANCE_REPORT.schema.json`). Mapping ClawBench `run_score` into `admission.decision` would be a **different product** (and would not replace the parallel scorecard).
- Skills/MCP inside OpenClaw do not satisfy FinToolBench’s annotated RapidAPI tools.

### AMA-wrapped bot

Already on the native surface. Register in `configs/agents.json`, run `get_action.sh` / `get_return.py`, harvest `action/*_trading_decisions.json`. To also sit FINSABER: reuse the same process via `AmaHttpShim.handle` in-process and a `BaseStrategyIso` that calls the same `decide()`. Live drift: pin as-of + `paper_trading_*.json` vintage (`MODULES.md`).

### FinMem-like strategy

Already FINSABER-native (`finmem.py:on_data`). Wire `FinsaberEnvAdapter` to construct that strategy (or a thin wrapper around `AgentAdapter`), run `FINSABER` with `execution_timing=next_open` + costs, refuse `cherry_pick_*`. Harvest `metrics.json` / `run_config.json`. That is the FINSABER suite (`adapters/finsaber.py`, `ARCHITECTURE.md`), not a global gate.

### TradingAgents / DeepFund-like graph

They own the day. Two honest modes:

- **Harvest-only:** chronological `main.py --local-db` (or `propagate`); scrape Decision/Signal/Portfolio; `status` reflects *their* agent, not ours. Optional exam room.
- **Inject:** replace `portfolio_agent` / Trader with a node that calls `AgentAdapter.decide` and writes `graph.schema.Decision`. Analysts still theirs unless also replaced.

Do not claim an OpenClaw/Hermes graph sat DeepFund because the YAML model string matches.

### FinTool JSONL agent

For each question: `Observation(query=..., tools=manifest, as_of=eval_date)` → `Decision.tool_calls` with `{tool_name, step, output}` → JSONL `{id, question, tool_calls, execution_result, ground_truth?}` → `run_relative_eval.py`. Gates on TMR/IMR/DMR must be `lte` (`MODULES.md`). This suite is **not** PnL.

---

## 6. What `adapters/base.py` `decide(Observation)` gets wrong or oversimplifies

Evidence against the current LCD (`adapters/base.py:Observation`, `Decision`, `AgentAdapter.decide`):

1. **One shot vs multi-turn tool loop.** Hermes/OpenClaw turns are “API call → tools → loop” ([agent-loop](https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop), OpenClaw `runAttempt`). `decide()` is a single function with no iteration, approval, or interrupt. Fine as a *boundary*, dishonest if we pretend the agent has no inner loop.

2. **Single `Decision.action: str` vs many vocabularies.** AMA: `BUY|SELL|HOLD` (`modules/ama/README.md`). DeepFund: `Buy|Sell|Hold` + `shares` (`graph/constants.py:Action`, `schema.py:Decision`). StockBench: `increase|decrease|hold|close` + `target_cash_amount` (`decision_agent_v1.txt`). FINSABER: no action enum — `framework.buy/sell` with quantity (`backtest_framework_iso.py`). One string cannot round-trip these without a per-suite mapper (AmaHttpShim already special-cases BUY/SELL/HOLD).

3. **Stateless Observation vs stateful book.** StockBench keeps `decision_history` on the strategy (`llm_decision.py`). AMA keeps `data/positions.json` in the testbed, not in the POST body (position key is commented out). DeepFund loads portfolio from DB (`AgentWorkflow.__init__`). `Observation.portfolio` is an optional dict with no schema; `decide()` has no required `agent_id`+date memory contract.

4. **Batch vs single-name.** StockBench `on_bar` decides a **universe** in one LLM batch (`decide_batch_dual_agent`). AMA POSTs **one symbol**. FINSABER `run_iterative_tickers` is per ticker. `Observation.symbols` is a list but `Decision.action` is scalar; `allocations` exists but is unused by stubs.

5. **Tool traces are untyped.** FinToolBench requires `tool_calls[].tool_name/step/output` (`metrics_capability.py`). `Decision.tool_calls: list[dict]` documents nothing. Hermes ShareGPT `from`/`value`/`tool_calls` is a third shape; ClawBench Partner Trace is a fourth.

6. **`capabilities()` is suite willingness, not tools.** Empty means sit every suite (`AgentAdapter.capabilities`). OpenClaw/Hermes “capabilities” are toolsets/MCP/skills. An agent that cannot call RapidAPI should not silently sit FinToolBench.

7. **No trajectory hook.** `SuiteResult.traces_path` exists but `decide()` never yields a turn log. Eval harnesses that score process (ClawBench 30% trajectory weight; FinTool TIR/TESR) need the inner loop, not just the final action.

8. **Env still owns the loop — the Protocol over-promises “one decide() sits every exam.”** `ARCHITECTURE.md` sequence diagram shows every Env calling `decide()`. FinToolBench’s official CLI never calls an agent (`run_relative_eval.py` only reads JSONL). DeepFund/StockBench official CLIs never import `AgentAdapter`. The LCD is a **translator target**, not a drop-in for official CLIs. Current stubs honestly `skip` (`skipped_suite`) — keep that until translators exist.

9. **Filings/news/prices are the right idea, wrong completeness.** AMA and FINSABER both pass price + news + 10-K/10-Q. StockBench also needs `position_state`, 7-day closes, optional fundamentals, rejected orders. DeepFund PM needs `analyst_signals` + `decision_memory`. Cramming them into `raw` works only if EnvAdapters actually fill `raw` and agents read it — the typed fields alone are AMA-shaped.

What it **gets right:** Env owns fills (`ARCHITECTURE.md` “Compose, don't rewrite”); `ProtocolSpec` hashes the exam paper not the answers; `Observation.raw` / `Decision.raw` are escape hatches; AMA shim is the correct depth for HTTP.

---

## 7. Recommended first-class bridges (ordered)

Estimates assume one engineer who already knows this repo. Not a schedule.

| Order | Bridge | Why first | Cost | Feeds admission how |
| --- | --- | --- | --- | --- |
| 1 | **AMA HTTP shim** (FastAPI around `AmaHttpShim`) | Contract is fully specified; stub exists; Hermes FastAPI sample is the same shape | **S** | `get_return.py` metrics → `ama.multi_market_live` SuiteResult (optional room) |
| 2 | **FINSABER `BaseStrategyIso` wrapper** | Long-horizon suite; call site is one line; FinMem is the template | **M** | `metrics.json` + honesty gates → FINSABER pass/fail (not a global veto) |
| 3 | **FinToolBench JSONL emitter** | Eval does not run the agent; we must produce files anyway | **M** | `all_metrics.json` TIR/…/DMR → suite among equals, `lte` gates |
| 4 | **StockBench `on_bar` translator** | Need per-symbol target-cash mapping + dual-agent ctx | **M–L** | `storage/reports/backtest/` → suite among equals |
| 5 | **DeepFund harvest-only** then optional PM-node inject | Harvest is compose-CLI; inject is graph surgery | **S** then **L** | DB traces → optional room |
| 6 | **Hermes `AIAgent` as one `AgentAdapter` impl** | Reuses 1–3; not a new suite | **M** | Same report; `traces_path` = `trajectory_samples.jsonl` |
| 7 | **OpenClaw** | Only if a customer *is* OpenClaw; still via HTTP/strategy, not `AgentHarnessV2` | **L** (integration) / **XL** if we try to be a harness | Same; do not ingest ClawBench `run_score` as promotion |

**Do not build (this repo):** OpenClaw `AgentHarnessV2`, ClawBench task runner, Hermes `evals/` probes, TradingAgents fork, a second Sharpe.

---

## 8. Direct answers to the assignment questions

**Can an arbitrary OpenClaw/Hermes agent sit this exam without rewriting?**  
No. Closest zero-logic path is AMA if they already speak `POST /trading_action/`. Everything else needs a bridge. Sitting FINSABER (the only thing that can `promote`) always requires a `BaseStrategyIso` (or Backtrader) wrapper.

**Who owns the agent loop?**  
Us only for FinToolBench (we must run the agent). Them for AMA, FINSABER, StockBench, DeepFund. Hermes/OpenClaw own *their* inner tool loop even when we wrap `decide()`.

**Is there an official bring-your-agent path?**  
ClawBench: Partner Trace JSONL. Hermes: no. AMA: HTTP. FINSABER: subclass. StockBench: `on_bar` or CLI profile. DeepFund: register analyst / swap LLM. FinToolBench: emit JSONL.
