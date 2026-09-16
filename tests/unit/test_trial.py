"""Phase D: thin Trial extras, seating skip, AMA dry skip (not HOLD-fill)."""

from __future__ import annotations

import asyncio
import unittest
from pathlib import Path

from adapters.base import AgentAdapter, Decision, Observation
from finagent.harness.base import BaseHarness
from finagent.trial.config import TrialConfig
from finagent.trial.trial import Trial

ROOT = Path(__file__).resolve().parents[2]


class SitNoneHarness(BaseHarness):
    """Harness that sits no benches. decide() must not run."""

    @staticmethod
    def name() -> str:
        return "sit-none"

    def version(self) -> str | None:
        return None

    def suite_ids(self) -> set[str]:
        return set()

    def as_agent_adapter(self) -> AgentAdapter:
        raise AssertionError("decide() must not be called for unseated benches")


class BoomAdapter:
    agent_id = "boom"

    def capabilities(self) -> set[str]:
        return set()

    def decide(self, observation: Observation) -> Decision:
        raise AssertionError(f"decide() must not be called; obs={observation}")


class SitNoneWithBoomAdapter(SitNoneHarness):
    def as_agent_adapter(self) -> AgentAdapter:
        return BoomAdapter()  # type: ignore[return-value]


class TrialTests(unittest.TestCase):
    def test_ama_dry_execute_false_skips(self) -> None:
        cfg = TrialConfig(
            harness="grok-cli",
            suite_id="ama.multi_market_live",
            execute=False,
            artifacts_dir=str(ROOT / "artifacts" / "ama"),
        )
        result = asyncio.run(Trial(cfg, repo_root=ROOT).run())
        self.assertEqual(result.suite_id, "ama.multi_market_live")
        self.assertEqual(result.status, "skip")
        notes = (result.notes or "").lower()
        self.assertTrue("execute" in notes or "wired" in notes, result.notes)

    def test_unseated_harness_skips_without_decide(self) -> None:
        cfg = TrialConfig(
            harness="tests.unit.test_trial:SitNoneWithBoomAdapter",
            suite_id="ama.multi_market_live",
            execute=True,
        )
        result = asyncio.run(Trial(cfg, repo_root=ROOT).run())
        self.assertEqual(result.status, "skip")
        self.assertIn("does not sit", result.notes or "")
        self.assertIn("sit-none", result.notes or "")


if __name__ == "__main__":
    unittest.main()
