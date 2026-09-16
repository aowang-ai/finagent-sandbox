#!/usr/bin/env python3
"""Thin shim — use `cli/run_grok_cli_eval.py` or `python -m finagent.cli`."""

from __future__ import annotations

import runpy
from pathlib import Path

raise SystemExit(
    runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "cli" / "run_grok_cli_eval.py"),
        run_name="__main__",
    )
    or 0
)
