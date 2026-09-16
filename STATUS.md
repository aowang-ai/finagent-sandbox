# Status

Product: **FinAgentSandbox**. Scoring policy: [`GOAL.md`](GOAL.md). Registries: [`ARCHITECTURE.md`](ARCHITECTURE.md) (HarnessFactory / BenchFactory / PluginFactory).

This skeleton does **not** vendor executed scorecards. Generate them locally (`scripts/run_eval.py`); do not wipe `reports/GROK_CLI_SCORECARD.*` if you create them.

## Wired (v1) — required for `admission.decision=promote`

| Suite | Adapter | Notes |
| --- | --- | --- |
| `ama.multi_market_live` | `adapters/ama.py` | HTTP testbed + `AmaHttpShim` |
| `finsaber.long_horizon` | `adapters/finsaber.py` | Honesty gates stay on this suite |
| `stockbench.daily_sim` | `adapters/stockbench.py` | Official CLI / YAML bridge |
| `fintoolbench.tool_compliance` | `adapters/fintoolbench.py` | Emit JSONL, then official evaluator |
| `deepfund.fund_arena` | `adapters/deepfund.py` | Official `main.py --local-db` |

## Wired (v2) — optional until a complete scorecard is wanted

Official-protocol adapters. Harvest / resume: `adapters/v2_ops/` + `scripts/v2_suite_ops.py`. Blockers: [`docs/engineering/V2_SUITE_STATUS.md`](docs/engineering/V2_SUITE_STATUS.md).

| Suite | Adapter |
| --- | --- |
| `investorbench.decision` | `adapters/investorbench.py` |
| `livetradebench.live` | `adapters/livetradebench.py` |
| `finmcp.tool_mcp` | `adapters/finmcp.py` |
| `vals_finance_agent.research` | `adapters/vals_finance_agent.py` |
| `finsearchcomp.search` | `adapters/finsearchcomp.py` |
| `openpm.portfolio_pit` | `adapters/openpm.py` |

`admission.decision` uses `REQUIRED_SUITE_IDS_V1` (the five). v2 cannot HOLD promote. FINSABER is not a global veto.

## Factories

| Registry | Keys today |
| --- | --- |
| `HarnessFactory` | `grok-cli` |
| `BenchFactory` | 11 `ALL_SUITE_IDS` → `EnvAdapterAsBench` |
| `PluginFactory` | `mcp` → `McpPlugin` |

Phase F (second real harness) is out of scope for this skeleton.
