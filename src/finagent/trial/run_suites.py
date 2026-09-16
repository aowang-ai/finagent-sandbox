"""Shared eval loop for cli/run_eval.py and cli/run_grok_cli_eval.py.

Harness construction goes through HarnessFactory. Benches and protocols
go through BenchFactory / ProtocolFactory. Dumps write under
artifacts/suite_results/<harness>/. A harness that cannot sit a bench skips
(not HOLD-fill).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from finagent._paths import REPO_ROOT as ROOT
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

VENV_PYTHON = Path("/workspace/finance-agent-p0/FINSABER/.venv/bin/python")


def default_eval_python() -> str:
    env = os.environ.get("EVAL_PYTHON")
    if env:
        return env
    if VENV_PYTHON.is_file():
        return str(VENV_PYTHON)
    local = ROOT / ".venv" / "bin" / "python"
    if local.is_file():
        return str(local)
    return sys.executable


def ensure_eval_python() -> None:
    """Re-exec under the FINSABER venv so in-process suites (pandas, langchain) import."""

    wanted = Path(default_eval_python()).resolve()
    current = Path(sys.executable).resolve()
    if wanted == current or not wanted.is_file():
        return
    os.environ.setdefault("EVAL_PYTHON", str(wanted))
    os.execv(str(wanted), [str(wanted), *sys.argv])


from adapters.base import (
    ALL_SUITE_IDS,
    OPTIONAL_SUITE_IDS,
    REQUIRED_SUITE_IDS,
    ProtocolSpec,
)
from finagent.scorecard.types import (
    AgentIdentity,
    SuiteResult,
    SuiteStatus,
    compose_acceptance_report,
    skipped_suite,
)
from adapters._ops.runtime import repo_venv_python
from finagent.scorecard.write import write_scorecard
from finagent.benches.factory import BenchFactory, ProtocolFactory, SUITE_ALIASES
from finagent.harness.factory import HarnessFactory
from finagent.trial.dumps import dump_suite, load_suite

OPTIONAL_VENV = {
    "investorbench.decision": "v2_investor",
    "livetradebench.live": "v2_livetrade",
    "finmcp.tool_mcp": "v2_finmcp",
    "vals_finance_agent.research": "v2_vals",
    "finsearchcomp.search": "v2_finsearch",
    "openpm.portfolio_pit": "v2_openpm",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _suite_status_on_disk(sid: str, *, harness_name: str = "grok-cli") -> str | None:
    loaded = load_suite(sid, harness_name=harness_name)
    if loaded is None:
        return None
    return str(loaded.status) if loaded.status else None


def _morning_ready_stamp(*, harness_name: str = "grok-cli") -> str:
    """Morning-ready only when every required suite has a non-error SuiteResult."""

    for sid in REQUIRED_SUITE_IDS:
        st = _suite_status_on_disk(sid, harness_name=harness_name)
        if st is None or st == SuiteStatus.ERROR.value:
            return "not yet"
    return "yes"


def _remaining_suite_ids(*, harness_name: str = "grok-cli") -> list[str]:
    leftover: list[str] = []
    for sid in REQUIRED_SUITE_IDS:
        st = _suite_status_on_disk(sid, harness_name=harness_name)
        if st is None or st == SuiteStatus.ERROR.value:
            leftover.append(f"{sid} ({st or 'missing'})")
    return leftover


def write_status(
    *,
    live: str,
    completed: list[str],
    blockers: list[str],
    next_action: str,
    errored: list[str] | None = None,
    harness_name: str = "grok-cli",
) -> None:
    status_dir = ROOT / "status"
    status_dir.mkdir(parents=True, exist_ok=True)
    path = status_dir / "eval.md"
    completed_txt = "\n".join(f"- {c}" for c in completed) or "- (none yet)"
    blockers_txt = "\n".join(f"- {b}" for b in blockers) or "- (none yet)"
    if errored is None:
        errored = [
            c
            for c in completed
            if "status=error" in c or "(cached error)" in c
        ]
    leftover = _remaining_suite_ids(harness_name=harness_name)
    morning = _morning_ready_stamp(harness_name=harness_name)
    if leftover and morning != "yes":
        next_action = (
            next_action.rstrip(".")
            + f"; remaining non-error suites still needed: {', '.join(leftover)}. "
            "Do not stamp morning-ready. Prefer scripts/run_remaining_suites.sh "
            "once finsaber.long_horizon is pass/fail/skip and its eval PID is gone."
        )
        if "idle" in live.lower():
            live = f"orchestrator subset finished; remaining: {', '.join(leftover)}"
    errored_txt = "\n".join(f"- {c}" for c in errored) or "- (none)"
    leftover_txt = "\n".join(f"- {c}" for c in leftover) or "- (none)"
    path.write_text(
        "# Overnight status\n\n"
        f"Updated: {utc_now()}\n"
        "Mandate: Bot supervises; Grok CLI implements full GOAL.md overnight.\n"
        "Scoring: **parallel scorecard — no FINSABER admission kernel veto.**\n\n"
        "## Live\n\n"
        f"- {live}\n\n"
        "## Completed\n\n"
        f"{completed_txt}\n\n"
        "## Errored\n\n"
        f"{errored_txt}\n\n"
        "## Remaining (error or missing SuiteResult)\n\n"
        f"{leftover_txt}\n\n"
        "## Blockers (documented; do not idle)\n\n"
        f"{blockers_txt}\n\n"
        "## Next action\n\n"
        f"- {next_action}\n"
        f"- morning-ready: {morning}\n",
        encoding="utf-8",
    )
    prog = status_dir / "progress.md"
    prog.write_text(
        "# Progress\n\n"
        f"Updated: {utc_now()}\n\n"
        f"- live: {live}\n"
        f"- completed: {', '.join(completed) or 'none'}\n"
        f"- errored: {', '.join(errored) or 'none'}\n"
        f"- remaining: {', '.join(leftover) or 'none'}\n"
        f"- next: {next_action}\n"
        f"- morning-ready: {morning}\n",
        encoding="utf-8",
    )


def _scorecard_names(harness_name: str) -> tuple[str, str | None]:
    """One scorecard per harness. grok-cli → reports/GROK_CLI_SCORECARD.*."""

    if harness_name == "grok-cli":
        return "GROK_CLI", None
    stem = harness_name.upper().replace("-", "_")
    return stem, None


def compose_and_write(suites: list[SuiteResult], notes: str, *, harness_name: str = "grok-cli") -> None:
    """Write one harness scorecard. Required + optional rows; completeness uses required."""

    if not suites:
        return
    by_id: dict[str, SuiteResult] = {}
    for suite in suites:
        by_id[suite.suite_id] = suite
    ordered = [by_id[sid] for sid in ALL_SUITE_IDS if sid in by_id]
    if not ordered:
        return
    runner_name, md_name = _scorecard_names(harness_name)
    report = compose_acceptance_report(
        AgentIdentity(agent_id=harness_name, name=harness_name, version="overnight"),
        ordered,
        report_id=str(uuid.uuid4()),
        notes=notes,
        required_suites=REQUIRED_SUITE_IDS,
        optional_suites=OPTIONAL_SUITE_IDS,
    )
    write_scorecard(
        report,
        repo_root=ROOT,
        runner_name=runner_name,
        md_name=md_name,
    )


def compose_and_write_v2(suites: list[SuiteResult], notes: str, *, harness_name: str = "grok-cli") -> None:
    """Deprecated alias: optional rows land on the same harness scorecard."""

    compose_and_write(suites, notes, harness_name=harness_name)


def _resolve_wanted(suites_arg: str) -> list[str]:
    key = suites_arg.strip().lower()
    if key in {"all", "required"}:
        return list(REQUIRED_SUITE_IDS)
    if key in {"optional", "v2"}:
        return list(OPTIONAL_SUITE_IDS)
    return [SUITE_ALIASES.get(s.strip(), s.strip()) for s in suites_arg.split(",") if s.strip()]


def run_suites(
    *,
    harness_name: str = "grok-cli",
    suites: str = "all",
    dry: bool = False,
    report_only: bool = False,
    backend: str | None = None,
    smoke: bool = False,
) -> int:
    os.chdir(ROOT)
    os.environ["PYTHONUNBUFFERED"] = "1"

    if harness_name == "grok-cli":
        from finagent.harness.grok import refresh_xai_api_key

        refresh_xai_api_key(force=True)

    wanted = _resolve_wanted(suites)
    unknown = [sid for sid in wanted if sid not in BenchFactory._MAP]
    if unknown:
        print("unknown suite id(s):", ", ".join(unknown))
        print("known:", ", ".join(BenchFactory._MAP))
        print("aliases:", ", ".join(sorted(SUITE_ALIASES)))
        return 2

    if report_only:
        loaded_suites: list[SuiteResult] = []
        for sid in ALL_SUITE_IDS:
            loaded = load_suite(sid, harness_name=harness_name)
            if loaded:
                loaded_suites.append(loaded)
        if not loaded_suites:
            print("no suite_results to compose")
            return 1
        compose_and_write(
            loaded_suites,
            notes="recomposed from artifacts/suite_results (one scorecard per harness; optional rows tagged)",
            harness_name=harness_name,
        )
        label = (
            "wrote reports/GROK_CLI_SCORECARD.md"
            if harness_name == "grok-cli"
            else f"wrote {harness_name} scorecard"
        )
        print(label)
        return 0

    artifacts_dir = ROOT / "artifacts" / ("grok_cli" if harness_name == "grok-cli" else harness_name)
    harness = HarnessFactory.create(
        harness_name,
        backend=backend,
        artifacts_dir=artifacts_dir,
    )
    seated = harness.suite_ids()
    completed: list[str] = []
    blockers: list[str] = []
    results: list[SuiteResult] = []

    for sid in ALL_SUITE_IDS:
        if sid in wanted:
            continue
        loaded = load_suite(sid, harness_name=harness_name)
        if loaded:
            results.append(loaded)
            if sid in REQUIRED_SUITE_IDS:
                completed.append(f"{sid} (cached {loaded.status})")

    for sid in wanted:
        if harness_name == "grok-cli":
            from finagent.harness.grok import refresh_xai_api_key

            refresh_xai_api_key(force=False)
        write_status(
            live=f"running {sid}",
            completed=completed,
            blockers=blockers,
            next_action=f"finish {sid} then continue",
            harness_name=harness_name,
        )
        proto: ProtocolSpec = ProtocolFactory.create(sid)
        proto.extra = dict(proto.extra)
        proto.extra["execute"] = not dry
        proto.extra["harness_name"] = harness.name()
        if sid in OPTIONAL_VENV:
            proto.extra["python"] = repo_venv_python(ROOT, OPTIONAL_VENV[sid])
        else:
            proto.extra["python"] = default_eval_python()
        art_root = ROOT / "artifacts" / sid.split(".")[0]
        if smoke:
            from finagent.trial.smoke import apply_smoke_protocol

            apply_smoke_protocol(proto)
            proto.extra["execute"] = not dry
            proto.extra["python"] = proto.extra.get("python") or default_eval_python()
            proto.extra["artifacts_dir"] = str(art_root / "smoke")
        else:
            proto.extra["artifacts_dir"] = str(art_root)
        sample = proto.extra.get("smoke_sample") if smoke else ""
        print(
            f"=== {sid} execute={proto.extra['execute']} python={proto.extra['python']}"
            f"{' smoke=' + sample if smoke else ''} ===",
            flush=True,
        )
        try:
            if sid not in seated:
                result = skipped_suite(
                    sid,
                    protocol=proto,
                    notes=(
                        f"harness {harness.name()!r} suite_ids={sorted(seated) or '∅'} "
                        f"does not sit {sid}; skip (not HOLD-fill)"
                    ),
                )
            else:
                bench = BenchFactory.create(sid, repo_root=ROOT)
                if getattr(bench, "opt_in_sandbox", False):
                    from finagent.trial.config import TrialConfig
                    from finagent.trial.trial import Trial

                    cfg = TrialConfig(
                        harness=harness_name,
                        suite_id=sid,
                        sandbox_type="local-process",
                        plugins=list(getattr(bench, "default_plugins", ()) or ()),
                        protocol=proto,
                        execute=bool(proto.extra.get("execute")),
                        artifacts_dir=str(proto.extra.get("artifacts_dir") or ""),
                        python=str(proto.extra.get("python") or "") or None,
                    )
                    result = asyncio.run(Trial(cfg, repo_root=ROOT, harness=harness).run())
                else:
                    result = bench.run_official(harness, proto, sandbox=None)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            result = SuiteResult(
                suite_id=sid,
                status=SuiteStatus.ERROR.value,
                protocol=proto,
                notes=f"orchestrator caught: {exc}",
            )
            blockers.append(f"{sid}: {exc}")
        if result.protocol is not None:
            result.protocol.extra.pop("_sandbox", None)
        dump_suite(result, harness_name=harness_name)
        results = [s for s in results if s.suite_id != sid] + [result]
        completed.append(f"{sid} status={result.status}")
        if harness_name == "grok-cli":
            card_notes = (
                "Parallel scorecard for Grok CLI. Required benches drive completeness; "
                "optional benches skip if deps are missing. Per-suite pass/fail is not a veto. "
                f"backend={backend or ''} model={harness.version()}."
                + (" SMOKE: tiny official samples (same entrypoints)." if smoke else "")
            )
        else:
            card_notes = (
                f"Parallel scorecard for {harness_name}. Required benches drive completeness; "
                "optional benches skip if deps are missing. Per-suite pass/fail is not a veto."
            )
        compose_and_write(results, notes=card_notes, harness_name=harness_name)
        print(f"=== {sid} -> {result.status} ===", flush=True)
        print(f"[suite] {sid} notes={(result.notes or '')[:240]}", flush=True)

    write_status(
        live="idle (orchestrator finished requested suites)",
        completed=completed,
        blockers=blockers,
        next_action="read reports/GROK_CLI_SCORECARD.md; resume unfinished suites if any",
        harness_name=harness_name,
    )
    return 0


def cli_main(
    argv: list[str] | None = None,
    *,
    default_harness: str = "grok-cli",
    expose_harness_flag: bool = True,
) -> int:
    parser = argparse.ArgumentParser(description="Finance-agent eval (shared run_suites)")
    if expose_harness_flag:
        parser.add_argument("--harness", default=default_harness, help="registry key (default grok-cli)")
    parser.add_argument(
        "--suites",
        default="all",
        help="all|required (default completeness set), optional, or comma list of ids/aliases",
    )
    parser.add_argument("--dry", action="store_true", help="do not execute engines")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="tiny official samples (dates/universe/--limit/n_questions); same entrypoints",
    )
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--backend", default=os.environ.get("GROK_EVAL_BACKEND", "api"))
    args = parser.parse_args(argv)
    ensure_eval_python()
    harness_name = args.harness if expose_harness_flag else default_harness
    return run_suites(
        harness_name=harness_name,
        suites=args.suites,
        dry=args.dry,
        report_only=args.report_only,
        backend=args.backend,
        smoke=bool(args.smoke),
    )
