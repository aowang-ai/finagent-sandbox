"""SuiteResult dump/load with per-harness namespace.

Write only artifacts/suite_results/<harness>/{suite_id}.json.
Load namespaced first; Grok falls back to the legacy flat Sep-12 file.
Never write the flat path. Non-Grok never reads or writes grok-cli/.
"""

from __future__ import annotations

import json
from pathlib import Path

from adapters.base import ProtocolSpec
from finagent.scorecard.types import Artifact, GateResult, Metric, SuiteResult

from finagent._paths import REPO_ROOT as ROOT


def suite_results_dir(repo_root: Path | None = None) -> Path:
    return Path(repo_root or ROOT) / "artifacts" / "suite_results"


def namespaced_path(
    suite_id: str,
    harness_name: str,
    *,
    results_dir: Path | None = None,
    repo_root: Path | None = None,
) -> Path:
    parent = Path(results_dir) if results_dir is not None else suite_results_dir(repo_root)
    if parent.name == harness_name:
        return parent / f"{suite_id}.json"
    return parent / harness_name / f"{suite_id}.json"


def legacy_path(
    suite_id: str,
    *,
    results_dir: Path | None = None,
    repo_root: Path | None = None,
) -> Path:
    parent = Path(results_dir) if results_dir is not None else suite_results_dir(repo_root)
    if parent.name not in {"suite_results"} and (parent.parent / f"{suite_id}.json").is_file():
        # results_dir already namespaced; legacy lives on the parent
        return parent.parent / f"{suite_id}.json"
    return parent / f"{suite_id}.json"


def dump_suite(
    result: SuiteResult,
    results_dir: Path | None = None,
    *,
    harness_name: str = "grok-cli",
    repo_root: Path | None = None,
) -> Path:
    """Write SuiteResult under <harness>/. Never writes the legacy flat file."""

    from dataclasses import asdict

    path = namespaced_path(
        result.suite_id,
        harness_name,
        results_dir=results_dir,
        repo_root=repo_root,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if result.protocol is not None:
        result.protocol.extra.pop("_sandbox", None)
    path.write_text(json.dumps(asdict(result), default=str, indent=2), encoding="utf-8")
    return path


def read_suite_file(path: Path) -> SuiteResult | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    proto_raw = data.get("protocol") or {}
    if isinstance(proto_raw, ProtocolSpec):
        proto = proto_raw
    else:
        proto = ProtocolSpec(
            suite_id=proto_raw.get("suite_id") or data.get("suite_id"),
            date_from=proto_raw.get("date_from"),
            date_to=proto_raw.get("date_to"),
            universe=list(proto_raw.get("universe") or []),
            data_vintage=proto_raw.get("data_vintage"),
            costs=dict(proto_raw.get("costs") or {}),
            execution_timing=proto_raw.get("execution_timing"),
            extra=dict(proto_raw.get("extra") or {}),
        )
    metrics = []
    for m in data.get("metrics") or []:
        if isinstance(m, dict):
            metrics.append(
                Metric(**{k: m[k] for k in ("name", "value", "unit", "higher_is_better", "source") if k in m})
            )
    gates = []
    for g in data.get("gates") or []:
        if isinstance(g, dict):
            gates.append(GateResult(**{k: g[k] for k in g if k in GateResult.__dataclass_fields__}))
    arts = []
    for a in data.get("artifacts") or []:
        if isinstance(a, dict):
            arts.append(Artifact(**{k: a[k] for k in ("kind", "path", "media_type") if k in a}))
    return SuiteResult(
        suite_id=data["suite_id"],
        status=data["status"],
        protocol=proto,
        metrics=metrics,
        gates=gates,
        artifacts=arts,
        traces_path=data.get("traces_path"),
        notes=data.get("notes") or "",
        upstream_cli=data.get("upstream_cli"),
    )


def load_suite(
    suite_id_or_path: str | Path,
    results_dir: Path | None = None,
    *,
    harness_name: str = "grok-cli",
    repo_root: Path | None = None,
) -> SuiteResult | None:
    """Load a SuiteResult.

    Path argument: read that file only (caller-chosen).
    suite_id string: namespaced file, then (Grok only) legacy flat fallback.
    """

    if isinstance(suite_id_or_path, Path):
        return read_suite_file(suite_id_or_path)
    namespaced = namespaced_path(
        suite_id_or_path,
        harness_name,
        results_dir=results_dir,
        repo_root=repo_root,
    )
    if namespaced.is_file():
        return read_suite_file(namespaced)
    if harness_name == "grok-cli":
        legacy = legacy_path(
            suite_id_or_path,
            results_dir=results_dir,
            repo_root=repo_root,
        )
        if legacy.is_file():
            return read_suite_file(legacy)
    return None
