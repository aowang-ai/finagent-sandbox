# FinAgentSandbox

Eval infra that scores **agent harnesses** on **community finance benches** inside a **composable sandbox**, and emits a parallel scorecard.

Innovation is the product of three independent axes — **三动态**, not a version number:

| Axis | Meaning | First instance here |
| --- | --- | --- |
| **Dynamic harness** | Grok CLI / Claude Code / Codex / OpenClaw / a custom agent plug into the **same** sandbox + benches | `GrokCliHarness` via `HarnessFactory` |
| **Dynamic environment** | Sandbox **provider** (session isolation) **plus** finance **plugins** (MCP / data tools) added without freezing one agent loop | `LocalProcessSandbox` + `McpPlugin` |
| **Dynamic bench** | Continuously compose StockBench, FINSABER, AMA, Vals, … — community exam rooms, not invented papers | `EnvAdapter` wrapped by `BenchFactory` |

This is **not** a trading bot, not a broker, and not a public “who has more alpha” leaderboard. We do **not** claim to be the first finance-agent eval, and we do **not** claim bitwise reproduction of any paper’s table. We compose upstream benches; we do not reinvent their protocols.

## Three factories

Adding a harness, bench, or plugin is a registry entry — not a new eval loop.

| Registry | Plug-in meaning | Today |
| --- | --- | --- |
| **`HarnessFactory`** | New agent harness without rewriting `run_suites` | `grok-cli` → `GrokCliHarness` |
| **`BenchFactory`** | New community bench without a new `ADAPTERS` dict | 11 suite ids → `EnvAdapterAsBench` wrap |
| **`PluginFactory`** | New MCP / tool / data env without a new sandbox type | `mcp` → `McpPlugin` (FinMCP `plugin_env`) |

`SandboxFactory` (`local-process`) is a **provider**, not the third dynamic. Do not put Yahoo harvest or MCP in it. See [`docs/paper/SANDBOX_REPO_DESIGN.md`](docs/paper/SANDBOX_REPO_DESIGN.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md).

Scoring is a **parallel scorecard**: every suite reports its own pass/fail. FINSABER honesty is suite-local, not a global veto. `admission.decision` means completeness only (`promote` when every required suite produced a score).

## Upstream benches (we compose)

### Required — `admission.decision=promote` completeness set

| Dir | Upstream | Paper | Role |
| --- | --- | --- | --- |
| `modules/stockbench` | [ChenYXxxx/stockbench](https://github.com/ChenYXxxx/stockbench) | [arXiv:2510.02209](https://arxiv.org/abs/2510.02209) | Daily DJIA-20 sim |
| `modules/ama` | [The-FinAI/Agent_Market_Arena](https://github.com/The-FinAI/Agent_Market_Arena) | [arXiv:2510.11695](https://arxiv.org/abs/2510.11695) | Live / near-live multi-market |
| `modules/deepfund` | [HKUSTDial/DeepFund](https://github.com/HKUSTDial/DeepFund) | [arXiv:2505.11065](https://arxiv.org/abs/2505.11065) NeurIPS'25 | Fund arena + decision traces |
| `modules/fintoolbench` | [Double-wk/FinToolBench](https://github.com/Double-wk/FinToolBench) | [arXiv:2603.08262](https://arxiv.org/abs/2603.08262) | Tool-call + timeliness/intent/domain |
| `modules/finsaber` | [waylonli/FINSABER](https://github.com/waylonli/FINSABER) | [arXiv:2505.07078](https://arxiv.org/abs/2505.07078) | Long-horizon anti-bias (suite among equals) |

### Optional — same `BenchFactory`; skip if deps are missing

| Dir | Upstream | Paper | Role |
| --- | --- | --- | --- |
| `modules/investorbench` | [felis33/INVESTOR-BENCH](https://github.com/felis33/INVESTOR-BENCH) | [arXiv:2412.18174](https://arxiv.org/abs/2412.18174) ACL'25 | Cross-asset decision |
| `modules/livetradebench` | [ulab-uiuc/live-trade-bench](https://github.com/ulab-uiuc/live-trade-bench) | [arXiv:2511.03628](https://arxiv.org/abs/2511.03628) | Live stocks + Polymarket |
| `modules/finmcp` | [aliyun/qwen-dianjin](https://github.com/aliyun/qwen-dianjin) `DianJin-TIR/` | [arXiv:2603.24943](https://arxiv.org/abs/2603.24943) | MCP tool orchestration |
| `modules/vals_finance_agent` | [vals-ai/finance-agent](https://github.com/vals-ai/finance-agent) | [arXiv:2508.00828](https://arxiv.org/abs/2508.00828) | SEC/research + tools |
| `modules/finsearchcomp` | [randomtutu/FinSearchComp](https://github.com/randomtutu/FinSearchComp) | [arXiv:2509.13160](https://arxiv.org/abs/2509.13160) | Time-sensitive search |
| `modules/openpm` | [aslcai/OpenPM-Bench](https://github.com/aslcai/OpenPM-Bench) | (repo README) | PIT portfolio + audit trail |

Clones live under `modules/` and are **gitignored**. Fetch with `./scripts/clone_modules.sh`. Per-suite CLIs, metrics, and pitfalls: [`MODULES.md`](MODULES.md). Glue we did not pretend away: [`docs/engineering/GLUE.md`](docs/engineering/GLUE.md).

## Quickstart

```bash
git clone https://github.com/aowang-ai/finagent-sandbox.git
cd finagent-sandbox

# 1. Placeholder env only — copy and fill; never commit .env
cp .env.example .env

# 2. Fetch required + optional upstreams (idempotent, shallow). Does not download parquet dumps.
./scripts/clone_modules.sh

# 3. Dry "infra doctor" — no API keys, no parquet, no LLM
./scripts/doctor.sh

# 4. Dry run through HarnessFactory (skip-path; no engines)
PYTHONPATH=src:. python -m finagent.cli --harness grok-cli --dry
```

Doctor checks that **required** modules exist (fail if missing), **warns** if optional clones are absent, compiles `adapters/` + `src/finagent/` factories, parses `ACCEPTANCE_REPORT.schema.json`, and runs a dummy `AgentAdapter` through the required five + optional six (dry skip). Expected admission on required stubs: **HOLD** (scorecard incomplete). A FINSABER fail does not veto other suites.

Executed scorecards are **generated artifacts**, not vendored in this skeleton. After a real run:

```bash
# optional: skip-path smoke of required adapters
PYTHONPATH=src:. python -m finagent.cli --harness grok-cli --dry

# optional: recompose an on-disk scorecard (no suite re-run, no LLM)
PYTHONPATH=src:. python -m finagent.cli --harness grok-cli --report-only

# optional-suite harvest / progress (same GROK_CLI_SCORECARD, tier=optional)
PYTHONPATH=src:. python cli/optional_suite_ops.py progress
PYTHONPATH=src:. python cli/optional_suite_ops.py harvest
```

`cli/run_grok_cli_eval.py` is a thin alias for `run_eval.py --harness grok-cli`. New dumps go under `artifacts/suite_results/<harness>/`. Do **not** wipe `reports/GROK_CLI_SCORECARD.*` if you generate them locally.

FINSABER parquet: set `FINSABER_DATA_ROOT` to a directory that contains `price_daily/`.

## Repo layout

```
src/finagent/harness/          HarnessFactory + GrokCliHarness + GrokRunner
src/finagent/provider/         SandboxFactory / LocalProcessSandbox
src/finagent/plugins/          PluginFactory / McpPlugin
src/finagent/trial/            Trial, run_suites, dumps, config
src/finagent/scorecard/        SuiteResult / AcceptanceReport / write_scorecard
src/finagent/benches/          BenchFactory wrapping adapters/*
src/finagent/cli.py            python -m finagent.cli
adapters/<bench>/              one package per bench (EnvAdapter + optional ops)
cli/run_eval.py                same eval entry as python -m finagent.cli
cli/optional_suite_ops.py      optional-suite progress / harvest / resume
scripts/clone_modules.sh       idempotent shallow clone into modules/
scripts/doctor.sh              structural health check (no secrets)
ACCEPTANCE_REPORT.schema.json
docs/                          GOAL, ARCHITECTURE, MODULES, STATUS + paper/product
CONTRIBUTING.md                how to register a harness / bench / plugin
modules/                       gitignored clones (README + .gitkeep are tracked)
reports/                       generate scorecards here; skeleton ships .gitkeep only
```

Single eval entry: `python -m finagent.cli` (console script `finagent-eval`). `cli/run_eval.py` is the same entry as a script. `cli/run_grok_cli_eval.py` is a thin alias that hides `--harness`.

Locked policy: [`docs/GOAL.md`](docs/GOAL.md). Adapter contracts: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Product vs Paradoox / Vals / Patronus: [`docs/product/POSITIONING.md`](docs/product/POSITIONING.md).


## License

[Apache License 2.0](LICENSE). Copyright 2026 Ao Wang.
