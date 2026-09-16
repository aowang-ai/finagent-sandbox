#!/usr/bin/env python3
"""Thin shim — canonical entry is `python -m finagent.cli` or `cli/run_eval.py`."""

from __future__ import annotations

import runpy
from pathlib import Path

raise SystemExit(runpy.run_path(str(Path(__file__).resolve().parents[1] / "cli" / "run_eval.py"), run_name="__main__") or 0)
