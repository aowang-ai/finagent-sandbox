"""FinMCP-Bench — MCP tool orchestration exam room.

Upstream code hub: https://github.com/aliyun/qwen-dianjin (DianJin-TIR/)
Paper: arXiv:2603.24943  ·  ICASSP 2026
Dataset: https://huggingface.co/datasets/DianJin/FinMCP-Bench (CC-BY-NC-SA-4.0)

Official surface: `python eval/evaluation.py --eval_data_path=...` after
inference that writes `messages_pred`. 613 samples / 65 real MCPs.
Qieman MCP Server URL + schema are required for inference. Never fake pass.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

from adapters.base import (
    AgentAdapter,
    Artifact,
    EnvAdapter,
    Metric,
    ProtocolSpec,
    SuiteResult,
    SuiteStatus,
    skipped_suite,
)
from adapters._ops.runtime import (
    error_result,
    execute_or_skip,
    repo_venv_python,
    run_logged,
    skip_message,
    tail_text,
    xai_env,
)

SUITE_ID = "finmcp.tool_mcp"
MODULE_REL = "modules/finmcp"
TIR_REL = "DianJin-TIR"
UPSTREAM_CLI = (
    "python DianJin-TIR/infer/inference_api.py && "
    "python DianJin-TIR/eval/evaluation.py --eval_data_path=<pred.json>"
)
N_SAMPLES = 613
N_MCPS = 65
VENV_NAME = "v2_finmcp"


class FinMcpEnvAdapter:
    suite_id = SUITE_ID
    module_dir = MODULE_REL

    def __init__(self, repo_root: str | Path = ".") -> None:
        self.repo_root = Path(repo_root).resolve()
        self.module_path = self.repo_root / MODULE_REL
        self.tir_path = self.module_path / TIR_REL

    def describe(self) -> Mapping[str, Any]:
        return {
            "suite_id": SUITE_ID,
            "role": "exam_room",
            "layer": "environment.tool_mcp",
            "task_suite": "mcp_tool_orchestration",
            "tier": "optional",
            "required_for_promote": False,
            "module": str(self.tir_path),
            "entry": "python DianJin-TIR/eval/evaluation.py --eval_data_path=...",
            "artifacts": "eval stdout: Tool Precision / Recall / F1 / EMR (consist)",
            "metrics": ["tool_precision", "tool_recall", "tool_f1", "emr"],
            "pitfalls": [
                "benchmark_final.json is on HuggingFace DianJin/FinMCP-Bench",
                "65 MCP servers from Qieman require MCP Server URL + MCP_SCHEMA",
                "HF dataset license CC-BY-NC-SA-4.0 (non-commercial share-alike)",
            ],
            "wired": True,
        }

    def run(self, agent: AgentAdapter, protocol: ProtocolSpec) -> SuiteResult:
        _ = agent
        proto = ProtocolSpec(
            suite_id=SUITE_ID,
            date_from=protocol.date_from,
            date_to=protocol.date_to,
            universe=list(protocol.universe or []),
            data_vintage=protocol.data_vintage
            or "DianJin/FinMCP-Bench 613 samples / 65 MCPs (HF)",
            extra=dict(protocol.extra),
        )
        proto.extra.setdefault("n_samples", N_SAMPLES)
        proto.extra.setdefault("n_mcps", N_MCPS)
        proto.extra.setdefault("splits", ["single_tool", "multi_tool", "multi_turn"])
        proto.extra.setdefault("dataset", "https://huggingface.co/datasets/DianJin/FinMCP-Bench")
        skipped = execute_or_skip(
            suite_id=SUITE_ID,
            protocol=proto,
            upstream_cli=UPSTREAM_CLI,
            blockers=_hard_blockers(self.tir_path),
            skip_notes=_skip_notes(self.tir_path, dry=True, proto=proto),
        )
        if skipped:
            return skipped
        try:
            return self._run_full(proto)
        except Exception as exc:  # noqa: BLE001
            return error_result(
                SUITE_ID,
                proto,
                f"finmcp official CLI error: {exc}",
                upstream_cli=UPSTREAM_CLI,
            )

    def _run_full(self, proto: ProtocolSpec) -> SuiteResult:
        from finagent.harness.grok import DEFAULT_MODEL_API, refresh_xai_api_key

        mcp_url = _lookup_env(proto, "QIEMAN_MCP_SERVER_URL", "MCP_SERVER_URL")
        mcp_schema = _lookup_env(proto, "QIEMAN_MCP_SCHEMA", "MCP_SCHEMA_PATH")
        schema_path = Path(mcp_schema) if mcp_schema else None
        bench = self.tir_path / "Benchmark" / "benchmark_final.json"
        proto.extra["benchmark_present"] = bench.is_file()
        proto.extra["benchmark_bytes"] = bench.stat().st_size if bench.is_file() else 0

        if not mcp_url or not schema_path or not schema_path.is_file():
            return skipped_suite(
                SUITE_ID,
                protocol=proto,
                upstream_cli=UPSTREAM_CLI,
                notes=(
                    "skip: Qieman MCP Server URL + MCP_SCHEMA missing "
                    f"(MCP_SERVER_URL/QIEMAN_MCP_SERVER_URL={'set' if mcp_url else 'unset'}; "
                    f"MCP_SCHEMA_PATH={'present' if schema_path and schema_path.is_file() else 'missing'}). "
                    f"benchmark_final.json is present at {bench} "
                    f"({proto.extra.get('benchmark_bytes')} bytes). "
                    "Official inference_api.py requires both MCP URL and schema; "
                    "not inventing a no-MCP protocol."
                ),
            )

        key = refresh_xai_api_key()
        if not key:
            return skipped_suite(
                SUITE_ID,
                protocol=proto,
                upstream_cli=UPSTREAM_CLI,
                notes="skip: XAI_API_KEY missing; cannot run inference_api.py assistant",
            )

        artifacts = Path(
            proto.extra.get("artifacts_dir") or (self.repo_root / "artifacts" / "finmcp")
        )
        artifacts.mkdir(parents=True, exist_ok=True)
        python = proto.extra.get("python") or repo_venv_python(self.repo_root, VENV_NAME)
        model = str(proto.extra.get("model") or DEFAULT_MODEL_API)
        pred_path = artifacts / "messages_pred.json"
        cfg_path = artifacts / "infer_config.yaml"
        cfg_path.write_text(
            (
                f'MCP_SERVER_URL: "{mcp_url}"\n'
                f'MCP_SCHEMA_PATH: "{schema_path}"\n'
                f"query_data_path: {json.dumps(str(bench))}\n"
                f"answer_save_path: {json.dumps(str(pred_path))}\n"
                "mcp_timeout: 30\n"
                "mcp_max_retries: 3\n"
                "max_tool_num: 20\n"
                "enable_thinking: false\n"
                "max_new_tokens: 4096\n"
                'ASSISTANT_API_BASE: "https://api.x.ai/v1"\n'
                f"ASSISTANT_API_KEY: {json.dumps(key)}\n"
                f"model: {json.dumps(model)}\n"
                'model_provider: "openai"\n'
                "max_concurrency: 2\n"
            ),
            encoding="utf-8",
        )
        plugin_env = proto.extra.get("plugin_env") if isinstance(proto.extra.get("plugin_env"), dict) else {}
        env = xai_env(extra=plugin_env or None, pythonpath_dirs=[self.tir_path, self.repo_root])
        sandbox = proto.extra.get("_sandbox")
        infer_log = artifacts / "inference.log"
        infer_cmd = [
            python,
            str(self.tir_path / "infer" / "inference_api.py"),
            "--config",
            str(cfg_path),
        ]
        proc_inf = _run_cmd(
            infer_cmd,
            cwd=self.tir_path / "infer",
            env=env,
            log_path=infer_log,
            sandbox=sandbox,
        )
        if proc_inf.returncode != 0 or not pred_path.is_file():
            return SuiteResult(
                suite_id=SUITE_ID,
                status=SuiteStatus.ERROR.value,
                protocol=proto,
                artifacts=[Artifact(kind="log", path=str(infer_log), media_type="text/plain")],
                notes=(
                    f"official inference_api.py failed rc={proc_inf.returncode}. "
                    + tail_text(infer_log, 20).replace("\n", " | ")[:500]
                ),
                upstream_cli=" ".join(infer_cmd),
            )
        eval_log = artifacts / "evaluation.log"
        eval_cmd = [
            python,
            str(self.tir_path / "eval" / "evaluation.py"),
            "--eval_data_path",
            str(pred_path),
        ]
        proc_ev = _run_cmd(
            eval_cmd,
            cwd=self.tir_path / "eval",
            env=env,
            log_path=eval_log,
            sandbox=sandbox,
        )
        harvested = _harvest_eval_log(eval_log)
        status = SuiteStatus.PASS.value if proc_ev.returncode == 0 else SuiteStatus.FAIL.value
        metrics = [
            Metric(name=k, value=v, source=str(eval_log))
            for k, v in harvested.items()
            if isinstance(v, (int, float))
        ]
        return SuiteResult(
            suite_id=SUITE_ID,
            status=status,
            protocol=proto,
            metrics=metrics,
            artifacts=[
                Artifact(kind="infer_log", path=str(infer_log), media_type="text/plain"),
                Artifact(kind="eval_log", path=str(eval_log), media_type="text/plain"),
                Artifact(kind="pred_json", path=str(pred_path), media_type="application/json"),
            ],
            traces_path=str(artifacts),
            notes=(
                f"Official FinMCP inference+eval model={model} "
                f"inf_rc={proc_inf.returncode} eval_rc={proc_ev.returncode}."
            ),
            upstream_cli=" && ".join([" ".join(infer_cmd), " ".join(eval_cmd)]),
        )


def _hard_blockers(tir_path: Path) -> list[str]:
    blockers: list[str] = []
    if not tir_path.is_dir():
        blockers.append(
            "modules/finmcp/DianJin-TIR missing (clone https://github.com/aliyun/qwen-dianjin)"
        )
        return blockers
    bench = tir_path / "Benchmark" / "benchmark_final.json"
    if not bench.is_file():
        blockers.append(
            "benchmark_final.json not in git; fetch HuggingFace DianJin/FinMCP-Bench"
        )
    return blockers


def _lookup_env(proto: ProtocolSpec, *keys: str) -> str:
    """Prefer protocol.extra['plugin_env'] over raw os.environ."""

    plugin_env = proto.extra.get("plugin_env")
    if isinstance(plugin_env, dict):
        for key in keys:
            value = plugin_env.get(key)
            if value:
                return str(value).strip()
    for key in keys:
        value = os.environ.get(key)
        if value:
            return str(value).strip()
    return ""


def _run_cmd(
    cmd: list[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    log_path: Path,
    sandbox: object | None = None,
) -> SimpleNamespace:
    """Official CLI: sandbox.exec_sync when a sandbox is seated, else host run_logged."""

    if sandbox is not None:
        print(f"[suite] sandbox.exec_sync cwd={cwd} cmd={' '.join(cmd)} log={log_path}", flush=True)
        result = sandbox.exec_sync(list(cmd), cwd=str(cwd), env=dict(env))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as logf:
            logf.write(f"$ {' '.join(cmd)}\n")
            if result.stdout:
                logf.write(result.stdout)
                if not str(result.stdout).endswith("\n"):
                    logf.write("\n")
            if result.stderr:
                logf.write(result.stderr)
        return SimpleNamespace(returncode=int(result.return_code))
    return run_logged(cmd, cwd=cwd, env=env, log_path=log_path)


def _skip_notes(tir_path: Path, *, dry: bool, proto: ProtocolSpec | None = None) -> str:
    extras: list[str] = []
    proto = proto or ProtocolSpec(suite_id=SUITE_ID)
    mcp_url = _lookup_env(proto, "QIEMAN_MCP_SERVER_URL", "MCP_SERVER_URL")
    if not mcp_url:
        extras.append("Qieman MCP_SERVER_URL / QIEMAN_MCP_SERVER_URL unset")
    schema = _lookup_env(proto, "QIEMAN_MCP_SCHEMA", "MCP_SCHEMA_PATH")
    if not schema:
        extras.append("MCP_SCHEMA_PATH / QIEMAN_MCP_SCHEMA unset")
    return skip_message(_hard_blockers(tir_path), dry=dry, extras=extras)


def _harvest_eval_log(log_path: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    if not log_path.is_file():
        return out
    text = log_path.read_text(encoding="utf-8", errors="replace")
    import re

    for name, pat in (
        ("tool_precision", r"Precision[^0-9]*([0-9.]+)"),
        ("tool_recall", r"Recall[^0-9]*([0-9.]+)"),
        ("tool_f1", r"F1[^0-9]*([0-9.]+)"),
        ("emr", r"EMR[^0-9]*([0-9.]+)"),
    ):
        m = re.search(pat, text, re.I)
        if m:
            try:
                out[name] = float(m.group(1))
            except ValueError:
                pass
    return out


def _assert_protocol() -> None:
    _: EnvAdapter = FinMcpEnvAdapter()  # type: ignore[assignment]


__all__ = ["SUITE_ID", "FinMcpEnvAdapter"]
