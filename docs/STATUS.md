# Status

Product: **FinAgentSandbox**. Scoring policy: [`GOAL.md`](GOAL.md). Registries: [`ARCHITECTURE.md`](ARCHITECTURE.md) (HarnessFactory / BenchFactory / PluginFactory).

This skeleton does **not** vendor executed scorecards. Generate them locally (`cli/run_eval.py`); do not wipe `reports/GROK_CLI_SCORECARD.*` if you create them.

## Required — `admission.decision=promote` completeness set

| Suite | Adapter | Notes |
| --- | --- | --- |
| `ama.multi_market_live` | `adapters/ama/adapter.py` | HTTP testbed + `AmaHttpShim` |
| `finsaber.long_horizon` | `adapters/finsaber/adapter.py` | Honesty gates stay on this suite |
| `stockbench.daily_sim` | `adapters/stockbench/adapter.py` | Official CLI / YAML bridge |
| `fintoolbench.tool_compliance` | `adapters/fintoolbench/adapter.py` | Emit JSONL, then official evaluator |
| `deepfund.fund_arena` | `adapters/deepfund/adapter.py` | Official `main.py --local-db` |

## Optional — same factory; skip if deps missing

Official-protocol adapters. Harvest / resume: `adapters/<bench>/ops.py` + `cli/optional_suite_ops.py`. Blockers: [`docs/engineering/OPTIONAL_SUITE_STATUS.md`](engineering/OPTIONAL_SUITE_STATUS.md).

| Suite | Adapter |
| --- | --- |
| `investorbench.decision` | `adapters/investorbench/adapter.py` |
| `livetradebench.live` | `adapters/livetradebench/adapter.py` |
| `finmcp.tool_mcp` | `adapters/finmcp/adapter.py` |
| `vals_finance_agent.research` | `adapters/vals_finance_agent/adapter.py` |
| `finsearchcomp.search` | `adapters/finsearchcomp/adapter.py` |
| `openpm.portfolio_pit` | `adapters/openpm/adapter.py` |

`admission.decision` uses `REQUIRED_SUITE_IDS` (the five). Optional benches cannot HOLD promote. FINSABER is not a global veto. One scorecard per harness; optional rows carry `tier=optional`.

## Factories

| Registry | Keys today |
| --- | --- |
| `HarnessFactory` | `grok-cli` |
| `BenchFactory` | 11 `ALL_SUITE_IDS` → `EnvAdapterAsBench` |
| `PluginFactory` | `mcp` → `McpPlugin` |

Phase F (second real harness) is out of scope for this skeleton.
