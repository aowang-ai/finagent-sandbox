#!/usr/bin/env python3
"""Run Grok CLI through official protocols and write the scorecard.

Thin alias into sandbox.runtime.run_suites with harness=grok-cli.

Usage:
  python scripts/run_grok_cli_eval.py                 # v1 five required suites, execute
  python scripts/run_grok_cli_eval.py --suites ama
  python scripts/run_grok_cli_eval.py --suites investorbench,finmcp
  python scripts/run_grok_cli_eval.py --suites v2      # planned v2 (does not rewrite v1 scorecard)
  python scripts/run_grok_cli_eval.py --dry           # skip execute (doctor-like)
  python scripts/run_grok_cli_eval.py --report-only   # recompose v1 from suite_results/

`--suites all` is the v1 five so completeness / GROK_CLI_SCORECARD stay stable.
v2 aliases work; running only v2 does not rewrite reports/GROK_CLI_SCORECARD.*.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sandbox.runtime.dumps import dump_suite, load_suite  # noqa: F401
from sandbox.runtime.run_suites import compose_and_write, compose_and_write_v2, cli_main  # noqa: F401


def main() -> int:
    return cli_main(expose_harness_flag=False, default_harness="grok-cli")


if __name__ == "__main__":
    raise SystemExit(main())
