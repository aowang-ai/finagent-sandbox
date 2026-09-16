# Grok CLI scorecard

- generated_at: `2026-09-16T13:18:25+00:00`
- report_id: `5dab1e04-fe1a-4810-a66d-009439687b12`
- agent: `grok-cli` version `overnight`
- protocol_hash: `sha256:5f62ad6ea50cf7a7040e6735322f3f55433df4b4574cc064c959532869eb55c6`
- scoring: **parallel scorecard** (kernel=`parallel_scorecard`)
- completeness: `reject` — scorecard incomplete: required suite(s) errored: ama.multi_market_live

Per-suite pass/fail is **not** a global veto. FINSABER honesty gates stay on that suite.

| Suite | Tier | Status | Key metrics | Notes |
| --- | --- | --- | --- | --- |
| `ama.multi_market_live` | required | **error** | — | AMA full protocol error: [Errno 98] Address already in use |
| `finsaber.long_horizon` | required | **missing** | — | not yet in this scorecard |
| `stockbench.daily_sim` | required | **missing** | — | not yet in this scorecard |
| `fintoolbench.tool_compliance` | required | **missing** | — | not yet in this scorecard |
| `deepfund.fund_arena` | required | **missing** | — | not yet in this scorecard |

## `ama.multi_market_live`

- status: `error`
- protocol_hash: `sha256:41c11aeebba6201a71c0cf141719b3d84af103e0479233272747fbc73ec3dc68`
- window: `2025-10-22` → `2025-12-06` universe=['BTC', 'ETH', 'ADA', 'SOL', 'DOT', 'LINK', 'UNI', 'MATIC', 'AVAX', 'ATOM', 'TSLA', 'AAPL']…
- upstream: `POST /trading_action/ + harvest action/*_trading_decisions.json`

AMA full protocol error: [Errno 98] Address already in use

## Notes

Parallel scorecard for Grok CLI. Required benches drive completeness; optional benches skip if deps are missing. Per-suite pass/fail is not a veto. backend=api model=grok-4.20-0309-non-reasoning.

