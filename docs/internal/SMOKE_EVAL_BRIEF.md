# BRIEF — Smoke eval: full pipeline, small samples

Repo: `/workspace/finagent-sandbox` only.

## Context

ao stopped the overnight **full** FINSABER/all-data run. Want **smoke**: cover the **complete flow** per bench (harness → factory → official protocol path → dump → scorecard), but **tiny samples**.

## Goal

For each of the 11 benches (required + optional):

1. Go through the real eval path (`PYTHONPATH=src python -m finagent.cli` / Trial when FinMCP opts in).
2. Shrink sample size via existing protocol knobs / env / documented limits — **do not invent a fake protocol**. Prefer:
   - fewer tickers / shorter window / `--limit N` / n_questions=1–3 / one day
   - if a suite has no official shrink knob, run the smallest honest official subset or skip with reason
3. Produce `artifacts/suite_results/grok-cli/{suite}.json` and one `reports/GROK_CLI_SCORECARD.*` with `tier=required|optional`.
4. Missing docker/MCP/OOM → honest **skip**, not fake pass.

## Flow to prove

`HarnessFactory(grok-cli) → BenchFactory → (subprocess | FinMCP sandbox.exec_sync) → SuiteResult dump → scorecard compose`

## Do

1. Confirm full-eval processes are dead (kill leftovers if any).
2. Implement or use smoke flags **only if** they still call the same official entrypoints (e.g. `protocol.extra["smoke"]=true` reducing windows). Prefer adapter-local shrink over rewriting upstream.
3. Run all 11 (or required then optional) in smoke mode; log `logs/smoke_eval.log`.
4. Write `docs/internal/SMOKE_EVAL_DONE.md` with per-suite: status, sample size used, notes.
5. Commit reports + DONE (no secrets). Author Ao Wang <aowang-ai@users.noreply.github.com>. Push without PAT in remote.

## Do not

- Resume full FINSABER 30-ticker marathon
- Fake passes
- Multi-round design review
- Touch finance-agent-eval-infra

## Done when

- Smoke finished for all 11 (pass/fail/skip)
- Scorecard written; DONE.md + push
- Runtime should be minutes–low tens of minutes, not overnight
