# Goal (locked 2026-09-14)

## North Star

Eval infra that scores **agent harnesses** on authoritative finance benchmarks and emits a unified parallel scorecard, without rewriting upstream engines. Protocols are **composed**, not invented.

## Research framing (paper)

**RQ:** On community-established, protocol-complete finance evaluations, how much does the agent harness (vs the backbone LLM) move results—and do those effects remain stable across trading, honesty, portfolio, tools, and research/search axes?

## Under test

**Current runner:** Grok CLI only.  
**Deferred runners:** Claude Code, Codex, Minara, OpenClaw, Hermes.

## Suite map — locked coverage (2026-09-14)

Authoritative agent-oriented finance evals, grouped by capability axis. Full official protocols — not smoke / subset.

### Wired today (v1)

| Axis | Suite | Upstream |
| --- | --- | --- |
| Decision / trading | StockBench (`stockbench.daily_sim`) | ChenYXxxx/stockbench · arXiv:2510.02209 |
| Decision / trading | AMA (`ama.multi_market_live`) | The-FinAI/Agent_Market_Arena · arXiv:2510.11695 |
| Long-horizon honesty | FINSABER (`finsaber.long_horizon`) | waylonli/FINSABER · arXiv:2505.07078 |
| Portfolio / fund | DeepFund (`deepfund.fund_arena`) | HKUSTDial/DeepFund · arXiv:2505.11065 |
| Tools | FinToolBench (`fintoolbench.tool_compliance`) | Double-wk/FinToolBench · arXiv:2603.08262 |

### Must add (v2) — locked

| Axis | Suite | Why |
| --- | --- | --- |
| Decision / trading | **InvestorBench** | Cross-asset (stock / crypto / ETF) decision env; ACL’25 |
| Decision / trading | **LiveTradeBench** | Live + multi-market (incl. prediction markets); complements AMA/DeepFund |
| Tools | **FinMCP-Bench** | MCP tool orchestration; complements FinToolBench |
| Research / search | **Finance Agent Benchmark (Vals)** | Expert SEC/research tasks + tools |
| Research / search | **FinSearchComp** | Time-sensitive financial search / investigation |

### Portfolio / honesty extension (v2) — locked choice

| Axis | Suite | Note |
| --- | --- | --- |
| Portfolio / PIT | **OpenPM-Bench** (preferred) **or PortBench** | Pick **one** primary; OpenPM preferred next to FINSABER (PIT / audit trail). Do not ship both as required until v3. |
| Long-horizon honesty | OpenPM optional overlap | If OpenPM is chosen above, it also strengthens the honesty axis; FINSABER remains required. |

### Optional later (not required for coverage lock)

| Suite | Role |
| --- | --- |
| FinDeepResearch / FinDeepForecast (OpenFinArena) | Deeper corporate analysis / forecast |
| Herculean | Paper contrast (self-built MCP workflows); **not** a core coverage suite |
| FinBen / FinanceBench / FinQA family | Static knowledge axis only |
| BizFinBench / CNFinBench / FinGAIA | Greater China / multi-vertical business — if product needs CN |

**Target core set after v2:**  
`StockBench + InvestorBench + AMA + LiveTradeBench` · `FINSABER (+ OpenPM if chosen)` · `DeepFund + OpenPM|PortBench` · `FinToolBench + FinMCP-Bench` · `Vals Finance Agent + FinSearchComp`.

## Scoring policy (locked)

**Parallel suites, no single admission kernel.**

- Each suite produces its own `SuiteResult` (pass / fail / skip / error + native metrics).
- The unified `AcceptanceReport` is a **scorecard / profile**, not a one-gate promote.
- FINSABER honesty is **one suite among equals**, not a veto over other axes.
- `admission.decision` means scorecard **completeness** only (e.g. all required suites produced a score).
- Report consumers compare harnesses **per suite** and side-by-side.

**Done (per wave):** Grok CLI runs each required suite end-to-end under that suite’s **complete** official protocol and we emit one unified report. Bitwise paper LLM backbone parity is out of scope; **protocol completeness** is in scope.

## Work mode (locked)

- **Grok Bot:** supervise, brief, monitor, accept/reject, lock goals.
- **Grok CLI:** all code changes and full suite runs.
- Bot does **not** implement bridges/runners itself.

## Non-goals (for now)

- Inventing new task protocols instead of composing upstream exams
- Multi-harness comparison runners (Claude Code / Codex / Minara) before v2 suites are wired
- Public leaderboard product
- Shortening suites to “prove the pipe”
- Single-suite admission veto
- Expanding beyond the locked map above without an explicit goal change
