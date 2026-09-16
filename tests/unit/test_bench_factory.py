"""Phase C: BenchFactory always wraps EnvAdapter as EnvAdapterAsBench."""

from __future__ import annotations

import unittest

from adapters.base import ALL_SUITE_IDS
from adapters.finsaber import FinsaberEnvAdapter
from adapters.stockbench import StockBenchEnvAdapter
from sandbox.benches.factory import BenchFactory, ProtocolFactory, SUITE_ALIASES
from sandbox.benches.wrap import EnvAdapterAsBench


class BenchFactoryTests(unittest.TestCase):
    def test_map_keys_are_all_suite_ids(self) -> None:
        self.assertEqual(set(BenchFactory._MAP), set(ALL_SUITE_IDS))
        self.assertEqual(len(BenchFactory._MAP), 11)
        self.assertEqual(set(ProtocolFactory._MAP), set(ALL_SUITE_IDS))

    def test_create_wraps_stockbench(self) -> None:
        bench = BenchFactory.create("stockbench.daily_sim")
        self.assertIsInstance(bench, EnvAdapterAsBench)
        self.assertEqual(bench.suite_id, "stockbench.daily_sim")
        self.assertTrue(hasattr(bench, "run_official"))
        self.assertIsInstance(bench.inner, StockBenchEnvAdapter)
        self.assertFalse(hasattr(StockBenchEnvAdapter, "run_official"))

    def test_create_wraps_finsaber(self) -> None:
        bench = BenchFactory.create("finsaber.long_horizon")
        self.assertEqual(bench.suite_id, "finsaber.long_horizon")
        self.assertTrue(callable(bench.run_official))
        self.assertIsInstance(bench.inner, FinsaberEnvAdapter)

    def test_unknown_suite_lists_known_ids(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            BenchFactory.create("not.a.suite")
        self.assertIn("stockbench.daily_sim", str(ctx.exception))

    def test_protocol_factory_pins_suite_id(self) -> None:
        proto = ProtocolFactory.create("ama.multi_market_live")
        self.assertEqual(proto.suite_id, "ama.multi_market_live")

    def test_aliases_resolve_short_names(self) -> None:
        self.assertEqual(SUITE_ALIASES["ama"], "ama.multi_market_live")
        self.assertEqual(SUITE_ALIASES["finsaber"], "finsaber.long_horizon")
        self.assertEqual(SUITE_ALIASES["stockbench"], "stockbench.daily_sim")


if __name__ == "__main__":
    unittest.main()
