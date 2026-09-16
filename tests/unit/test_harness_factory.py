"""Phase B: HarnessFactory creates GrokCliHarness; dumps are namespaced."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from adapters.base import ALL_SUITE_IDS, skipped_suite
from finagent.harness.factory import HarnessFactory
from finagent.trial.dumps import dump_suite, legacy_path, load_suite, namespaced_path


class HarnessFactoryTests(unittest.TestCase):
    def test_create_grok_cli(self) -> None:
        harness = HarnessFactory.create("grok-cli")
        self.assertEqual(harness.name(), "grok-cli")
        self.assertEqual(harness.suite_ids(), set(ALL_SUITE_IDS))
        self.assertTrue(harness.features().decide_lcd)
        adapter = harness.as_agent_adapter()
        self.assertEqual(adapter.agent_id, "grok-cli")

    def test_unknown_harness_lists_grok_cli_only(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            HarnessFactory.create("claude-code")
        self.assertIn("grok-cli", str(ctx.exception))
        self.assertNotIn("claude-code", HarnessFactory._MAP)
        self.assertEqual(list(HarnessFactory._MAP), ["grok-cli"])

    def test_map_is_grok_cli_only(self) -> None:
        self.assertEqual(list(HarnessFactory._MAP), ["grok-cli"])
        self.assertEqual(
            HarnessFactory._MAP["grok-cli"],
            "finagent.harness.grok_cli:GrokCliHarness",
        )


class DumpNamespaceTests(unittest.TestCase):
    def test_dump_writes_namespaced_never_flat(self) -> None:
        result = skipped_suite("ama.multi_market_live", notes="unit-dump")
        with tempfile.TemporaryDirectory() as tmp:
            results_dir = Path(tmp) / "suite_results"
            path = dump_suite(result, results_dir, harness_name="grok-cli")
            self.assertEqual(path, results_dir / "grok-cli" / "ama.multi_market_live.json")
            self.assertTrue(path.is_file())
            self.assertFalse((results_dir / "ama.multi_market_live.json").exists())

    def test_load_prefers_namespaced_then_legacy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            results_dir = Path(tmp) / "suite_results"
            results_dir.mkdir()
            legacy = results_dir / "ama.multi_market_live.json"
            legacy.write_text(
                '{"suite_id": "ama.multi_market_live", "status": "pass", "protocol": {}, "notes": "legacy"}',
                encoding="utf-8",
            )
            loaded = load_suite("ama.multi_market_live", results_dir, harness_name="grok-cli")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.status, "pass")
            self.assertEqual(loaded.notes, "legacy")

            namespaced = skipped_suite("ama.multi_market_live", notes="namespaced")
            dump_suite(namespaced, results_dir, harness_name="grok-cli")
            loaded2 = load_suite("ama.multi_market_live", results_dir, harness_name="grok-cli")
            self.assertIsNotNone(loaded2)
            assert loaded2 is not None
            self.assertEqual(loaded2.notes, "namespaced")
            # legacy file still present and untouched
            self.assertIn("legacy", legacy.read_text(encoding="utf-8"))

    def test_non_grok_does_not_fallback_to_legacy_or_grok_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            results_dir = Path(tmp) / "suite_results"
            results_dir.mkdir()
            (results_dir / "ama.multi_market_live.json").write_text(
                '{"suite_id": "ama.multi_market_live", "status": "pass", "protocol": {}}',
                encoding="utf-8",
            )
            grok_dir = results_dir / "grok-cli"
            grok_dir.mkdir()
            (grok_dir / "ama.multi_market_live.json").write_text(
                '{"suite_id": "ama.multi_market_live", "status": "pass", "protocol": {}, "notes": "grok"}',
                encoding="utf-8",
            )
            loaded = load_suite("ama.multi_market_live", results_dir, harness_name="other")
            self.assertIsNone(loaded)

    def test_path_helpers(self) -> None:
        self.assertTrue(str(namespaced_path("ama.multi_market_live", "grok-cli")).endswith(
            "suite_results/grok-cli/ama.multi_market_live.json"
        ))
        self.assertTrue(str(legacy_path("ama.multi_market_live")).endswith(
            "suite_results/ama.multi_market_live.json"
        ))


if __name__ == "__main__":
    unittest.main()
