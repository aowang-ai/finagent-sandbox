# DONE — Harbor-thin layout restructure

Repo: `aowang-ai/finagent-sandbox` only. `finance-agent-eval-infra` untouched.

Commit: `4f72c34dd8bc72841cf11939696411ac8bab09e4` (`4f72c34`).  
Author: Ao Wang `<aowang-ai@users.noreply.github.com>`.

## Checklist

- [x] `src/finagent/{harness,provider,plugins,trial,scorecard}` (+ `benches/` factory wrap, same three registries).
- [x] `adapters/<bench>/` one package per bench; Yahoo / AMA HTTP folded into `adapters/ama/`.
- [x] `cli/run_eval.py` + `python -m finagent.cli` / console script `finagent-eval`.
- [x] `sandbox/` and `runners/` packages removed. No `sandbox` compat shim.
- [x] Product-facing `v2` paths renamed: `adapters/_ops/runtime.py`, per-bench `ops.py`, `cli/optional_suite_ops.py`.
- [x] Root GOAL / ARCHITECTURE / MODULES / STATUS moved to `docs/` with thin stubs.
- [x] `pyproject.toml` src-layout `finagent` + root `adapters`. Doctor + unit tests green.
- [x] No protocol / metric / admission changes. Doctor dummy protocol_hash unchanged: `sha256:47969cdb7942b2a93fe39c9e43463209d943f263c9c21c4a924a53761921b117`.
- [x] Pushed `main`. Remote has no embedded PAT.

## Before

```
adapters/*.py                  flat EnvAdapter modules + v2_ops/ + v2_runtime.py
runners/                       grok, protocols, scorecard, yahoo, ama_http
sandbox/{harness,provider,plugins,benches,runtime}
scripts/run_eval.py            public eval entry
scripts/v2_suite_ops.py
GOAL.md ARCHITECTURE.md MODULES.md STATUS.md   bulky at root
```

## After

```
src/finagent/
  harness/       BaseHarness, HarnessFactory, GrokCliHarness, GrokRunner
  provider/      BaseSandbox, SandboxFactory, LocalProcessSandbox
  plugins/       EnvPlugin, PluginFactory, McpPlugin
  trial/         Trial, TrialConfig, run_suites, dumps
  scorecard/     SuiteResult / AcceptanceReport / write_scorecard
  benches/       BenchFactory + ProtocolFactory + EnvAdapterAsBench wrap
  cli.py         python -m finagent.cli
adapters/
  base.py        ProtocolSpec, Observation, Decision, AgentAdapter, EnvAdapter
  <bench>/       adapter.py (+ ops.py / yahoo.py / http.py where needed)
  _ops/runtime.py
cli/
  run_eval.py
  run_grok_cli_eval.py          thin alias
  optional_suite_ops.py
docs/{GOAL,ARCHITECTURE,MODULES,STATUS}.md
scripts/doctor.sh clone_modules.sh + thin eval shims
```

## Import map (mechanical)

| Old | New |
| --- | --- |
| `sandbox.harness` | `finagent.harness` |
| `sandbox.provider` | `finagent.provider` |
| `sandbox.plugins` | `finagent.plugins` |
| `sandbox.runtime` | `finagent.trial` |
| `sandbox.benches` | `finagent.benches` |
| `runners.grok` | `finagent.harness.grok` |
| `runners.scorecard` | `finagent.scorecard` |
| `runners.protocols` | `finagent.benches.protocols` |
| `runners.yahoo` | `adapters.ama.yahoo` |
| `runners.ama_http` | `adapters.ama.http` |
| `adapters.v2_runtime` | `adapters._ops.runtime` |
| `adapters.v2_ops.<bench>` | `adapters.<bench>.ops` |

`SuiteResult` / `AcceptanceReport` / `skipped_suite` / `write_scorecard` canonical home is `finagent.scorecard`. `adapters.base` lazy-re-exports the types so existing `from adapters.base import SuiteResult` still works. Dataclass fields are unchanged.

## Verify

```
./scripts/doctor.sh     # pass=128 fail=0
PYTHONPATH=src:. python -m unittest tests.unit.test_factory_stubs \
  tests.unit.test_harness_factory tests.unit.test_bench_factory \
  tests.unit.test_plugin_factory tests.unit.test_local_process_sandbox \
  tests.unit.test_trial -q
# 36 ran, 1 skipped (FinMCP HF bench JSON)
PYTHONPATH=src:. python -m finagent.cli --help
```

Single eval entry: `python -m finagent.cli` (also `cli/run_eval.py`, console script `finagent-eval`).
