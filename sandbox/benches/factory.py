"""BenchFactory — Harbor adapters analogue.

Always returns EnvAdapterAsBench wrapping the registered *EnvAdapter.
ProtocolFactory + SUITE_ALIASES live here so the Grok script is not
the exam-paper registry.
"""

from __future__ import annotations

import importlib

from adapters.base import ProtocolSpec
from sandbox.benches.wrap import EnvAdapterAsBench, FinMcpEnvAdapterAsBench


def _load_symbol(path: str):
    module_name, sep, attr = path.partition(":")
    if not sep or not attr:
        raise ValueError(f"import path must be 'module:attr', got {path!r}")
    module = importlib.import_module(module_name)
    return getattr(module, attr)


SUITE_ALIASES: dict[str, str] = {
    "ama": "ama.multi_market_live",
    "finsaber": "finsaber.long_horizon",
    "stockbench": "stockbench.daily_sim",
    "fintool": "fintoolbench.tool_compliance",
    "fintoolbench": "fintoolbench.tool_compliance",
    "deepfund": "deepfund.fund_arena",
    "investorbench": "investorbench.decision",
    "livetrade": "livetradebench.live",
    "livetradebench": "livetradebench.live",
    "finmcp": "finmcp.tool_mcp",
    "vals": "vals_finance_agent.research",
    "vals_finance_agent": "vals_finance_agent.research",
    "finance_agent": "vals_finance_agent.research",
    "finsearch": "finsearchcomp.search",
    "finsearchcomp": "finsearchcomp.search",
    "openpm": "openpm.portfolio_pit",
}


class BenchFactory:
    _MAP: dict[str, str] = {
        "ama.multi_market_live": "adapters.ama:AmaEnvAdapter",
        "finsaber.long_horizon": "adapters.finsaber:FinsaberEnvAdapter",
        "stockbench.daily_sim": "adapters.stockbench:StockBenchEnvAdapter",
        "fintoolbench.tool_compliance": "adapters.fintoolbench:FinToolBenchEnvAdapter",
        "deepfund.fund_arena": "adapters.deepfund:DeepFundEnvAdapter",
        "investorbench.decision": "adapters.investorbench:InvestorBenchEnvAdapter",
        "livetradebench.live": "adapters.livetradebench:LiveTradeBenchEnvAdapter",
        "finmcp.tool_mcp": "adapters.finmcp:FinMcpEnvAdapter",
        "vals_finance_agent.research": "adapters.vals_finance_agent:ValsFinanceAgentEnvAdapter",
        "finsearchcomp.search": "adapters.finsearchcomp:FinSearchCompEnvAdapter",
        "openpm.portfolio_pit": "adapters.openpm:OpenPmEnvAdapter",
    }

    @classmethod
    def create(cls, name: str, **kwargs: object) -> EnvAdapterAsBench:
        if name not in cls._MAP:
            raise ValueError(f"unknown bench {name!r}; known: {sorted(cls._MAP)}")
        klass = _load_symbol(cls._MAP[name])
        repo_root = kwargs.get("repo_root", ".")
        inner = klass(repo_root)
        wrap = FinMcpEnvAdapterAsBench if name == "finmcp.tool_mcp" else EnvAdapterAsBench
        return wrap(inner)


class ProtocolFactory:
    _MAP: dict[str, str] = {
        "ama.multi_market_live": "runners.protocols:ama_protocol",
        "finsaber.long_horizon": "runners.protocols:finsaber_protocol",
        "stockbench.daily_sim": "runners.protocols:stockbench_protocol",
        "fintoolbench.tool_compliance": "runners.protocols:fintool_protocol",
        "deepfund.fund_arena": "runners.protocols:deepfund_protocol",
        "investorbench.decision": "runners.protocols:investorbench_protocol",
        "livetradebench.live": "runners.protocols:livetradebench_protocol",
        "finmcp.tool_mcp": "runners.protocols:finmcp_protocol",
        "vals_finance_agent.research": "runners.protocols:vals_finance_agent_protocol",
        "finsearchcomp.search": "runners.protocols:finsearchcomp_protocol",
        "openpm.portfolio_pit": "runners.protocols:openpm_protocol",
    }

    @classmethod
    def create(cls, suite_id: str) -> ProtocolSpec:
        if suite_id not in cls._MAP:
            raise ValueError(f"unknown protocol {suite_id!r}; known: {sorted(cls._MAP)}")
        fn = _load_symbol(cls._MAP[suite_id])
        return fn()
