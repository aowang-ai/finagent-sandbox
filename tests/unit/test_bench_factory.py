"""Phase C: BenchFactory always wraps EnvAdapter as EnvAdapterAsBench."""

from __future__ import annotations

import unittest

from adapters.base import (
    ALL_SUITE_IDS,
    OPTIONAL_SUITE_IDS,
    REQUIRED_SUITE_IDS,
    suite_tier,
)
from adapters.finsaber import FinsaberEnvAdapter
from adapters.stockbench import StockBenchEnvAdapter
from finagent.benches.factory import BenchFactory, ProtocolFactory, SUITE_ALIASES
from finagent.benches.wrap import EnvAdapterAsBench
from finagent.trial.run_suites import _resolve_wanted


class BenchFactoryTests(unittest.TestCase):
    def test_map_keys_are_all_suite_ids(self) -> None:
        self.assertEqual(set(BenchFactory._MAP), set(ALL_SUITE_IDS))
        self.assertEqual(len(BenchFactory._MAP), 11)
        self.assertEqual(set(ProtocolFactory._MAP), set(ALL_SUITE_IDS))
        self.assertEqual(ALL_SUITE_IDS, REQUIRED_SUITE_IDS + OPTIONAL_SUITE_IDS)
        self.assertEqual(len(REQUIRED_SUITE_IDS), 5)
        self.assertEqual(len(OPTIONAL_SUITE_IDS), 6)
        self.assertTrue(set(REQUIRED_SUITE_IDS).isdisjoint(OPTIONAL_SUITE_IDS))

    def test_suite_tier_and_resolve_wanted(self) -> None:
        self.assertEqual(suite_tier("ama.multi_market_live"), "required")
        self.assertEqual(suite_tier("openpm.portfolio_pit"), "optional")
        self.assertEqual(_resolve_wanted("all"), list(REQUIRED_SUITE_IDS))
        self.assertEqual(_resolve_wanted("required"), list(REQUIRED_SUITE_IDS))
        self.assertEqual(_resolve_wanted("optional"), list(OPTIONAL_SUITE_IDS))
        self.assertEqual(_resolve_wanted("ama"), ["ama.multi_market_live"])

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
