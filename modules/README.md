# Modules

Upstream clones live here locally and are **gitignored**. This repo composes them; it does not vendor their git history.

```bash
# from repo root
./scripts/clone_modules.sh
./scripts/doctor.sh
```

| Dir | Upstream | Role |
| --- | --- | --- |
| `stockbench` | https://github.com/ChenYXxxx/stockbench | Daily portfolio sim (exam room) · v1 |
| `ama` | https://github.com/The-FinAI/Agent_Market_Arena | Live / near-live multi-market (exam room) · v1 |
| `deepfund` | https://github.com/HKUSTDial/DeepFund | Fund arena + decision traces (exam room) · v1 |
| `fintoolbench` | https://github.com/Double-wk/FinToolBench | Tool-call + compliance (exam room) · v1 |
| `finsaber` | https://github.com/waylonli/FINSABER | Long-horizon honesty (suite among equals) · v1 |
| `investorbench` | https://github.com/felis33/INVESTOR-BENCH | Cross-asset decision · `investorbench.decision` · v2 |
| `livetradebench` | https://github.com/ulab-uiuc/live-trade-bench | Live stocks + Polymarket · `livetradebench.live` · v2 |
| `finmcp` | https://github.com/aliyun/qwen-dianjin (`DianJin-TIR/`) | MCP tool orchestration · `finmcp.tool_mcp` · v2 |
| `vals_finance_agent` | https://github.com/vals-ai/finance-agent | SEC/research + tools · `vals_finance_agent.research` · v2 |
| `finsearchcomp` | https://github.com/randomtutu/FinSearchComp | Time-sensitive search · `finsearchcomp.search` · v2 |
| `openpm` | https://github.com/aslcai/OpenPM-Bench | PIT portfolio + audit trail · `openpm.portfolio_pit` · v2 |

See `MODULES.md` at the repo root for entry CLIs, metrics, and pitfalls. Scoring is a parallel scorecard (`GOAL.md`); FINSABER is not a global gate.

Do not commit nested `modules/*/.git`, parquet dumps, or `.venv` trees. If you need a pinned commit, record it in `STATUS.md` / a lock file — do not vendor copies.
