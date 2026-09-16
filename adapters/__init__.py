"""Adapter contracts and per-bench EnvAdapter packages.

Import `adapters.base` for exam-paper types (ProtocolSpec, AgentAdapter,
EnvAdapter). Scorecard types (`SuiteResult`, `AcceptanceReport`, …) live in
`finagent.scorecard` and are also lazy-exported from `adapters.base`.

"""

from .base import (
    ALL_SUITE_IDS,
    OPTIONAL_SUITE_IDS,
    REQUIRED_SUITE_IDS,
    BenchTier,
    AgentAdapter,
    Decision,
    EnvAdapter,
    Observation,
    ProtocolSpec,
    canonical_protocol_hash,
    suite_tier,
)
from finagent.scorecard import (
    DEFAULT_KERNEL_SUITE_ID,
    SCHEMA_VERSION,
    AcceptanceReport,
    Admission,
    AdmissionDecision,
    AgentIdentity,
    Artifact,
    GateResult,
    Metric,
    Signature,
    SuiteResult,
    SuiteStatus,
    compose_acceptance_report,
    evaluate_admission,
    skipped_suite,
)

__all__ = [
    "ALL_SUITE_IDS",
    "DEFAULT_KERNEL_SUITE_ID",
    "OPTIONAL_SUITE_IDS",
    "REQUIRED_SUITE_IDS",
    "SCHEMA_VERSION",
    "BenchTier",
    "AcceptanceReport",
    "Admission",
    "AdmissionDecision",
    "AgentAdapter",
    "AgentIdentity",
    "Artifact",
    "Decision",
    "EnvAdapter",
    "GateResult",
    "Metric",
    "Observation",
    "ProtocolSpec",
    "Signature",
    "SuiteResult",
    "SuiteStatus",
    "canonical_protocol_hash",
    "compose_acceptance_report",
    "evaluate_admission",
    "skipped_suite",
    "suite_tier",
]
