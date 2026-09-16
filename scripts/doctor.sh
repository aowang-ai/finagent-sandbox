#!/usr/bin/env bash
# Infra doctor: structural health of the composed evaluation repo.
# No API keys, no dataset downloads, no LLM calls.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

RED=$'\033[31m'
GRN=$'\033[32m'
YLW=$'\033[33m'
DIM=$'\033[2m'
RST=$'\033[0m'

FAILS=0
WARNS=0
PASSES=0

pass() { PASSES=$((PASSES + 1)); printf '%s[pass]%s %s\n' "${GRN}" "${RST}" "$*"; }
warn() { WARNS=$((WARNS + 1)); printf '%s[warn]%s %s\n' "${YLW}" "${RST}" "$*"; }
fail() { FAILS=$((FAILS + 1)); printf '%s[fail]%s %s\n' "${RED}" "${RST}" "$*"; }

usage() {
  cat <<'EOF'
Usage: scripts/doctor.sh [--help]

Checks (no network, no API keys):
  - product skeleton (docs / adapters / schema / product scripts)
  - does not require overnight/campaign scripts
  - v1 modules/<name> present with official entry files (fail if missing)
  - v2 modules optional: warn if missing, never fail doctor
  - git remote + HEAD for each cloned module (if .git exists)
  - ACCEPTANCE_REPORT.schema.json parses
  - adapters package imports (stdlib only), including v2 adapters
  - optional --help / py_compile smoke when cheap

Exit 0 iff every structural check passed. Optional smokes are warnings.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

echo "=== finagent-sandbox doctor ==="
echo "root: ${ROOT}"
echo "cwd:  $(pwd)"
echo "python: $(command -v python3 || echo missing)"
echo "api keys: not required (doctor never reads OPENAI/POLYGON/FINNHUB/SUPABASE)"
echo

# ---------------------------------------------------------------------------
# Deliverables
# ---------------------------------------------------------------------------
echo "-- deliverables --"
REQUIRED_FILES=(
  README.md
  LICENSE
  CONTRIBUTING.md
  .env.example
  GOAL.md
  ARCHITECTURE.md
  MODULES.md
  STATUS.md
  ACCEPTANCE_REPORT.schema.json
  pyproject.toml
  docs/product/POSITIONING.md
  docs/engineering/GLUE.md
  adapters/base.py
  adapters/stockbench.py
  adapters/ama.py
  adapters/deepfund.py
  adapters/fintoolbench.py
  adapters/finsaber.py
  adapters/investorbench.py
  adapters/livetradebench.py
  adapters/finmcp.py
  adapters/vals_finance_agent.py
  adapters/finsearchcomp.py
  adapters/openpm.py
  adapters/v2_runtime.py
  docs/engineering/V2_SUITE_STATUS.md
  docs/paper/HARBOR_NORMS.md
  docs/paper/SANDBOX_REPO_DESIGN.md
  docs/paper/MIGRATION_PLAN.md
  scripts/doctor.sh
  scripts/clone_modules.sh
  scripts/run_grok_cli_eval.py
  scripts/run_eval.py
  scripts/v2_suite_ops.py
  sandbox/harness/base.py
  sandbox/harness/grok_cli.py
  sandbox/runtime/dumps.py
  sandbox/runtime/run_suites.py
  sandbox/benches/base.py
  sandbox/benches/wrap.py
  sandbox/provider/base.py
  sandbox/provider/factory.py
  sandbox/provider/local_process.py
  sandbox/runtime/config.py
  sandbox/runtime/trial.py
  tests/unit/test_harness_factory.py
  tests/unit/test_bench_factory.py
  tests/unit/test_local_process_sandbox.py
  tests/unit/test_trial.py
  sandbox/plugins/base.py
  sandbox/plugins/mcp.py
  tests/unit/test_plugin_factory.py
  runners/scorecard.py
  runners/grok.py
  runners/protocols.py
  .gitignore
  modules/README.md
)
for f in "${REQUIRED_FILES[@]}"; do
  if [[ -f "${ROOT}/${f}" ]]; then
    pass "file ${f}"
  else
    fail "missing ${f}"
  fi
done

if grep -q 'modules/\*' "${ROOT}/.gitignore" && grep -q '!modules/README.md' "${ROOT}/.gitignore"; then
  pass "gitignore keeps modules/ out except README"
else
  fail "gitignore must ignore modules/* except modules/README.md"
fi

# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------
echo
echo "-- modules --"

check_module() {
  local name="$1"
  shift
  local dir="${ROOT}/modules/${name}"
  if [[ ! -d "${dir}" ]]; then
    fail "module missing: modules/${name}  (run scripts/clone_modules.sh)"
    return
  fi
  pass "module dir modules/${name}"

  local rel
  for rel in "$@"; do
    if [[ -e "${dir}/${rel}" ]]; then
      pass "  entry ${name}/${rel}"
    else
      fail "  missing entry ${name}/${rel}"
    fi
  done

  if [[ -d "${dir}/.git" ]]; then
    local remote head subject
    remote="$(git -C "${dir}" remote get-url origin 2>/dev/null || echo '(no origin)')"
    head="$(git -C "${dir}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
    subject="$(git -C "${dir}" log -1 --format='%s' 2>/dev/null || echo '')"
    echo "       ${DIM}remote=${remote}${RST}"
    echo "       ${DIM}HEAD=${head} ${subject}${RST}"
  else
    warn "  modules/${name} has no .git (vendored copy); version unknown"
  fi
}

check_module stockbench \
  README.md \
  scripts/run_benchmark.sh \
  stockbench/apps/run_backtest.py \
  config.yaml

check_module ama \
  README.md \
  testbed/get_daily_action.py \
  testbed/get_return.py \
  testbed/auto_daily_action.sh \
  testbed/configs/agents.json

check_module deepfund \
  README.md \
  src/main.py \
  src/database/sqlite_setup.py \
  TECHNICAL_GUIDE.md

check_module fintoolbench \
  README.md \
  code_bench/evaluate/run_relative_eval.py \
  tools/tools_all_annotated.jsonl \
  data/question/select_data_real_remove_duplicates.jsonl

check_module finsaber \
  README.md \
  pyproject.toml \
  backtest/finsaber.py \
  backtest/toolkit/metrics.py

# v2 modules: warn (do not fail) if optional clones are absent.
check_optional_module() {
  local name="$1"
  shift
  local dir="${ROOT}/modules/${name}"
  if [[ ! -d "${dir}" ]]; then
    warn "optional v2 module missing: modules/${name}  (run scripts/clone_modules.sh)"
    return
  fi
  pass "optional module dir modules/${name}"

  local rel
  for rel in "$@"; do
    if [[ -e "${dir}/${rel}" ]]; then
      pass "  entry ${name}/${rel}"
    else
      warn "  missing optional entry ${name}/${rel}"
    fi
  done

  if [[ -d "${dir}/.git" ]]; then
    local remote head subject
    remote="$(git -C "${dir}" remote get-url origin 2>/dev/null || echo '(no origin)')"
    head="$(git -C "${dir}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
    subject="$(git -C "${dir}" log -1 --format='%s' 2>/dev/null || echo '')"
    echo "       ${DIM}remote=${remote}${RST}"
    echo "       ${DIM}HEAD=${head} ${subject}${RST}"
  else
    warn "  modules/${name} has no .git (vendored copy); version unknown"
  fi
}

echo
echo "-- optional v2 modules (warn if missing; do not fail doctor) --"

check_optional_module investorbench \
  README.md \
  run.py \
  data/msft.json

check_optional_module livetradebench \
  README.md \
  pyproject.toml \
  live_trade_bench/systems/stock_system.py

check_optional_module finmcp \
  README.md \
  DianJin-TIR/README.md \
  DianJin-TIR/eval/evaluation.py

check_optional_module vals_finance_agent \
  README.md \
  finance_agent/run_agent.py \
  data/public.txt

check_optional_module finsearchcomp \
  README.md \
  finsearchcomp/eval/eval.py \
  data/finsearchcomp_data.json

check_optional_module openpm \
  README.md \
  pyproject.toml \
  agents/portfolio/__main__.py

# ---------------------------------------------------------------------------
# Schema + adapters (cheap Python, stdlib only)
# ---------------------------------------------------------------------------
echo
echo "-- schema & adapters (no third-party imports) --"

if command -v python3 >/dev/null 2>&1; then
  if python3 - <<'PY'
import json, pathlib, sys
p = pathlib.Path("ACCEPTANCE_REPORT.schema.json")
data = json.loads(p.read_text(encoding="utf-8"))
assert data.get("$schema"), "schema missing $schema"
assert data.get("title"), "schema missing title"
required = data.get("required") or []
for key in ("schema_version", "report_id", "agent", "protocol_hash", "suites", "admission"):
    if key not in required:
        raise SystemExit(f"schema.required missing {key}")
print("schema keys:", ", ".join(sorted(data.get("properties", {}))))
PY
  then
    pass "ACCEPTANCE_REPORT.schema.json parses and has required keys"
  else
    fail "ACCEPTANCE_REPORT.schema.json invalid"
  fi

  COMPILE_FILES=(
    adapters/base.py
    adapters/stockbench.py
    adapters/ama.py
    adapters/deepfund.py
    adapters/fintoolbench.py
    adapters/finsaber.py
    adapters/investorbench.py
    adapters/livetradebench.py
    adapters/finmcp.py
    adapters/vals_finance_agent.py
    adapters/finsearchcomp.py
    adapters/openpm.py
    adapters/v2_runtime.py
    adapters/v2_ops/__init__.py
    adapters/v2_ops/finsearchcomp.py
    adapters/v2_ops/vals_finance_agent.py
    adapters/v2_ops/livetradebench.py
    adapters/__init__.py
    sandbox/__init__.py
    sandbox/harness/__init__.py
    sandbox/harness/factory.py
    sandbox/harness/base.py
    sandbox/harness/grok_cli.py
    sandbox/benches/__init__.py
    sandbox/benches/factory.py
    sandbox/benches/base.py
    sandbox/benches/wrap.py
    sandbox/plugins/__init__.py
    sandbox/plugins/factory.py
    sandbox/plugins/base.py
    sandbox/plugins/mcp.py
    sandbox/provider/__init__.py
    sandbox/provider/base.py
    sandbox/provider/factory.py
    sandbox/provider/local_process.py
    sandbox/runtime/__init__.py
    sandbox/runtime/config.py
    sandbox/runtime/dumps.py
    sandbox/runtime/run_suites.py
    sandbox/runtime/trial.py
    tests/unit/test_factory_stubs.py
    tests/unit/test_harness_factory.py
    tests/unit/test_bench_factory.py
    tests/unit/test_local_process_sandbox.py
    tests/unit/test_trial.py
    tests/unit/test_plugin_factory.py
  )
  for extra in runners/__init__.py runners/grok.py runners/ama_http.py runners/scorecard.py runners/protocols.py scripts/run_grok_cli_eval.py scripts/run_eval.py scripts/v2_suite_ops.py; do
    if [[ -f "${ROOT}/${extra}" ]]; then
      COMPILE_FILES+=("${extra}")
    fi
  done
  if python3 -m py_compile "${COMPILE_FILES[@]}"
  then
    pass "adapters/*.py (+ runners if present) compile"
  else
    fail "adapters py_compile failed"
  fi

  if PYTHONPATH="${ROOT}" python3 - <<'PY'
from adapters.base import (
    ALL_SUITE_IDS,
    PLANNED_SUITE_IDS_V2,
    REQUIRED_SUITE_IDS_V1,
    AgentAdapter,
    AgentIdentity,
    EnvAdapter,
    Observation,
    Decision,
    ProtocolSpec,
    SuiteResult,
    compose_acceptance_report,
    canonical_protocol_hash,
    evaluate_admission,
    skipped_suite,
)
from adapters.stockbench import StockBenchEnvAdapter
from adapters.ama import AmaEnvAdapter
from adapters.deepfund import DeepFundEnvAdapter
from adapters.fintoolbench import FinToolBenchEnvAdapter
from adapters.finsaber import FinsaberEnvAdapter
from adapters.investorbench import InvestorBenchEnvAdapter
from adapters.livetradebench import LiveTradeBenchEnvAdapter
from adapters.finmcp import FinMcpEnvAdapter
from adapters.vals_finance_agent import ValsFinanceAgentEnvAdapter
from adapters.finsearchcomp import FinSearchCompEnvAdapter
from adapters.openpm import OpenPmEnvAdapter

class Dummy:
    agent_id = "dummy-v0"
    def capabilities(self):
        return set()
    def decide(self, observation: Observation) -> Decision:
        return Decision(action="HOLD", reasoning="doctor smoke")

agent = Dummy()
assert isinstance(agent, AgentAdapter)

assert ALL_SUITE_IDS == REQUIRED_SUITE_IDS_V1 + PLANNED_SUITE_IDS_V2
assert set(REQUIRED_SUITE_IDS_V1).isdisjoint(PLANNED_SUITE_IDS_V2)
assert len(REQUIRED_SUITE_IDS_V1) == 5
assert len(PLANNED_SUITE_IDS_V2) == 6

envs = [
    StockBenchEnvAdapter(),
    AmaEnvAdapter(),
    DeepFundEnvAdapter(),
    FinToolBenchEnvAdapter(),
    FinsaberEnvAdapter(),
]
suites = []
for env in envs:
    assert isinstance(env, EnvAdapter)
    proto = ProtocolSpec(suite_id=env.suite_id)
    result = env.run(agent, proto)
    assert isinstance(result, SuiteResult)
    assert result.status == "skip", result
    suites.append(result)

v2_envs = [
    InvestorBenchEnvAdapter(),
    LiveTradeBenchEnvAdapter(),
    FinMcpEnvAdapter(),
    ValsFinanceAgentEnvAdapter(),
    FinSearchCompEnvAdapter(),
    OpenPmEnvAdapter(),
]
for env in v2_envs:
    assert isinstance(env, EnvAdapter)
    proto = ProtocolSpec(suite_id=env.suite_id)
    result = env.run(agent, proto)
    assert isinstance(result, SuiteResult)
    assert result.status == "skip", result
    assert result.upstream_cli, env.suite_id
    assert env.suite_id in PLANNED_SUITE_IDS_V2

report = compose_acceptance_report(
    AgentIdentity(agent_id="dummy-v0", name="doctor-dummy"),
    suites,
    report_id="doctor-smoke",
)
assert report.admission.decision == "hold", report.admission
assert report.admission.kernel == "parallel_scorecard", report.admission
assert report.protocol_hash.startswith("sha256:")
assert canonical_protocol_hash(suites[0].protocol).startswith("sha256:")
assert list(report.admission.required_suites) == list(REQUIRED_SUITE_IDS_V1)

# Parallel scorecard: FINSABER fail must not veto other suites.
# Completeness uses v1 required ids so v2 skips cannot HOLD forever.
scored = []
for sid in REQUIRED_SUITE_IDS_V1:
    scored.append(SuiteResult(
        suite_id=sid,
        status="fail" if sid == "finsaber.long_horizon" else "pass",
        protocol=ProtocolSpec(suite_id=sid),
    ))
scored_report = evaluate_admission(scored)
assert scored_report.decision == "promote", scored_report
assert "veto" not in scored_report.rationale.lower() or "not a veto" in scored_report.rationale.lower()
print("admission=", report.admission.decision, "suites=", [s.suite_id for s in suites])
print("protocol_hash=", report.protocol_hash)
print("parallel_scorecard_complete=", scored_report.decision)
print("v2_planned=", list(PLANNED_SUITE_IDS_V2))

from runners.scorecard import SUITE_METRIC_PREFER, _metric_summary, render_markdown
from adapters.base import Metric, compose_acceptance_report
from adapters.fintoolbench import QUESTION_ALIASES, _resolve_questions_path
assert set(SUITE_METRIC_PREFER) == set(ALL_SUITE_IDS)
assert "full" in QUESTION_ALIASES
from pathlib import Path
_q = _resolve_questions_path(Path("."), "full")
assert _q.name.endswith(".jsonl") or not _q.exists() or _q.is_file()
ama = SuiteResult(
    suite_id="ama.multi_market_live",
    status="pass",
    protocol=ProtocolSpec(suite_id="ama.multi_market_live"),
    metrics=[
        Metric(name="n_assets", value=22.0),
        Metric(name="n_http_ok", value=920.0),
        Metric(name="mean_total_return", value=-3.8),
    ],
)
assert "n_assets=22.0" in _metric_summary(ama)
md = render_markdown(
    compose_acceptance_report(
        AgentIdentity(agent_id="dummy-v0"),
        scored,
        report_id="doctor-scorecard",
    )
)
assert "parallel scorecard" in md.lower()
assert "global veto" in md.lower()
print("scorecard_prefer_ok")
PY
  then
    pass "adapters import + dummy AgentAdapter → v1 five skipped → HOLD; v2 stubs skip; FINSABER fail does not veto"
  else
    fail "adapters import / compose smoke failed"
  fi

  if PYTHONPATH="${ROOT}" python3 - <<'PY'
import sandbox
from sandbox.benches.factory import BenchFactory
from sandbox.harness.factory import HarnessFactory
from sandbox.plugins.factory import PluginFactory
from sandbox.provider.local_process import LocalProcessSandbox
from sandbox.runtime.trial import Trial
from adapters.base import ALL_SUITE_IDS

assert sandbox.__doc__ and "FinAgentSandbox" in sandbox.__doc__
assert list(HarnessFactory._MAP) == ["grok-cli"]
assert set(BenchFactory._MAP) == set(ALL_SUITE_IDS)
assert len(BenchFactory._MAP) == 11
assert list(PluginFactory._MAP) == ["mcp"]

try:
    HarnessFactory.create("claude-code")
except ValueError as exc:
    assert "grok-cli" in str(exc), exc
else:
    raise SystemExit("expected ValueError for unknown harness")

h = HarnessFactory.create("grok-cli")
assert h.name() == "grok-cli", h.name()

b = BenchFactory.create("finsaber.long_horizon")
assert b.suite_id == "finsaber.long_horizon", b.suite_id
assert hasattr(b, "run_official")
from sandbox.benches.wrap import EnvAdapterAsBench, FinMcpEnvAdapterAsBench
assert isinstance(b, EnvAdapterAsBench)

try:
    BenchFactory.create("not.a.suite")
except ValueError as exc:
    assert "finsaber.long_horizon" in str(exc) or "stockbench.daily_sim" in str(exc), exc
else:
    raise SystemExit("expected ValueError for unknown bench")

p = PluginFactory.create("mcp")
assert p.name() == "mcp"
try:
    PluginFactory.create("yahoo")
except ValueError as exc:
    assert "mcp" in str(exc), exc
else:
    raise SystemExit("expected ValueError listing mcp for unknown plugin")

finmcp_bench = BenchFactory.create("finmcp.tool_mcp")
assert isinstance(finmcp_bench, FinMcpEnvAdapterAsBench)
assert finmcp_bench.opt_in_sandbox is True

assert LocalProcessSandbox.type() == "local-process"
assert Trial is not None
print("sandbox_factories_ok", list(HarnessFactory._MAP), h.name(), b.suite_id, len(BenchFactory._MAP))
PY
  then
    pass "import sandbox + HarnessFactory.create(grok-cli) + BenchFactory wrap + McpPlugin"
  else
    fail "sandbox factory import failed"
  fi

  if PYTHONPATH="${ROOT}" python3 -m unittest tests.unit.test_factory_stubs tests.unit.test_harness_factory tests.unit.test_bench_factory tests.unit.test_local_process_sandbox tests.unit.test_trial tests.unit.test_plugin_factory -q
  then
    pass "tests.unit factory/harness/bench/sandbox/trial/plugin"
  else
    fail "sandbox unit tests failed"
  fi
else
  fail "python3 not on PATH"
fi

# ---------------------------------------------------------------------------
# Optional cheap --help (warnings only; deps may be missing)
# ---------------------------------------------------------------------------
echo
echo "-- optional smokes (warnings only) --"

if [[ -x "${ROOT}/scripts/clone_modules.sh" ]]; then
  pass "clone_modules.sh is executable"
else
  warn "chmod +x scripts/clone_modules.sh recommended"
fi

if [[ -x "${ROOT}/scripts/doctor.sh" ]]; then
  pass "doctor.sh is executable"
else
  warn "chmod +x scripts/doctor.sh recommended"
fi

if [[ -x "${ROOT}/scripts/run_grok_cli_eval.py" ]]; then
  pass "run_grok_cli_eval.py is executable"
else
  warn "chmod +x scripts/run_grok_cli_eval.py recommended"
fi

if [[ -x "${ROOT}/scripts/run_eval.py" ]]; then
  pass "run_eval.py is executable"
else
  warn "chmod +x scripts/run_eval.py recommended"
fi

for leftover in \
  scripts/run_remaining_suites.sh \
  scripts/stamp_overnight_status.py \
  scripts/wait_finsaber_then_remaining.sh \
  scripts/watch_overnight_eval.py \
  scripts/v2_continue_finsearch.py \
  scripts/v2_continue_vals.py \
  scripts/v2_continue_livetrade.py \
  scripts/v2_continue_harvest.py \
  scripts/v2_continue_progress.py
do
  if [[ -e "${ROOT}/${leftover}" ]]; then
    warn "campaign leftover still at ${leftover}; remove it (v2 ops live in scripts/v2_suite_ops.py)"
  fi
done

if [[ -x "${ROOT}/scripts/v2_suite_ops.py" ]]; then
  pass "v2_suite_ops.py is executable"
else
  warn "chmod +x scripts/v2_suite_ops.py recommended"
fi

echo
echo "-- optional v2 venvs (warn if missing; do not fail doctor) --"
for venv_name in v2_finsearch v2_vals v2_livetrade v2_openpm v2_finmcp; do
  if [[ -x "${ROOT}/venvs/${venv_name}/bin/python" ]]; then
    pass "venv venvs/${venv_name}"
  else
    warn "optional venv missing: venvs/${venv_name} (v2 execute falls back to sys.executable)"
  fi
done

if [[ -f "${ROOT}/reports/GROK_CLI_SCORECARD.md" && -f "${ROOT}/reports/GROK_CLI_SCORECARD.json" ]]; then
  pass "reports/GROK_CLI_SCORECARD.{md,json} present"
else
  warn "Grok CLI scorecard files missing under reports/"
fi

if [[ -d "${ROOT}/artifacts/suite_results" ]]; then
  pass "artifacts/suite_results/ present"
else
  warn "artifacts/suite_results/ missing (gitignored; preserve local copies)"
fi

# StockBench typer --help is cheap *if* the package is importable. Skip otherwise.
if PYTHONPATH="${ROOT}/modules/stockbench" python3 -c "import stockbench.apps.run_backtest" >/dev/null 2>&1; then
  if PYTHONPATH="${ROOT}/modules/stockbench" python3 -m stockbench.apps.run_backtest --help >/dev/null 2>&1; then
    pass "stockbench.apps.run_backtest --help"
  else
    warn "stockbench importable but --help failed"
  fi
else
  warn "stockbench not importable in this interpreter (install skipped; ok)"
fi

echo
echo "=== summary  pass=${PASSES}  warn=${WARNS}  fail=${FAILS} ==="
if [[ "${FAILS}" -ne 0 ]]; then
  echo "doctor failed. Clone modules with scripts/clone_modules.sh if they are missing."
  exit 1
fi
echo "doctor ok. Parallel scorecard: skipped suites yield HOLD (incomplete), not a FINSABER veto."
exit 0
