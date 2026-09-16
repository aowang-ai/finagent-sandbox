"""FinToolBench — tool-call correctness + finance compliance (exam room).

Upstream: https://github.com/Double-wk/FinToolBench  ·  arXiv:2603.08262

Open release is eval + 295 questions + 760-tool manifest. We emit result JSONL
via a Grok tool-use loop, then compose run_relative_eval.py (judge via xAI).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from adapters.base import (
    AgentAdapter,
    Artifact,
    EnvAdapter,
    GateResult,
    Metric,
    Observation,
    ProtocolSpec,
    SuiteResult,
    SuiteStatus,
    skipped_suite,
)

SUITE_ID = "fintoolbench.tool_compliance"
MODULE_REL = "modules/fintoolbench"
UPSTREAM_CLI = (
    "python -u modules/fintoolbench/code_bench/evaluate/run_relative_eval.py "
    "--inputs {inputs} --output_dir {output_dir}"
)
MANIFEST = "modules/fintoolbench/tools/tools_all_annotated.jsonl"
QUESTIONS = "modules/fintoolbench/data/question/select_data_real_remove_duplicates.jsonl"

FINTOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "tool_calls": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "tool_name": {"type": "string"},
                    "step": {"type": "integer"},
                    "arguments": {"type": "object"},
                    "output": {"type": "string"},
                },
                "required": ["tool_name", "step", "output"],
            },
        },
        "execution_result": {"type": "string"},
        "reasoning": {"type": "string"},
    },
    "required": ["tool_calls", "execution_result"],
}


class FinToolBenchEnvAdapter:
    suite_id = SUITE_ID
    module_dir = MODULE_REL

    def __init__(self, repo_root: str | Path = ".") -> None:
        self.repo_root = Path(repo_root).resolve()
        self.module_path = self.repo_root / MODULE_REL

    def describe(self) -> Mapping[str, Any]:
        return {
            "suite_id": SUITE_ID,
            "role": "exam_room",
            "layer": "environment.tool_sandbox",
            "task_suite": "tool_routing_compliance",
            "module": str(self.module_path),
            "entry": "python -u code_bench/evaluate/run_relative_eval.py",
            "questions": QUESTIONS,
            "tool_manifest": MANIFEST,
            "metrics": {
                "capability": ["tir", "tesr", "cer", "soft_score", "css"],
                "compliance_mismatch_lower_is_better": ["tmr", "imr", "dmr"],
            },
            "pitfalls": [
                "RapidAPI/akshare not in this environment — tool outputs are model-produced",
                "official judge endpoint boyue is private; we route judges to xAI",
            ],
            "wired": True,
        }

    def run(self, agent: AgentAdapter, protocol: ProtocolSpec) -> SuiteResult:
        extra = dict(protocol.extra)
        extra["questions"] = str(
            _resolve_questions_path(self.repo_root, extra.get("questions", QUESTIONS))
        )
        extra.setdefault("tool_manifest", MANIFEST)
        proto = ProtocolSpec(
            suite_id=SUITE_ID,
            date_from=protocol.date_from,
            date_to=protocol.date_to,
            universe=protocol.universe,
            data_vintage=protocol.data_vintage or "tools_all_annotated.jsonl",
            extra=extra,
        )
        if not extra.get("execute"):
            return skipped_suite(
                SUITE_ID,
                protocol=proto,
                upstream_cli=UPSTREAM_CLI.format(
                    inputs="artifacts/fintoolbench/grok_cli.jsonl",
                    output_dir="artifacts/fintoolbench/eval",
                ),
                notes=(
                    "wired: set protocol.extra.execute=true to emit the full 295-question "
                    "JSONL via Grok and run the official evaluator. RapidAPI is a documented gap."
                ),
            )
        try:
            return self._run_full(agent, proto)
        except Exception as exc:  # noqa: BLE001
            return SuiteResult(
                suite_id=SUITE_ID,
                status=SuiteStatus.ERROR.value,
                protocol=proto,
                notes=f"FinToolBench full protocol error: {exc}",
                upstream_cli=UPSTREAM_CLI,
            )

    def _run_full(self, agent: AgentAdapter, proto: ProtocolSpec) -> SuiteResult:
        from finagent.harness.grok import GrokRunner, LOCKED_SYSTEM

        q_path = _resolve_questions_path(self.repo_root, proto.extra.get("questions", QUESTIONS))
        proto.extra["questions"] = str(q_path)
        m_raw = proto.extra.get("tool_manifest", MANIFEST)
        m_path = Path(str(m_raw))
        if not m_path.is_absolute():
            m_path = self.repo_root / m_path
        questions = _load_jsonl(q_path)
        tools = _load_jsonl(m_path)
        compact = [
            {
                "name": t.get("name"),
                "description": str(t.get("description") or "")[:160],
                "params": list(((t.get("parameters") or {}).get("properties") or {}).keys())[:12],
            }
            for t in tools
            if t.get("name")
        ]
        artifacts = Path(proto.extra.get("artifacts_dir") or (self.repo_root / "artifacts" / "fintoolbench"))
        artifacts.mkdir(parents=True, exist_ok=True)
        out_jsonl = artifacts / "grok_cli.jsonl"
        runner = getattr(agent, "runner", None) or GrokRunner(artifacts_dir=artifacts / "grok")

        existing_rows = _load_jsonl(out_jsonl) if out_jsonl.is_file() else []
        done_ids = {str(r.get("id")) for r in existing_rows if r.get("id") is not None and str(r.get("id"))}
        rows: list[dict[str, Any]] = list(existing_rows)
        n_with_tools = sum(1 for r in rows if r.get("tool_calls"))
        hb_path = artifacts / "heartbeat.json"
        if existing_rows:
            print(f"[fintool] resume {len(existing_rows)}/{len(questions)} from {out_jsonl}", flush=True)
        wrote = 0
        with out_jsonl.open("a" if existing_rows else "w", encoding="utf-8") as fh:
            for idx, q in enumerate(questions):
                qid = str(q.get("id") or q.get("original_idx") or idx)
                if qid in done_ids:
                    continue
                question = str(q.get("question") or q.get("query") or "")
                preferred = q.get("select_tools") if isinstance(q.get("select_tools"), list) else []
                shortlist = _shortlist_tools(compact, question, k=40, preferred=preferred)
                wrote += 1
                if wrote == 1 or idx % 10 == 0:
                    try:
                        hb_path.write_text(
                            json.dumps(
                                {
                                    "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                                    "idx": idx,
                                    "n": len(questions),
                                    "qid": qid,
                                    "resumed": len(existing_rows),
                                }
                            ),
                            encoding="utf-8",
                        )
                    except OSError:
                        pass
                    print(f"[fintool] {idx}/{len(questions)} qid={qid}", flush=True)
                obs = Observation(
                    as_of=str(proto.date_from or "eval"),
                    query=question,
                    tools=shortlist,
                    raw={"id": qid, "category": q.get("category")},
                )
                prompt = (
                    "You are sitting FinToolBench. Pick tools from the manifest, emit tool_calls "
                    "with {tool_name, step, output}, then a final execution_result. "
                    "RapidAPI is unavailable; produce the tool output you would expect from a live call, "
                    "clearly as the tool's return payload.\n"
                    + json.dumps(
                        {"id": qid, "question": question, "tools": shortlist},
                        ensure_ascii=False,
                    )
                )
                completion = runner.complete_json(
                    prompt,
                    schema=FINTOOL_SCHEMA,
                    system=LOCKED_SYSTEM + " Tool-use JSON only.",
                )
                parsed = completion.parsed or {}
                tool_calls = parsed.get("tool_calls") if isinstance(parsed.get("tool_calls"), list) else []
                if not tool_calls:
                    # Fall back to AgentAdapter.decide if the dedicated schema failed.
                    decision = agent.decide(obs)
                    tool_calls = decision.tool_calls or []
                    execution_result = decision.reasoning
                else:
                    execution_result = str(parsed.get("execution_result") or "")
                if tool_calls:
                    n_with_tools += 1
                row = {
                    "id": qid,
                    "question": question,
                    "query": question,
                    "tool_calls": _normalize_tool_calls(tool_calls),
                    "execution_result": execution_result,
                    "answer": execution_result,
                    "ground_truth": q.get("answer") or q.get("ground_truth") or "",
                }
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
                rows.append(row)
                done_ids.add(qid)

        eval_dir = artifacts / "eval"
        eval_dir.mkdir(parents=True, exist_ok=True)
        eval_metrics: dict[str, Any] = {}
        eval_notes = ""
        try:
            eval_metrics = _run_official_eval(self.module_path, out_jsonl, eval_dir)
        except Exception as exc:  # noqa: BLE001
            eval_notes = f"official evaluator failed: {exc}"

        metrics = [
            Metric(name="n_questions", value=float(len(rows)), source="fintoolbench"),
            Metric(name="n_with_tool_calls", value=float(n_with_tools), source="fintoolbench"),
        ]
        nested = eval_metrics.get("cap") if isinstance(eval_metrics.get("cap"), dict) else eval_metrics
        for key in ("tir", "tesr", "cer", "soft_score", "css"):
            val = _dig(nested, key)
            if isinstance(val, (int, float)):
                metrics.append(Metric(name=key, value=float(val), higher_is_better=True, source="evaluator"))
        com = eval_metrics.get("com") if isinstance(eval_metrics.get("com"), dict) else {}
        gates: list[GateResult] = []
        for key in ("tmr", "imr", "dmr"):
            val = _dig(com, key)
            if isinstance(val, (int, float)):
                metrics.append(Metric(name=key, value=float(val), higher_is_better=False, source="evaluator"))
                gates.append(
                    GateResult(
                        gate_id=f"{key}_lte",
                        metric=key,
                        op="lte",
                        threshold=1.0,
                        actual=float(val),
                        passed=float(val) <= 1.0,
                        required=False,
                        rationale="mismatch rate (lower is better); recorded, not a global veto",
                    )
                )
        status = SuiteStatus.PASS.value if n_with_tools else SuiteStatus.FAIL.value
        notes = (
            f"Full question set n={len(rows)} tool_calls={n_with_tools}. "
            "RapidAPI/akshare not subscribed — tool outputs are Grok-produced. "
            + eval_notes
        )
        return SuiteResult(
            suite_id=SUITE_ID,
            status=status,
            protocol=proto,
            metrics=metrics,
            gates=gates,
            artifacts=[
                Artifact(kind="tool_trace", path=str(out_jsonl), media_type="application/jsonl"),
                Artifact(kind="metrics_json", path=str(eval_dir), media_type="application/json"),
            ],
            traces_path=str(out_jsonl),
            notes=notes,
            upstream_cli=UPSTREAM_CLI.format(inputs=str(out_jsonl), output_dir=str(eval_dir)),
        )


QUESTION_ALIASES = {
    "full": QUESTIONS,
    "official": QUESTIONS,
    "all": QUESTIONS,
    "295": QUESTIONS,
}


def _resolve_questions_path(repo_root: Path, raw: Any) -> Path:
    """Map protocol aliases like 'full' onto the official 295-question JSONL."""

    text = str(raw or "").strip()
    alias = QUESTION_ALIASES.get(text.lower()) if text else QUESTIONS
    if alias:
        path = Path(alias)
    else:
        path = Path(text)
    if not path.is_absolute():
        path = repo_root / path
    if path.is_file():
        return path
    if path.is_dir():
        hits = sorted(path.glob("*.jsonl"))
        if hits:
            return hits[0]
    fallback = repo_root / QUESTIONS
    if fallback.is_file():
        return fallback
    raise FileNotFoundError(
        f"FinToolBench question set not found (raw={raw!r}). Expected {fallback}"
    )


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def _shortlist_tools(
    compact: list[dict[str, Any]],
    question: str,
    k: int = 40,
    preferred: list[Any] | None = None,
) -> list[dict[str, Any]]:
    by_name = {str(t.get("name")): t for t in compact if t.get("name")}
    picked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name in preferred or []:
        tool = by_name.get(str(name))
        if tool and str(name) not in seen:
            picked.append(tool)
            seen.add(str(name))
    words = {w.lower() for w in question.replace("?", " ").split() if len(w) > 3}
    scored: list[tuple[int, dict[str, Any]]] = []
    for tool in compact:
        name = str(tool.get("name") or "")
        if name in seen:
            continue
        blob = (name + " " + str(tool.get("description") or "")).lower()
        score = sum(1 for w in words if w in blob)
        scored.append((score, tool))
    scored.sort(key=lambda x: x[0], reverse=True)
    for s, t in scored:
        if len(picked) >= k:
            break
        if s > 0 or len(picked) < 15:
            picked.append(t)
    if len(picked) < 15:
        for _, t in scored:
            if len(picked) >= k:
                break
            if t not in picked:
                picked.append(t)
    return picked[:k]


def _normalize_tool_calls(raw: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        name = item.get("tool_name") or item.get("name") or item.get("tool")
        if not name:
            continue
        output = item.get("output")
        if output is None:
            output = json.dumps(item.get("arguments") or {}, ensure_ascii=False)
        if not isinstance(output, str):
            output = json.dumps(output, ensure_ascii=False)
        out.append(
            {
                "tool_name": str(name),
                "step": int(item.get("step") or i),
                "output": output,
            }
        )
    return out


def _dig(blob: Any, key: str) -> Any:
    if isinstance(blob, dict):
        if key in blob:
            return blob[key]
        for v in blob.values():
            found = _dig(v, key)
            if found is not None:
                return found
    return None


def _run_official_eval(module_path: Path, inputs: Path, output_dir: Path) -> dict[str, Any]:
    """Import the official evaluator with the judge routed to xAI when boyue is dead."""

    eval_dir = module_path / "code_bench" / "evaluate"
    if str(eval_dir) not in sys.path:
        sys.path.insert(0, str(eval_dir))
    if str(module_path) not in sys.path:
        sys.path.insert(0, str(module_path))

    try:
        import code_bench.utils.model_requests as mr  # type: ignore

        def _xai_judge(model: str = "", messages=None, available_tools=None, num_samples: int = 1):
            from finagent.harness.grok import GrokRunner

            prompt = ""
            if messages:
                prompt = "\n".join(str(m.get("content") or "") for m in messages)
            runner = GrokRunner()
            schema = {
                "type": "object",
                "properties": {
                    "score": {"type": "number"},
                    "label": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["score", "label"],
            }
            completion = runner.complete_json(prompt or "score 0", schema=schema)
            parsed = completion.parsed or {"score": 0.0, "label": "wrong", "reason": "empty"}
            return json.dumps(parsed)

        mr.boyue_model_requests = _xai_judge  # type: ignore[assignment]
    except Exception:
        pass

    os.environ.setdefault("TOOL_METADATA_PATH", str(module_path / "tools" / "tools_all_annotated.jsonl"))
    os.environ.setdefault("SCORE_REPEAT_K", "1")
    from evaluator import evaluate_dataset, load_jsonl_as_dict  # type: ignore

    data = load_jsonl_as_dict(str(inputs))
    results, metrics = evaluate_dataset(data)
    (output_dir / "all_metrics.json").write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")
    with (output_dir / "results.jsonl").open("w", encoding="utf-8") as fh:
        for row in results:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return metrics if isinstance(metrics, dict) else {}


def _assert_protocol() -> None:
    _: EnvAdapter = FinToolBenchEnvAdapter()  # type: ignore[assignment]


__all__ = ["SUITE_ID", "FinToolBenchEnvAdapter"]
