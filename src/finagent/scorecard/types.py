"""Scorecard dataclasses and admission helpers.

Moved from adapters.base. ProtocolSpec / hashing stay on adapters.base
(exam paper). No field or metric changes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable

import json

from adapters.base import (
    OPTIONAL_SUITE_IDS,
    REQUIRED_SUITE_IDS,
    ComparisonOp,
    ProtocolSpec,
    canonical_protocol_hash,
    sha256_hex,
)

SCHEMA_VERSION = "1.0.0"

# Parallel scorecard: no suite is a veto kernel. The field remains on
# Admission for schema compatibility; it is not a FINSABER (or any) gate.
DEFAULT_KERNEL_SUITE_ID = "parallel_scorecard"

class SuiteStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"


class AdmissionDecision(str, Enum):
    PROMOTE = "promote"
    HOLD = "hold"
    REJECT = "reject"

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
    required_suites: list[str] = field(default_factory=lambda: list(REQUIRED_SUITE_IDS))
    optional_suites: list[str] = field(default_factory=lambda: list(OPTIONAL_SUITE_IDS))
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
    optional_suites: Iterable[str] | None = None,
) -> Admission:
    """Parallel scorecard. No suite vetoes another (including FINSABER).

    Suite-level pass/fail and honesty gates stay on SuiteResult. This function
    only summarizes whether the scorecard is complete enough to read.

    promote — every required suite produced a score (status pass or fail)
    hold    — a required suite is missing or skipped
    reject  — a required suite errored (engine/data/API could not score it)
    Optional benches never HOLD or REJECT completeness.
    """

    required = list(required_suites) if required_suites is not None else list(REQUIRED_SUITE_IDS)
    optional = list(optional_suites) if optional_suites is not None else list(OPTIONAL_SUITE_IDS)
    by_id: dict[str, SuiteResult] = {s.suite_id: s for s in suites}

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
    optional_suites: Iterable[str] | None = None,
    notes: str = "",
) -> AcceptanceReport:
    admission = evaluate_admission(
        suites,
        kernel=kernel,
        required_suites=required_suites,
        optional_suites=optional_suites,
    )
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
