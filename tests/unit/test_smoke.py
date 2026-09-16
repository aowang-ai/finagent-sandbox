"""Smoke shrinks official protocol knobs; does not invent a second protocol."""

from __future__ import annotations
import unittest

from adapters.base import ALL_SUITE_IDS
from finagent.benches.factory import ProtocolFactory
from finagent.trial.smoke import apply_smoke_protocol, is_smoke


class SmokeProtocolTests(unittest.TestCase):
    def test_smoke_flag_and_samples_for_all_11(self) -> None:
        for sid in ALL_SUITE_IDS:
            proto = ProtocolFactory.create(sid)
            apply_smoke_protocol(proto)
            self.assertTrue(is_smoke(proto), sid)
            self.assertTrue(proto.extra.get("smoke_sample"), sid)

    def test_ama_one_ticker_one_day(self) -> None:
        proto = ProtocolFactory.create("ama.multi_market_live")
        apply_smoke_protocol(proto)
        self.assertEqual(proto.universe, ["AAPL"])
        self.assertEqual(proto.date_from, proto.date_to)

    def test_finsearch_uses_official_limit(self) -> None:
        proto = ProtocolFactory.create("finsearchcomp.search")
        apply_smoke_protocol(proto)
        self.assertEqual(proto.extra.get("limit"), 2)

    def test_fintool_n_questions(self) -> None:
        proto = ProtocolFactory.create("fintoolbench.tool_compliance")
        apply_smoke_protocol(proto)
        self.assertEqual(proto.extra.get("n_questions"), 2)

    def test_full_protocol_factory_unchanged(self) -> None:
        proto = ProtocolFactory.create("ama.multi_market_live")
        self.assertGreater(len(proto.universe), 1)
        self.assertFalse(is_smoke(proto))


if __name__ == "__main__":
    unittest.main()
