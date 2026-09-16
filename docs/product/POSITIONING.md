# Positioning — admission infra, not a public alpha leaderboard

## What we sell

A **promotion gate** for finance agents.

A team brings an agent (a model + tools + prompts + a book). We run it through versioned protocols and return a **signable scorecard**: per-suite pass/fail plus a completeness bit (`promote` / `hold` / `reject`). FINSABER honesty (long horizon, next-open execution, costs, no cherry-picked survivors) is one suite among equals. StockBench, AMA, DeepFund, and FinToolBench are scored in parallel — none of them, including FINSABER, vetoes another.

We do **not** sell:

- a trading bot, a broker, or a live strategy
- a public "who has more alpha" leaderboard
- bitwise reproduction of any one paper's table

The artifact the customer keeps is the report + the protocol hash, not a rank.

## Why this is a different product

Public leaderboards answer: *which name looks best on last month's tape?*

Admission infra answers: *may this agent be promoted into paper (or stay in the lab), given an honest exam paper?*

Those questions diverge as soon as:

- the universe is today's survivors
- fills happen at the same close as date-only news
- costs and liquidity are zero
- the eval date is after the model's training cutoff but the data is replayed as if live
- tool calls ignore timeliness / intent / regulatory domain

FINSABER exists because LLM traders look brilliant on cherry-picks and collapse on a long, biased-against-you window. DeepFund's own paper is titled **Time Travel is Cheating**. We take both seriously: honesty is a first-class suite, live rooms exist to stop time travel, and we still refuse to turn either into a public alpha board or a single veto.

## Versus nearby products

### Paradoox / DeepFund Arena

DeepFund collaborates with Paradoox AI and publishes a **live fund arena** (demo: `https://deepfund.paradoox.ai/`). That is a research + go-to-market surface: models race in public, traces go to a database, the metaphor is a car race.

We **compose** DeepFund as an exam room (fund/portfolio traces, chronological `trading-date`, `--local-db`). We do not operate or compete with their public arena.

| | Paradoox / DeepFund Arena | This infra |
| --- | --- | --- |
| Audience | public / research demo | internal promotion, compliance, research ops |
| Output | leaderboard, race view | Acceptance Report (`promote/hold/reject`) |
| Default question | who's winning live? | is the protocol honest enough to promote? |
| Scoring | live arena | parallel scorecard; FINSABER honesty is one suite |

If a customer wants a public scoreboard, they already have Paradoox. If they want to *refuse* a model that only wins on cherry-picks, they need us.

### Vals

Vals (vals.ai and related eval products) sells **model evaluation** and public-facing leaderboards across general and domain benchmarks. The unit is usually a model name; the output is a rank and a methodology page.

We evaluate an **agent-in-a-protocol** (tools, fills, universe, costs), not a naked LLM. A Vals-style "GPT-X beats Claude-Y on finance QA" does not tell you whether the same stack looks ahead, ignores liquidity, or routes to a stale RapidAPI. Those are admission questions.

Compatible, not competing: a Vals score can be an *optional metric* on a report. It cannot be the gate.

### Patronus

Patronus-class products (hallucination, RAG faithfulness, judge scorers, enterprise eval harnesses) excel at **text quality** and policy checks on generations.

Finance agents fail in ways a faithfulness judge will not see:

- same-close fill on date-only 10-K text
- buying 20% of daily volume at the print
- testing only names that still exist
- calling a delayed quote tool for a "now" question (FinToolBench TMR)
- mixing intent (screening vs execution) or regulatory domain

We will happily harvest Patronus-style judges **inside** FinToolBench's SoftScore / compliance mismatch rates. We will not substitute them for FINSABER fills.

## What "admission" means in practice

```
lab → parallel suites (AMA, FINSABER, StockBench, FinTool, DeepFund) → scorecard → paper → (not our product) live
```

| Decision | Operational meaning |
| --- | --- |
| `promote` | Scorecard complete: every required suite produced a score (pass or fail). Read the per-suite rows. |
| `hold` | Scorecard incomplete: a required suite is missing or skipped. |
| `reject` | A required suite errored (could not be scored). |

A pretty StockBench Sortino on DJIA-20 over three months is one suite row. It does not hide a FINSABER honesty fail, and a FINSABER fail does not hide it.

## What we will say in public, and what we won't

**Will say**

- We compose StockBench, AMA, DeepFund, FinToolBench, FINSABER.
- The unit of value is a signable Acceptance Report over a hashed protocol.
- FINSABER honesty is a first-class suite; other modules are scored in parallel (no veto).
- Live rooms exist because historical replay can cheat.

**Won't say**

- "We reproduced Table 3 of paper X bit-for-bit."
- "Our leaderboard of LLM alphas."
- "This agent is safe to trade live capital." (promotion ≠ brokerage)
- "We replace Paradoox / Vals / Patronus."

## One-line

**Paradoox races agents in public. Vals ranks models. Patronus judges text. We decide whether a finance agent is allowed to graduate — and we make the exam paper hashable.**
