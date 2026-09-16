"""Unified contracts for finance-agent evaluation infra.

One AgentAdapter is the unit under test. Each upstream module is an
EnvAdapter (an "exam room"). Suites are scored in parallel: the unified
report is a scorecard / profile, not a one-gate promote. FINSABER honesty
is a suite-level metric, not a veto over AMA / StockBench / FinTool /
DeepFund. This file is stdlib-only.

This pass composes upstream CLIs rather than reimplementing them.
Bitwise paper reproduction is explicitly out of scope.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
from typing import Any, Iterable, Mapping, Protocol, runtime_checkable
import json
from datetime import datetime, timezone


SCHEMA_VERSION = "1.0.0"

# Parallel scorecard: no suite is a veto kernel. The field remains on
# Admission for schema compatibility; it is not a FINSABER (or any) gate.
DEFAULT_KERNEL_SUITE_ID = "parallel_scorecard"

# Completeness for promote today is the v1 five. v2 suites are registered
# and cloneable but optional until a full official-protocol run exists.
REQUIRED_SUITE_IDS_V1: tuple[str, ...] = (
    "ama.multi_market_live",
    "finsaber.long_horizon",
    "stockbench.daily_sim",
    "fintoolbench.tool_compliance",
    "deepfund.fund_arena",
)

PLANNED_SUITE_IDS_V2: tuple[str, ...] = (
    "investorbench.decision",
    "livetradebench.live",
    "finmcp.tool_mcp",
    "vals_finance_agent.research",
    "finsearchcomp.search",
    "openpm.portfolio_pit",
)

ALL_SUITE_IDS: tuple[str, ...] = REQUIRED_SUITE_IDS_V1 + PLANNED_SUITE_IDS_V2


class SuiteStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"


class AdmissionDecision(str, Enum):
    PROMOTE = "promote"
    HOLD = "hold"
    REJECT = "reject"


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
# Metrics, gates, artifacts, suite / acceptance reports
# ---------------------------------------------------------------------------


@dataclass
class Metric:
    name: str
    value: float | None
    unit: str | None = None
    higher_is_better: bool | None = None
    source: str | None = None


@dataclass
class GateResult:
    gate_id: str
    metric: str
    op: str
    threshold: float | int | str | bool | None
    actual: float | int | str | bool | None
    passed: bool
    required: bool = True
    rationale: str = ""


@dataclass
class Artifact:
    kind: str
    path: str
    media_type: str | None = None


@dataclass
class SuiteResult:
    suite_id: str
    status: str
    protocol: ProtocolSpec
    metrics: list[Metric] = field(default_factory=list)
    gates: list[GateResult] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    traces_path: str | None = None
    notes: str = ""
    upstream_cli: str | None = None

    @property
    def protocol_hash(self) -> str:
        return canonical_protocol_hash(self.protocol)


@dataclass
class AgentIdentity:
    agent_id: str
    name: str | None = None
    version: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Signature:
    """Detached, signable slot. This scaffold does not implement crypto."""

    role: str
    signer: str
    signed_at: str | None = None
    digest: str | None = None
    signature: str | None = None
    key_id: str | None = None


@dataclass
class Admission:
    """Top-level summary of a parallel scorecard.

    `decision` is completeness of the scorecard, not a FINSABER-kernel veto:
    promote = every required suite produced a score (pass or fail);
    hold    = a required suite is missing or skipped;
    reject  = a required suite errored (could not be scored).
    Per-suite pass/fail and honesty gates live on SuiteResult.
    """

    decision: str
    kernel: str = DEFAULT_KERNEL_SUITE_ID
    required_suites: list[str] = field(default_factory=lambda: list(REQUIRED_SUITE_IDS_V1))
    optional_suites: list[str] = field(default_factory=lambda: list(PLANNED_SUITE_IDS_V2))
    rationale: str = ""


@dataclass
class AcceptanceReport:
    schema_version: str
    report_id: str
    generated_at: str
    agent: AgentIdentity
    protocol_hash: str
    suites: list[SuiteResult]
    admission: Admission
    artifacts: list[Artifact] = field(default_factory=list)
    signatures: list[Signature] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def compare(op: str, actual: Any, threshold: Any) -> bool:
    if actual is None:
        return False
    if op == ComparisonOp.GTE.value:
        return actual >= threshold
    if op == ComparisonOp.LTE.value:
        return actual <= threshold
    if op == ComparisonOp.GT.value:
        return actual > threshold
    if op == ComparisonOp.LT.value:
        return actual < threshold
    if op == ComparisonOp.EQ.value:
        return actual == threshold
    if op == ComparisonOp.NEQ.value:
        return actual != threshold
    raise ValueError(f"unknown comparison op: {op}")


def evaluate_admission(
    suites: Iterable[SuiteResult],
    *,
    kernel: str = DEFAULT_KERNEL_SUITE_ID,
    required_suites: Iterable[str] | None = None,
) -> Admission:
    """Parallel scorecard. No suite vetoes another (including FINSABER).

    Suite-level pass/fail and honesty gates stay on SuiteResult. This function
    only summarizes whether the scorecard is complete enough to read.

    promote — every required suite produced a score (status pass or fail)
    hold    — a required suite is missing or skipped
    reject  — a required suite errored (engine/data/API could not score it)
    """

    required = list(required_suites) if required_suites is not None else list(REQUIRED_SUITE_IDS_V1)
    by_id: dict[str, SuiteResult] = {s.suite_id: s for s in suites}
    optional = [sid for sid in by_id if sid not in required]

    missing_or_skip: list[str] = []
    errored: list[str] = []
    scored: list[str] = []
    for sid in required:
        result = by_id.get(sid)
        if result is None or result.status == SuiteStatus.SKIP.value:
            missing_or_skip.append(sid)
            continue
        if result.status == SuiteStatus.ERROR.value:
            errored.append(sid)
            continue
        scored.append(sid)

    if errored:
        decision = AdmissionDecision.REJECT.value
        rationale = (
            "scorecard incomplete: required suite(s) errored: " + ", ".join(errored)
        )
    elif missing_or_skip:
        decision = AdmissionDecision.HOLD.value
        rationale = (
            "scorecard incomplete: required suite(s) not yet run: "
            + ", ".join(missing_or_skip)
        )
    else:
        decision = AdmissionDecision.PROMOTE.value
        rationale = (
            "parallel scorecard complete: all required suites produced a score "
            f"({', '.join(scored) or 'none'}). Per-suite pass/fail is not a veto."
        )

    return Admission(
        decision=decision,
        kernel=kernel or DEFAULT_KERNEL_SUITE_ID,
        required_suites=required,
        optional_suites=optional,
        rationale=rationale,
    )


def compose_acceptance_report(
    agent: AgentIdentity,
    suites: list[SuiteResult],
    *,
    report_id: str,
    kernel: str = DEFAULT_KERNEL_SUITE_ID,
    required_suites: Iterable[str] | None = None,
    notes: str = "",
) -> AcceptanceReport:
    admission = evaluate_admission(suites, kernel=kernel, required_suites=required_suites)
    protocol_hash = sha256_hex([canonical_protocol_hash(s.protocol) for s in suites])
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return AcceptanceReport(
        schema_version=SCHEMA_VERSION,
        report_id=report_id,
        generated_at=generated_at,
        agent=agent,
        protocol_hash=protocol_hash,
        suites=suites,
        admission=admission,
        notes=notes,
    )


def skipped_suite(
    suite_id: str,
    *,
    notes: str,
    upstream_cli: str | None = None,
    protocol: ProtocolSpec | None = None,
) -> SuiteResult:
    """Helper for unwired stubs: honest skip, never a fake pass."""

    return SuiteResult(
        suite_id=suite_id,
        status=SuiteStatus.SKIP.value,
        protocol=protocol or ProtocolSpec(suite_id=suite_id),
        notes=notes,
        upstream_cli=upstream_cli,
    )


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

    Harbor-style benches wrap this as sandbox.benches.wrap.EnvAdapterAsBench
    (BenchAdapter). Do not rename EnvAdapter.
    """

    suite_id: str
    module_dir: str

    def describe(self) -> Mapping[str, Any]:
        """Human-readable wrap plan: CLI, artifacts, metrics, pitfalls."""
        ...

    def run(self, agent: AgentAdapter, protocol: ProtocolSpec) -> SuiteResult:
        ...
