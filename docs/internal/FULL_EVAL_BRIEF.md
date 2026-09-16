# BRIEF — Full real eval on finagent-sandbox

Repo: `/workspace/finagent-sandbox` only. Do not touch finance-agent-eval-infra.

## Goal

Run a **real, complete** evaluation pass through the Harbor-thin path:

```text
PYTHONPATH=src python -m finagent.cli --harness grok-cli --suites required
```

then optional suites (`--suites optional` or all 11). Prefer one harness scorecard with `tier=required|optional`.

Use existing env (`XAI_API_KEY` / `OPENAI_API_KEY` already in environment). Modules are already under `modules/`.

## Rules

1. **Execute for real** (not only `--dry`), except suites that must skip for missing infra (docker/vLLM/Qdrant, Qieman MCP, OOM) — skip honestly, do not invent protocols.
2. Default host subprocess; FinMCP may opt into LocalProcessSandbox.
3. Do not push `.env` with secrets.
4. Write suite dumps under `artifacts/suite_results/grok-cli/`. Write `reports/GROK_CLI_SCORECARD.*`.
5. Log to `logs/full_eval.log`. Long suites may take hours — keep alive; checkpoint dumps as each suite finishes.
6. When done: summarize per-suite status; commit reports + DONE (not huge binaries). Author Ao Wang <aowang-ai@users.noreply.github.com>. Push without PAT in remote.
7. Write `docs/internal/FULL_EVAL_DONE.md`.

## Do not

- Multi-round design review
- Fake pass on skipped suites
- Force OpenPM if OOM — skip with stamp
- Change official protocols

## Done when

- Required five attempted for real (or clear skip)
- Optional six attempted or honest skip
- Scorecard written; DONE.md + push
