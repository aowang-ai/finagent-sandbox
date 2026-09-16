#!/usr/bin/env python3
"""Optional-suite operations: progress, harvest, resume.

Replaces the campaign one-offs `scripts/v2_continue_{finsearch,vals,livetrade,harvest,progress}.py`.
Membership is OPTIONAL_SUITE_IDS.

Usage:
  python cli/optional_suite_ops.py progress
  python cli/optional_suite_ops.py harvest
  python cli/optional_suite_ops.py resume finsearch|vals|livetrade
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "src", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from adapters.base import ALL_SUITE_IDS
from adapters.finsearchcomp.ops import (
    harvest_existing_run as harvest_finsearch,
    resume_official as resume_finsearch,
)
from adapters.livetradebench.ops import (
    harvest_existing_run as harvest_livetrade,
    progress_snapshot as livetrade_progress,
    resume_official as resume_livetrade,
)
from adapters.vals_finance_agent.ops import (
    harvest_existing_run as harvest_vals,
    progress_snapshot as vals_progress,
    resume_official as resume_vals,
)
from adapters._ops.runtime import json_list_len, pid_alive

from finagent.trial.dumps import dump_suite, load_suite
from finagent.trial.run_suites import compose_and_write


RESUME = {
    "finsearch": resume_finsearch,
    "finsearchcomp": resume_finsearch,
    "vals": resume_vals,
    "vals_finance_agent": resume_vals,
    "livetrade": resume_livetrade,
    "livetradebench": resume_livetrade,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def cmd_progress() -> int:
    snap = {
        "ts": utc_now(),
        "finsearch": {
            "n_chat": json_list_len(ROOT / "artifacts" / "finsearchcomp" / "chat.json"),
            "n_eval": json_list_len(ROOT / "artifacts" / "finsearchcomp" / "eval.json"),
            "n_total": 635,
            "pid": pid_alive(ROOT / "logs" / "v2_finsearch_run.pid"),
        },
        "vals": {
            **vals_progress(ROOT),
            "n_questions": 50,
            "pid": pid_alive(ROOT / "logs" / "v2_vals_run.pid"),
        },
        "livetrade": {
            **livetrade_progress(ROOT),
            "pid": pid_alive(ROOT / "logs" / "v2_livetrade_run.pid"),
        },
    }
    line = json.dumps(snap, sort_keys=True)
    print(line, flush=True)
    log = ROOT / "logs" / "v2_continue.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    stamp = ROOT / "status" / "v2_continue_progress.json"
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(json.dumps(snap, indent=2) + "\n", encoding="utf-8")
    return 0


def cmd_harvest() -> int:
    results_dir = ROOT / "artifacts" / "suite_results"
    results_dir.mkdir(parents=True, exist_ok=True)
    harvested = [
        harvest_finsearch(ROOT),
        harvest_vals(ROOT),
        harvest_livetrade(ROOT),
    ]
    for result in harvested:
        dump_suite(result, harness_name="grok-cli")
        metrics = {m.name: m.value for m in (result.metrics or [])}
        print(
            f"[harvest {utc_now()}] {result.suite_id} status={result.status} metrics={metrics}",
            flush=True,
        )
    harvested_all: list = []
    for sid in ALL_SUITE_IDS:
        loaded = load_suite(sid, harness_name="grok-cli")
        if loaded:
            harvested_all.append(loaded)
    compose_and_write(
        harvested_all,
        notes=(
            "Parallel scorecard recomposed from artifacts/suite_results. "
            "Optional harvest rows share reports/GROK_CLI_SCORECARD.*."
        ),
        harness_name="grok-cli",
    )
    print(f"[harvest {utc_now()}] wrote reports/GROK_CLI_SCORECARD.md", flush=True)
    snap = {
        "ts": utc_now(),
        "suites": {
            s.suite_id: {
                "status": s.status,
                "metrics": {m.name: m.value for m in (s.metrics or [])},
            }
            for s in harvested
        },
    }
    stamp = results_dir / "_v2_continue_harvest.json"
    stamp.write_text(json.dumps(snap, indent=2), encoding="utf-8")
    return 0


def cmd_resume(suite: str) -> int:
    fn = RESUME.get(suite)
    if fn is None:
        print("unknown suite:", suite, file=sys.stderr)
        print("known:", ", ".join(sorted(set(RESUME))), file=sys.stderr)
        return 2
    return int(fn(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="optional-suite progress / harvest / resume")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("progress", help="one-line CONTINUE snapshot")
    sub.add_parser("harvest", help="refresh suite_results + GROK_CLI_SCORECARD")
    p_resume = sub.add_parser("resume", help="resume official remaining work")
    p_resume.add_argument("suite", help="finsearch | vals | livetrade")
    args = parser.parse_args()
    if args.cmd == "progress":
        return cmd_progress()
    if args.cmd == "harvest":
        return cmd_harvest()
    return cmd_resume(args.suite)


if __name__ == "__main__":
    raise SystemExit(main())
