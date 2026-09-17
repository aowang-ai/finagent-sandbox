# BRIEF — CI + root MD cleanup

Repo: `/workspace/finagent-sandbox` only.

## Why

ao: root feels messy (GOAL/ARCHITECTURE/MODULES/STATUS stubs). Add CI. Keep Harbor-thin public face.

## Do

### 1. Root MD cleanup
- **Delete** root stubs: `GOAL.md`, `ARCHITECTURE.md`, `MODULES.md`, `STATUS.md` (real content already in `docs/`).
- Root should keep only: `README.md`, `LICENSE`, `CONTRIBUTING.md`, `.env.example`, `pyproject.toml`, `.gitignore`, maybe `ACCEPTANCE_REPORT.schema.json` if still used at root — if schema can live under `docs/` or `src/`, move it and fix refs; otherwise leave schema at root once.
- Update README / CONTRIBUTING / doctor / any links that pointed at root `GOAL.md` etc. → `docs/GOAL.md` …
- Optional: add `docs/README.md` index (Goal / Architecture / Modules / Status / paper / engineering). Do **not** delete `docs/internal/` yet; add one line in docs/README that `internal/` is maintainer notes.

### 2. Minimal CI
Add `.github/workflows/ci.yml`:
- on: push/PR to `main`
- python 3.11 (or 3.10+)
- `pip install -e ".[dev]"` or install pytest + package editable with `PYTHONPATH=src`
- run unit tests: `pytest tests/unit -q` (or existing command)
- run `./scripts/doctor.sh` — doctor currently **fails if modules missing**. For CI without cloning 11 heavy repos:
  - Prefer: add `scripts/doctor.sh --ci` or `DOCTOR_SKIP_MODULES=1` that still checks src/finagent, adapters, factories, schema, but **warns** (not fails) on missing `modules/*` entry files
  - Document in workflow comment: full doctor locally after `clone_modules.sh`
- No API keys, no network evals, no smoke eval in CI

### 3. Ship
- Commit + push as Ao Wang <aowang-ai@users.noreply.github.com>, remote without PAT
- Write `docs/internal/CI_AND_ROOT_CLEAN_DONE.md`
- No multi-round review. No finance-agent-eval-infra.

## Done when
- Root has no GOAL/ARCHITECTURE/MODULES/STATUS stubs
- CI workflow exists and is sensible for empty-modules checkout
- doctor+pytest pass in the CI-shaped mode locally
- Pushed
