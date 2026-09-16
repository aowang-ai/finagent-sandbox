"""Unified contracts for finance-agent evaluation infra.

One AgentAdapter is the unit under test. Each upstream module is an
EnvAdapter (an "exam room"). Suites are scored in parallel: the unified
report is a scorecard / profile, not a one-gate promote. FINSABER honesty
is a suite-level metric, not a veto over AMA / StockBench / FinTool /
DeepFund. This file is stdlib-only.

Exam-paper types live here. SuiteResult / AcceptanceReport live in
`finagent.scorecard` and are re-exported lazily from this module so
existing `from adapters.base import SuiteResult` still works.

This pass composes upstream CLIs rather than reimplementing them.
Bitwise paper reproduction is explicitly out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from typing import TYPE_CHECKING, Any, Mapping, Protocol, runtime_checkable
import json

if TYPE_CHECKING:
    from finagent.scorecard.types import SuiteResult

# All 11 ids are BenchFactory equals. Completeness / --suites all uses the
# required five. Optional six skip when deps are missing; they do not HOLD
# admission.
REQUIRED_SUITE_IDS: tuple[str, ...] = (
    "ama.multi_market_live",
    "finsaber.long_horizon",
    "stockbench.daily_sim",
    "fintoolbench.tool_compliance",
    "deepfund.fund_arena",
)

OPTIONAL_SUITE_IDS: tuple[str, ...] = (
    "investorbench.decision",
    "livetradebench.live",
    "finmcp.tool_mcp",
    "vals_finance_agent.research",
    "finsearchcomp.search",
    "openpm.portfolio_pit",
)

ALL_SUITE_IDS: tuple[str, ...] = REQUIRED_SUITE_IDS + OPTIONAL_SUITE_IDS


class BenchTier(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"


def suite_tier(suite_id: str) -> str:
    """required | optional for a registered bench. Unknown ids raise."""

    if suite_id in REQUIRED_SUITE_IDS:
        return BenchTier.REQUIRED.value
    if suite_id in OPTIONAL_SUITE_IDS:
        return BenchTier.OPTIONAL.value
    raise ValueError(f"unknown suite_id {suite_id!r}")

class ComparisonOp(str, Enum):
    GTE = "gte"
    LTE = "lte"
    GT = "gt"
    LT = "lt"
    EQ = "eq"
    NEQ = "neq"


# ---------------------------------------------------------------------------
# Protocol / observation / decision
# ---------------------------------------------------------------------------


@dataclass
class ProtocolSpec:
    """Versioned evaluation protocol. Hash this; do not hash the agent's answers.

    A protocol is the *exam paper*: data vintage, universe, dates, costs,
    execution timing. Changing any of these is a different exam.
    """

    suite_id: str
    date_from: str | None = None
    date_to: str | None = None
    universe: list[str] = field(default_factory=list)
    data_vintage: str | None = None
    costs: dict[str, Any] = field(default_factory=dict)
    execution_timing: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "universe": list(self.universe),
            "data_vintage": self.data_vintage,
            "costs": self.costs,
            "execution_timing": self.execution_timing,
            "extra": self.extra,
        }


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(payload: Any) -> str:
    blob = canonical_json(payload).encode("utf-8")
    return "sha256:" + sha256(blob).hexdigest()


def canonical_protocol_hash(protocol: ProtocolSpec) -> str:
    return sha256_hex(protocol.canonical_dict())


@dataclass
class Observation:
    """Normalized view of what an agent may see at a decision point.

    EnvAdapters map upstream payloads into this shape. Fields not used by a
    given suite stay empty. `raw` preserves the upstream document.
    """

    as_of: str
    symbols: list[str] = field(default_factory=list)
    prices: dict[str, Any] = field(default_factory=dict)
    news: dict[str, Any] = field(default_factory=dict)
    filings: dict[str, Any] = field(default_factory=dict)
    portfolio: dict[str, Any] = field(default_factory=dict)
    tools: list[dict[str, Any]] = field(default_factory=list)
    query: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Decision:
    """Normalized agent output. EnvAdapters translate this back to CLI/HTTP."""

    action: str
    symbols: list[str] = field(default_factory=list)
    reasoning: str = ""
    allocations: dict[str, float] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------

# Adapter protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class AgentAdapter(Protocol):
    """The unit under test. One implementation should plug into every suite.

    `decide` is the lowest common denominator (AMA-style BUY/SELL/HOLD, plus
    optional allocations and tool_calls). Suites that need a richer native
    object (FINSABER strategy class, DeepFund analyst graph) should wrap this
    adapter at the EnvAdapter boundary rather than forking the agent.
    """

    agent_id: str

    def capabilities(self) -> set[str]:
        """Declared suite ids this agent is willing to sit. Empty means all."""
        ...

    def decide(self, observation: Observation) -> Decision:
        ...


@runtime_checkable
class EnvAdapter(Protocol):
    """Wraps one upstream module. Prefer subprocess of the official CLI.

    Harbor-style benches wrap this as finagent.benches.wrap.EnvAdapterAsBench
    (BenchAdapter). Do not rename EnvAdapter.
    """

    suite_id: str
    module_dir: str

    def describe(self) -> Mapping[str, Any]:
        """Human-readable wrap plan: CLI, artifacts, metrics, pitfalls."""
        ...

    def run(self, agent: AgentAdapter, protocol: ProtocolSpec) -> SuiteResult:
        ...

# ---------------------------------------------------------------------------
# Lazy re-export of scorecard types (canonical home: finagent.scorecard)
# ---------------------------------------------------------------------------

_SCORECARD_EXPORTS = frozenset({
    "SCHEMA_VERSION",
    "DEFAULT_KERNEL_SUITE_ID",
    "SuiteStatus",
    "AdmissionDecision",
    "Metric",
    "GateResult",
    "Artifact",
    "SuiteResult",
    "AgentIdentity",
    "Signature",
    "Admission",
    "AcceptanceReport",
    "evaluate_admission",
    "compose_acceptance_report",
    "skipped_suite",
    "compare",
})


def __getattr__(name: str):
    if name in _SCORECARD_EXPORTS:
        from finagent.scorecard import types as _sc

        return getattr(_sc, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(list(globals()) + list(_SCORECARD_EXPORTS))
