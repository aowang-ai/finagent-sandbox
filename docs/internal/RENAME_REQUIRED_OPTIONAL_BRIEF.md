# BRIEF — Drop v1/v2 naming → required / optional (bench layer)

Repo: `/workspace/finagent-sandbox` (aowang-ai/finagent-sandbox only)  
Do **not** change `finance-agent-eval-infra`.

## Goal

All 11 suites are **bench-layer** equals in `BenchFactory`. Stop calling them v1/v2.

| Old | New |
| --- | --- |
| v1 five | **required** benches (default completeness / admission set) |
| v2 six | **optional** benches (same factory; skip if deps missing) |
| `GROK_CLI_SCORECARD` vs `_V2` | Prefer **one** harness scorecard path, with per-suite `required`/`optional` (or `tier`) in the report. If a hard cut is needed for back-compat filenames, document alias once then prefer the unified name. |
| `--suites all` = v1 five | `--suites all` or default = **required** set; `--suites optional` / explicit ids for the rest |
| `REQUIRED_SUITE_IDS_V1`, `GROK_CLI_SCORECARD_V2`, docs saying "v1/v2" | Rename symbols and docs |

## Do

1. Introduce clear constants e.g. `REQUIRED_SUITE_IDS`, `OPTIONAL_SUITE_IDS` (or `BenchTier.required|optional` on registry metadata). Keep the same 5 + 6 membership unless BRIEF says otherwise.
2. Update `run_suites` / CLI / doctor / adapters comments / README / CONTRIBUTING / GOAL / ARCHITECTURE / MODULES / engineering docs: **no product-facing v1/v2**.
3. Scorecard: unify naming toward one report per harness (e.g. still `reports/GROK_CLI_SCORECARD.*` for grok-cli). Optional suites appear in the same card with a field, **or** keep writing a secondary file only as deprecated alias with a comment — prefer single card if straightforward.
4. Do not wipe historical metric *values* if any example reports exist; this repo may have empty reports — fine.
5. doctor + unit tests green; factories still 11.
6. Commit + push `main` as Ao Wang <aowang-ai@users.noreply.github.com>. Remote without embedded PAT.
7. Short `docs/internal/RENAME_REQUIRED_OPTIONAL_DONE.md` with checklist.

## Do not

- Multi-round design review
- Touch finance-agent-eval-infra
- Invent new benches or change official protocols
- Force all benches through LocalProcessSandbox

## Done when

- Product/docs/code show no user-facing "v1 five" / "v2 suites" framing (git history ok)
- required/optional is the vocabulary
- push succeeded; print commit hash
