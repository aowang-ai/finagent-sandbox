# BRIEF — Harbor-thin layout restructure (finagent-sandbox only)

Repo: `/workspace/finagent-sandbox`  
Do **not** touch `finance-agent-eval-infra`.

## Target tree (ao approved)

```
src/finagent/
  harness/       # from sandbox/harness + peel runners/grok into harness/grok_cli (keep low-level runner module if needed under harness/)
  provider/      # from sandbox/provider
  plugins/       # from sandbox/plugins
  trial/         # from sandbox/runtime (trial, run_suites, dumps, config)
  scorecard/     # SuiteResult / AcceptanceReport / write_scorecard types moved from adapters.base / runners.scorecard as cleanly as practical
adapters/        # one dir (or package) per bench: stockbench/, ama/, … — EnvAdapter implementations live here
cli/             # run_eval as the single public entry; thin wrappers ok temporarily
docs/
modules/         # gitignored clones (unchanged policy)
tests/
```

## Rules

1. **Move + fix imports only.** No official protocol changes. No metric rewrite. No new benches.
2. Package name: **`finagent`** under `src/` (src-layout). Update `pyproject.toml` accordingly. Prefer short-term compat shims (`sandbox` → re-export `finagent`) **only if** needed for one release; document deprecation; ideally update all imports in-repo and drop `sandbox` package.
3. Kill product-facing leftover names where cheap: rename `adapters/v2_ops` → something like `adapters/_ops` or fold into per-bench dirs; rename `scripts/v2_suite_ops.py` → `cli/` or `scripts/optional_suite_ops.py`. Don't leave "v2" in public paths if easy.
4. Root: keep README, LICENSE, CONTRIBUTING, pyproject, .env.example, .gitignore. Move bulky GOAL/ARCHITECTURE/MODULES/STATUS into `docs/` (or keep thin stubs that point to docs/). Don't delete content.
5. `modules/` stays gitignored clones; `reports/`, `artifacts/` stay as today.
6. doctor + unit tests must pass after path updates.
7. Single eval entry: `python -m finagent.cli` or `cli/run_eval.py` / console_script — pick one and document in README.
8. Commit + push `main` as Ao Wang <aowang-ai@users.noreply.github.com>; remote without PAT.
9. Write `docs/internal/LAYOUT_HARBOR_DONE.md` with before/after tree and commit hash.

## Do not

- Multi-round design review
- Force all benches through LocalProcessSandbox
- Implement Phase F / second harness
- Vendor Harbor source

## Done when

- Tree matches the spirit of the target (src/finagent/{harness,provider,plugins,trial,scorecard}, adapters per bench, cli entry)
- Imports/doctor/tests green
- Pushed; DONE.md written
