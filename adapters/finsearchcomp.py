"""FinSearchComp — time-sensitive financial search / investigation.

Upstream: https://github.com/randomtutu/FinSearchComp  ·  arXiv:2509.13160
Dataset: https://huggingface.co/datasets/ByteSeedXpert/FinSearchComp  ·  CC-BY-4.0

Official surface:
  python finsearchcomp/chat/chat.py ...
  python finsearchcomp/eval/eval.py ...
635 expert questions. Never invent a subset. Never fake pass metrics.

Patches / harvest / resume: `adapters.v2_ops.finsearchcomp`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .base import (
    AgentAdapter,
    Artifact,
    EnvAdapter,
    Metric,
    ProtocolSpec,
    SuiteResult,
    SuiteStatus,
    skipped_suite,
)
from .v2_ops.finsearchcomp import (
    MODULE_REL,
    N_QUESTIONS,
    SUITE_ID,
    TASKS,
    UPSTREAM_CLI,
    VENV_NAME,
    apply_continue_patches,
    count_chat_rows,
    ensure_install,
    hard_blockers,
    harvest_eval,
    harvest_existing_run,
    skip_notes,
)
from .v2_runtime import (
    artifacts_dir,
    error_result,
    execute_or_skip,
    repo_venv_python,
    run_logged,
    tail_text,
    xai_env,
)


class FinSearchCompEnvAdapter:
    suite_id = SUITE_ID
    module_dir = MODULE_REL

    def __init__(self, repo_root: str | Path = ".") -> None:
        self.repo_root = Path(repo_root).resolve()
        self.module_path = self.repo_root / MODULE_REL

    def describe(self) -> Mapping[str, Any]:
        return {
            "suite_id": SUITE_ID,
            "role": "exam_room",
            "layer": "environment.research_search",
            "task_suite": "time_sensitive_financial_search",
            "tier": "optional",
            "required_for_promote": False,
            "module": str(self.module_path),
            "entry": "python finsearchcomp/chat/chat.py + finsearchcomp/eval/eval.py",
            "artifacts": "finsearchcomp/result/eval-result/eval.json",
            "metrics": ["accuracy", "n_questions", "time_sensitive", "simple_historical", "complex_historical"],
            "pitfalls": [
                "Needs model API keys in finsearchcomp/config/config.yaml",
                "Time-sensitive split uses AkShare; snapshots go stale",
                "Official openai_api.py uses AzureOpenAI — glue-patched to OpenAI() for xAI",
            ],
            "wired": True,
        }

    def run(self, agent: AgentAdapter, protocol: ProtocolSpec) -> SuiteResult:
        _ = agent
        proto = ProtocolSpec(
            suite_id=SUITE_ID,
            date_from=protocol.date_from,
            date_to=protocol.date_to,
            universe=list(protocol.universe or ["global", "greater_china"]),
            data_vintage=protocol.data_vintage
            or "data/finsearchcomp_data.json (635) + akshare split (594)",
            extra=dict(protocol.extra),
        )
        proto.extra.setdefault("n_questions", N_QUESTIONS)
        proto.extra.setdefault("tasks", list(TASKS))
        proto.extra.setdefault("questions", "modules/finsearchcomp/data/finsearchcomp_data.json")
        skipped = execute_or_skip(
            suite_id=SUITE_ID,
            protocol=proto,
            upstream_cli=UPSTREAM_CLI,
            blockers=hard_blockers(self.module_path),
            skip_notes=skip_notes(self.module_path, dry=True),
        )
        if skipped:
            return skipped
        try:
            return self._run_full(proto)
        except Exception as exc:  # noqa: BLE001
            return error_result(
                SUITE_ID,
                proto,
                f"finsearchcomp official CLI error: {exc}",
                upstream_cli=UPSTREAM_CLI,
            )

    def _run_full(self, proto: ProtocolSpec) -> SuiteResult:
        from runners.grok import DEFAULT_MODEL_API, refresh_xai_api_key

        key = refresh_xai_api_key()
        if not key:
            return skipped_suite(
                SUITE_ID,
                protocol=proto,
                upstream_cli=UPSTREAM_CLI,
                notes="skip: XAI_API_KEY / ~/.grok/auth.json missing; cannot configure model+judge",
            )
        artifacts = Path(proto.extra.get("artifacts_dir") or artifacts_dir(self.repo_root, "finsearchcomp"))
        artifacts.mkdir(parents=True, exist_ok=True)
        python = proto.extra.get("python") or repo_venv_python(self.repo_root, VENV_NAME)
        model = str(proto.extra.get("model") or DEFAULT_MODEL_API)
        proto.extra["model"] = model

        ensure_install(python, self.module_path)
        apply_continue_patches(self.repo_root)

        data_file = self.module_path / "data" / "finsearchcomp_data.json"
        chat_out = artifacts / "chat.json"
        eval_out = artifacts / "eval.json"
        chat_log = artifacts / "chat.log"
        eval_log = artifacts / "eval.log"
        inner = self.module_path / "finsearchcomp"
        env = xai_env(pythonpath_dirs=[inner, self.module_path, self.repo_root])
        chat_cmd = [
            python,
            str(inner / "chat" / "chat.py"),
            "--model_name",
            model,
            "--input_file",
            str(data_file),
            "--output_path",
            str(chat_out),
            "--limit",
            "0",
        ]
        proc_chat = run_logged(chat_cmd, cwd=inner, env=env, log_path=chat_log)
        n_chat = count_chat_rows(chat_out)
        if proc_chat.returncode != 0 and n_chat <= 0:
            return SuiteResult(
                suite_id=SUITE_ID,
                status=SuiteStatus.ERROR.value,
                protocol=proto,
                artifacts=[Artifact(kind="log", path=str(chat_log), media_type="text/plain")],
                notes=(
                    f"official chat.py failed returncode={proc_chat.returncode} n_chat={n_chat}. "
                    + tail_text(chat_log, 20).replace("\n", " | ")[:500]
                ),
                upstream_cli=" ".join(chat_cmd),
            )

        eval_cmd = [
            python,
            str(inner / "eval" / "eval.py"),
            "--model_name",
            model,
            "--input",
            str(chat_out),
            "--output",
            str(eval_out),
        ]
        proc_eval = None
        if n_chat > 0:
            proc_eval = run_logged(eval_cmd, cwd=inner, env=env, log_path=eval_log)
        harvested = harvest_eval(eval_out, chat_out)
        eval_rc = proc_eval.returncode if proc_eval is not None else None
        status = (
            SuiteStatus.PASS.value
            if proc_chat.returncode == 0 and eval_rc == 0 and eval_out.is_file()
            else SuiteStatus.FAIL.value
            if n_chat > 0
            else SuiteStatus.ERROR.value
        )
        metrics = [
            Metric(name=k, value=v, source=str(eval_out) if eval_out.is_file() else "chat.json")
            for k, v in harvested.items()
            if isinstance(v, (int, float))
        ]
        arts = [
            Artifact(kind="chat_log", path=str(chat_log), media_type="text/plain"),
            Artifact(kind="eval_log", path=str(eval_log), media_type="text/plain"),
            Artifact(kind="chat_json", path=str(chat_out), media_type="application/json"),
        ]
        if eval_out.is_file():
            arts.append(Artifact(kind="eval_json", path=str(eval_out), media_type="application/json"))
        notes = (
            f"Official FinSearchComp chat+eval model={model} "
            f"chat_rc={proc_chat.returncode} eval_rc={eval_rc} n_chat={n_chat}. "
            "config.yaml pointed at xAI; openai_api AzureOpenAI glue-patched to OpenAI(). "
            "limit=0 (all questions; documented official flag). "
            + tail_text(eval_log if eval_log.is_file() else chat_log, 12).replace("\n", " | ")[:400]
        )
        return SuiteResult(
            suite_id=SUITE_ID,
            status=status,
            protocol=proto,
            metrics=metrics,
            artifacts=arts,
            traces_path=str(artifacts),
            notes=notes,
            upstream_cli=" && ".join([" ".join(chat_cmd), " ".join(eval_cmd)]),
        )


def _assert_protocol() -> None:
    _: EnvAdapter = FinSearchCompEnvAdapter()  # type: ignore[assignment]


__all__ = ["SUITE_ID", "FinSearchCompEnvAdapter", "harvest_existing_run", "apply_continue_patches"]
