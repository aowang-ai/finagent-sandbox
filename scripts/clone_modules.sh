#!/usr/bin/env bash
# Idempotent shallow clone of required + optional upstream evaluation modules.
# Does not fetch HuggingFace parquet, RapidAPI tools, IEX HIST dumps, or LLM weights.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${ROOT}/modules"
DEPTH="${CLONE_DEPTH:-1}"

usage() {
  cat <<'EOF'
Usage: scripts/clone_modules.sh [--help]

Idempotent shallow clone of:

  required
    stockbench    https://github.com/ChenYXxxx/stockbench
    ama           https://github.com/The-FinAI/Agent_Market_Arena
    deepfund    https://github.com/HKUSTDial/DeepFund
    fintoolbench  https://github.com/Double-wk/FinToolBench
    finsaber      https://github.com/waylonli/FINSABER

  optional
    investorbench https://github.com/felis33/INVESTOR-BENCH
    livetradebench https://github.com/ulab-uiuc/live-trade-bench
    finmcp        https://github.com/aliyun/qwen-dianjin  (FinMCP-Bench lives in DianJin-TIR/)
    vals_finance_agent https://github.com/vals-ai/finance-agent
    finsearchcomp https://github.com/randomtutu/FinSearchComp
    openpm        https://github.com/aslcai/OpenPM-Bench

into modules/<name>/. Skips a directory that already has a .git or
non-empty contents (so a local vendor copy is never overwritten).
A failed clone is a warning, not a hard error (optional clones may be private/unavailable).

Env:
  CLONE_DEPTH   git --depth (default 1)
  GIT_TERMINAL_PROMPT is forced off so the script cannot hang on credentials.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

mkdir -p "${DEST}"

clone_one() {
  local name="$1"
  local url="$2"
  local target="${DEST}/${name}"

  if [[ -d "${target}/.git" ]]; then
    local head
    head="$(git -C "${target}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
    echo "[skip] ${name}: already cloned @ ${head}"
    return 0
  fi

  if [[ -d "${target}" ]] && [[ -n "$(ls -A "${target}" 2>/dev/null)" ]]; then
    echo "[skip] ${name}: directory exists and is non-empty (vendored copy, no .git)"
    return 0
  fi

  echo "[clone] ${name} <- ${url} (depth=${DEPTH})"
  if ! GIT_TERMINAL_PROMPT=0 git clone --depth "${DEPTH}" "${url}" "${target}"; then
    echo "[warn] ${name}: clone failed from ${url} (private/unavailable?). Doctor will warn, not fail."
    rm -rf "${target}"
    return 0
  fi
}

clone_one stockbench    "https://github.com/ChenYXxxx/stockbench"
clone_one ama           "https://github.com/The-FinAI/Agent_Market_Arena"
clone_one deepfund    "https://github.com/HKUSTDial/DeepFund"
clone_one fintoolbench  "https://github.com/Double-wk/FinToolBench"
clone_one finsaber      "https://github.com/waylonli/FINSABER"

clone_one investorbench      "https://github.com/felis33/INVESTOR-BENCH"
clone_one livetradebench     "https://github.com/ulab-uiuc/live-trade-bench"
clone_one finmcp             "https://github.com/aliyun/qwen-dianjin"
clone_one vals_finance_agent "https://github.com/vals-ai/finance-agent"
clone_one finsearchcomp      "https://github.com/randomtutu/FinSearchComp"
clone_one openpm             "https://github.com/aslcai/OpenPM-Bench"

echo "[ok] modules are in ${DEST} (gitignored; do not vendor nested .git)"
echo "[note] FinMCP-Bench code/eval is modules/finmcp/DianJin-TIR/ (aliyun/qwen-dianjin hub)."
