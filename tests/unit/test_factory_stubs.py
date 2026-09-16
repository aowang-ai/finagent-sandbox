"""Phase A: three Harbor factory stubs expose the expected _MAP keys."""

from __future__ import annotations

import unittest

from adapters.base import ALL_SUITE_IDS
from sandbox.benches.factory import BenchFactory
from sandbox.harness.factory import HarnessFactory
from sandbox.plugins.factory import PluginFactory


class FactoryStubMapTests(unittest.TestCase):
    def test_harness_map_is_grok_cli_only(self) -> None:
        self.assertEqual(list(HarnessFactory._MAP), ["grok-cli"])
        self.assertEqual(
            HarnessFactory._MAP["grok-cli"],
            "sandbox.harness.grok_cli:GrokCliHarness",
        )

    def test_bench_map_keys_match_all_suite_ids(self) -> None:
        self.assertEqual(set(BenchFactory._MAP), set(ALL_SUITE_IDS))
        self.assertEqual(len(BenchFactory._MAP), 11)

    def test_plugin_map_registers_mcp(self) -> None:
        self.assertEqual(list(PluginFactory._MAP), ["mcp"])
        self.assertEqual(PluginFactory._MAP["mcp"], "sandbox.plugins.mcp:McpPlugin")

    def test_unknown_harness_lists_known_keys(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            HarnessFactory.create("claude-code")
        self.assertIn("grok-cli", str(ctx.exception))

    def test_known_harness_creates_grok_cli(self) -> None:
        harness = HarnessFactory.create("grok-cli")
        self.assertEqual(harness.name(), "grok-cli")

    def test_known_bench_wraps_env_adapter(self) -> None:
        bench = BenchFactory.create("stockbench.daily_sim")
        self.assertEqual(bench.suite_id, "stockbench.daily_sim")
        self.assertTrue(hasattr(bench, "run_official"))

    def test_unknown_bench_lists_known_keys(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            BenchFactory.create("not.a.suite")
        self.assertIn("stockbench.daily_sim", str(ctx.exception))

    def test_plugin_create_mcp(self) -> None:
        plugin = PluginFactory.create("mcp")
        self.assertEqual(plugin.name(), "mcp")

    def test_unknown_plugin_lists_mcp(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            PluginFactory.create("yahoo")
        self.assertIn("mcp", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
