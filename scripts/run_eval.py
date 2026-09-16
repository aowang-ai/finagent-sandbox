#!/usr/bin/env python3
"""Generic eval CLI. Default --harness grok-cli; shared run_suites loop."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sandbox.runtime.run_suites import cli_main


def main() -> int:
    return cli_main(expose_harness_flag=True, default_harness="grok-cli")


if __name__ == "__main__":
    raise SystemExit(main())
