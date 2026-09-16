"""Parallel scorecard types + writer.

Canonical import path for SuiteResult / AcceptanceReport / write_scorecard.
Types are defined in finagent.scorecard.types (moved from adapters.base);
the writer is finagent.scorecard.write (moved from runners.scorecard).
"""

from finagent.scorecard.types import (
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
from finagent.scorecard.write import (
    SUITE_METRIC_PREFER,
    _metric_summary,
    render_markdown,
    write_scorecard,
)

__all__ = [
    "DEFAULT_KERNEL_SUITE_ID",
    "SCHEMA_VERSION",
    "SUITE_METRIC_PREFER",
    "AcceptanceReport",
    "Admission",
    "AdmissionDecision",
    "AgentIdentity",
    "Artifact",
    "GateResult",
    "Metric",
    "Signature",
    "SuiteResult",
    "SuiteStatus",
    "_metric_summary",
    "compose_acceptance_report",
    "evaluate_admission",
    "render_markdown",
    "skipped_suite",
    "write_scorecard",
]
