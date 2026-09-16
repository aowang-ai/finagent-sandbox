#!/usr/bin/env python3
"""Thin alias: run_eval --harness grok-cli (no --harness flag exposed).

Usage:
  python cli/run_grok_cli_eval.py
  python cli/run_grok_cli_eval.py --suites ama
  python cli/run_grok_cli_eval.py --dry
  python cli/run_grok_cli_eval.py --report-only
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "src", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from finagent.trial.run_suites import cli_main


def main() -> int:
    return cli_main(expose_harness_flag=False, default_harness="grok-cli")


if __name__ == "__main__":
    raise SystemExit(main())
