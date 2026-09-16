#!/usr/bin/env python3
"""Generic eval CLI. Default --harness grok-cli; shared run_suites loop.

Canonical entry: `python -m finagent.cli` (console script: finagent-eval).
This file is the same entry as a repo-root script.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "src", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from finagent.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
