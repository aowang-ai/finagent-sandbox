"""Adapter contracts and per-module CLI wrappers.

Import `adapters.base` for the shared types. Module stubs under this package
are intentionally not wired to live LLM / data runs.
"""

from .base import (
    ALL_SUITE_IDS,
    DEFAULT_KERNEL_SUITE_ID,
    PLANNED_SUITE_IDS_V2,
    REQUIRED_SUITE_IDS_V1,
    SCHEMA_VERSION,
    AcceptanceReport,
    Admission,
    AdmissionDecision,
    AgentAdapter,
    AgentIdentity,
    Artifact,
    Decision,
    EnvAdapter,
    GateResult,
    Metric,
    Observation,
    ProtocolSpec,
    Signature,
    SuiteResult,
    SuiteStatus,
    canonical_protocol_hash,
    compose_acceptance_report,
    evaluate_admission,
    skipped_suite,
)

__all__ = [
    "ALL_SUITE_IDS",
    "DEFAULT_KERNEL_SUITE_ID",
    "PLANNED_SUITE_IDS_V2",
    "REQUIRED_SUITE_IDS_V1",
    "SCHEMA_VERSION",
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
]
