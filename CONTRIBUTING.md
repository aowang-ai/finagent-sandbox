# Contributing to FinAgentSandbox

Apache-2.0. We compose community finance benches; we do not reinvent their papers. A second harness, bench, or plugin is a **factory `_MAP` entry**, not a new eval loop.

## Before you start

```bash
./scripts/clone_modules.sh
./scripts/doctor.sh
PYTHONPATH=src:. python -m finagent.cli --harness grok-cli --dry
```

Doctor must stay green for structural checks. Optional clones and venvs are warnings, not failures. GitHub Actions / empty-modules checkout: `./scripts/doctor.sh --ci` (missing `modules/*` warns, does not fail).

Copy `.env.example` → `.env` for local keys. **Never commit `.env`, PATs, OIDC blobs, or `~/.grok/auth.json`.**

## Do not wipe scorecards

Do **not** rewrite metric values in:

- `reports/GROK_CLI_SCORECARD.md` / `.json` (one card per harness; required/optional is a per-suite field)
- legacy flat `artifacts/suite_results/{suite_id}.json`

New dumps go under `artifacts/suite_results/<harness>/`. Non-Grok harnesses never write `grok-cli/`. `--report-only` may recompose a scorecard from dumps; it must not invent suite rows.

`admission.decision` is scorecard **completeness**. FINSABER honesty is suite-local — it does not veto AMA / StockBench / FinTool / DeepFund.

## Add a harness (`HarnessFactory`)

1. Implement `finagent.harness.base.BaseHarness` (`name()`, `features()`, `suite_ids()`, setup/run as in [`docs/paper/SANDBOX_REPO_DESIGN.md`](docs/paper/SANDBOX_REPO_DESIGN.md)).
2. Register in `src/finagent/harness/factory.py`:

   ```python
   HarnessFactory._MAP["your-harness"] = "finagent.harness.your_mod:YourHarness"
   ```

3. A harness that cannot sit a `decide()`-bench **skips**; it does **not** HOLD-fill. Empty `suite_ids()` = sit none.
4. Do not grow `src/finagent/trial/run_suites.py` or `Trial` with `if harness == ...`. Unknown names already raise `ValueError` listing keys.
5. Import-path escape: a name containing `:` is loaded directly (Harbor `create_agent_from_config` analogue).

Today only `grok-cli` is registered. Empty Claude Code / Codex / OpenClaw stubs are **not** a required milestone.

## Add a bench (`BenchFactory`)

1. Write an `EnvAdapter` in `adapters/<bench>/adapter.py` (`suite_id`, `module_dir`, `describe()`, `run(agent, protocol) -> SuiteResult`). Prefer the official upstream CLI; harvest native artifacts. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/engineering/GLUE.md`](docs/engineering/GLUE.md).
2. Add the suite id to `adapters/base.py` (`REQUIRED_SUITE_IDS` or `OPTIONAL_SUITE_IDS` — do not silently promote a bench into the required set).
3. Register in `src/finagent/benches/factory.py`:

   ```python
   BenchFactory._MAP["yourbench.suite_id"] = "adapters.yourbench:YourEnvAdapter"
   ProtocolFactory._MAP["yourbench.suite_id"] = "finagent.benches.protocols:yourbench_protocol"
   ```

   `BenchFactory.create` **always** wraps with `EnvAdapterAsBench` (FinMCP uses `FinMcpEnvAdapterAsBench` for `exec_sync` opt-in).
4. Add a protocol helper in `src/finagent/benches/protocols.py` and an optional short alias in `SUITE_ALIASES`.
5. Clone URL goes in `scripts/clone_modules.sh` + `modules/README.md` + `docs/MODULES.md`. Do not vendor the clone.

We compose; we do not reimplement fills, judges, or LangGraph.

## Add a plugin (`PluginFactory`)

Finance env plugins are **not** sandbox providers.

1. Implement `finagent.plugins.base.EnvPlugin`.
2. Register in `src/finagent/plugins/factory.py`:

   ```python
   PluginFactory._MAP["your-plugin"] = "finagent.plugins.your_mod:YourPlugin"
   ```

3. MCP / Qieman attach here (`McpPlugin` is `plugin_env` for FinMCP). Yahoo harvest stays `adapters/ama/yahoo.py` — do **not** register it as a plugin or a `SandboxFactory` type.
4. `LocalProcessSandbox` is isolation (session `HOME`). Do not put MCP in `SandboxFactory`.

## Doctor and tests

```bash
./scripts/doctor.sh
pytest tests/unit -q
```

CI is `pytest tests/unit -q` plus `./scripts/doctor.sh --ci`. If you add a registry key, extend the corresponding unit test and `scripts/doctor.sh` factory smoke. Do not require overnight/campaign scripts.

## License

Contributions are under the [Apache License 2.0](LICENSE). Copyright 2026 Ao Wang.
