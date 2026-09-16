"""python -m finagent.cli — single public eval entry."""

from __future__ import annotations

from finagent.trial.run_suites import cli_main


def main() -> int:
    return cli_main(expose_harness_flag=True, default_harness="grok-cli")


if __name__ == "__main__":
    raise SystemExit(main())
