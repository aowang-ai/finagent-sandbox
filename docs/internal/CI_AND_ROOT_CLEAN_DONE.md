# DONE — CI + root MD cleanup

Repo: `aowang-ai/finagent-sandbox` only. `finance-agent-eval-infra` untouched.

Author: Ao Wang `<aowang-ai@users.noreply.github.com>`.
Commit: `4fe8d6fb01bdd189c5d212981570efedf46c0fbf` (`4fe8d6f`).
Remote: `https://github.com/aowang-ai/finagent-sandbox.git` (no embedded PAT).

## Checklist

- [x] Deleted root stubs `GOAL.md` / `ARCHITECTURE.md` / `MODULES.md` / `STATUS.md`. Canonical copies stay in `docs/`.
- [x] Root product files: `README.md`, `LICENSE`, `CONTRIBUTING.md`, `.env.example`, `pyproject.toml`, `.gitignore`, `ACCEPTANCE_REPORT.schema.json` (schema left at root; doctor, README, and scorecard still treat it as the public contract).
- [x] Links updated: README, CONTRIBUTING, `modules/README.md`, `scripts/doctor.sh`.
- [x] `docs/README.md` index (Goal / Architecture / Modules / Status / paper / engineering / product / research). One line: `internal/` is maintainer notes.
- [x] `.github/workflows/ci.yml`: push/PR to `main`, Python 3.11, `pip install -e ".[dev]"`, `pytest tests/unit -q`, `./scripts/doctor.sh --ci`. No API keys, no network evals, no smoke eval.
- [x] `scripts/doctor.sh --ci` / `DOCTOR_SKIP_MODULES=1`: still checks src/finagent, adapters, factories, schema; missing `modules/*` is **warn not fail**. Full doctor locally after `clone_modules.sh`.
- [x] Local verify: pytest 40 passed, 1 skipped. Doctor `--ci` with clones: pass=133 fail=0. Doctor `--ci` with all clones hidden: pass=83 warn=12 fail=0.
- [x] Pushed `main`. No review loops.

## Verify

```
pytest tests/unit -q
./scripts/doctor.sh --ci
```
