# DONE — required / optional rename (bench layer)

Repo: `aowang-ai/finagent-sandbox` only. `finance-agent-eval-infra` untouched.

## Checklist

- [x] Constants: `REQUIRED_SUITE_IDS` (5) + `OPTIONAL_SUITE_IDS` (6) + `BenchTier` / `suite_tier()`. Same membership as the old v1 five + v2 six.
- [x] All 11 ids remain `BenchFactory` equals (`len(_MAP) == 11`).
- [x] `--suites all` / `--suites required` = required five. `--suites optional` = optional six. Hidden `v2` alias kept in `_resolve_wanted` only.
- [x] One scorecard per harness: `reports/GROK_CLI_SCORECARD.*` (or `{HARNESS}_SCORECARD.*`). JSON + markdown carry per-suite `tier` (`required` | `optional`). Completeness still uses the required five. No new `GROK_CLI_SCORECARD_V2` writer.
- [x] `compose_and_write_v2` is a deprecated alias onto the unified card.
- [x] CLI / doctor / adapter comments / README / CONTRIBUTING / GOAL / ARCHITECTURE / MODULES / STATUS / engineering docs: no product-facing “v1 five” / “v2 suites”.
- [x] Engineering status file: `docs/engineering/OPTIONAL_SUITE_STATUS.md` (replaces `V2_SUITE_STATUS.md`). Historical metric values kept.
- [x] Internal helper filenames (`adapters/v2_runtime.py`, `adapters/v2_ops/`, `scripts/v2_suite_ops.py`, `venvs/v2_*`) left as-is; comments say optional-suite glue.
- [x] `./scripts/doctor.sh` exit 0. Unit tests 36 ran, 1 skipped (FinMCP HF bench JSON).
- [x] Commit + push `main` as Ao Wang `<aowang-ai@users.noreply.github.com>`. Remote has no embedded PAT.

## Membership

Required: `ama.multi_market_live`, `finsaber.long_horizon`, `stockbench.daily_sim`, `fintoolbench.tool_compliance`, `deepfund.fund_arena`.

Optional: `investorbench.decision`, `livetradebench.live`, `finmcp.tool_mcp`, `vals_finance_agent.research`, `finsearchcomp.search`, `openpm.portfolio_pit`.
