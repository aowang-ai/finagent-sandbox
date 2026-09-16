"""Vals Finance Agent Benchmark — expert SEC / research tasks + tools.

Upstream: https://github.com/vals-ai/finance-agent  ·  arXiv:2508.00828
Site: https://www.vals.ai/benchmarks/finance_agent

Official surface: `finance-agent --question-file data/public.txt`.
Full 537-question suite is gated on platform.vals.ai (VALS_API_KEY).
Public clone ships 50 questions. Never fake pass metrics.

Patches / harvest / resume: `adapters.v2_ops.vals_finance_agent`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .base import (
    AgentAdapter,
    EnvAdapter,
    ProtocolSpec,
    SuiteResult,
    skipped_suite,
)
from .v2_ops.vals_finance_agent import (
    MODULE_REL,
    N_FULL,
    N_PUBLIC,
    SUITE_ID,
    TOOLS,
    UPSTREAM_CLI,
    VENV_NAME,
    apply_continue_patches,
    available_tools,
    ensure_grok_registry_model,
    ensure_install,
    find_results_json,
    hard_blockers,
    harvest_existing_run,
    harvest_results,
    skip_notes,
    suite_from_harvest,
)
from .v2_runtime import (
    artifacts_dir,
    error_result,
    execute_or_skip,
    repo_venv_python,
    run_logged,
    xai_env,
)


class ValsFinanceAgentEnvAdapter:
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
            "task_suite": "sec_research_with_tools",
            "wave": "v2",
            "required_for_promote": False,
            "module": str(self.module_path),
            "entry": "finance-agent --question-file data/public.txt",
            "artifacts": "logs/<run>/results.json",
            "metrics": ["n_questions", "n_success", "n_error"],
            "pitfalls": [
                "VALS_API_KEY + platform approval required for the full 537-question suite",
                "TAVILY_API_KEY and SEC_EDGAR_API_KEY for tools",
                "Open clone ships a 50-question public.txt subset, not the gated 537",
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
            or "vals-ai/finance-agent data/public.txt (50 public; 537 gated)",
            extra=dict(protocol.extra),
        )
        proto.extra.setdefault("n_questions_public", N_PUBLIC)
        proto.extra.setdefault("n_questions_full", N_FULL)
        proto.extra.setdefault("tools", list(TOOLS))
        proto.extra.setdefault("questions", "modules/vals_finance_agent/data/public.txt")
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
                f"vals_finance_agent official CLI error: {exc}",
                upstream_cli=UPSTREAM_CLI,
            )

    def _run_full(self, proto: ProtocolSpec) -> SuiteResult:
        from runners.grok import DEFAULT_MODEL_API, refresh_xai_api_key

        artifacts = Path(proto.extra.get("artifacts_dir") or artifacts_dir(self.repo_root, "vals_finance_agent"))
        artifacts.mkdir(parents=True, exist_ok=True)
        python = proto.extra.get("python") or repo_venv_python(self.repo_root, VENV_NAME)
        public = self.module_path / "data" / "public.txt"
        model = str(proto.extra.get("model") or f"grok/{DEFAULT_MODEL_API}")
        tools = available_tools()
        proto.extra["tools_enabled"] = list(tools)
        proto.extra["tools_skipped"] = [t for t in TOOLS if t not in tools]
        proto.extra["model"] = model

        key = refresh_xai_api_key()
        if not key:
            return skipped_suite(
                SUITE_ID,
                protocol=proto,
                upstream_cli=UPSTREAM_CLI,
                notes="skip: XAI_API_KEY / ~/.grok/auth.json missing; cannot point LLM at xAI",
            )

        apply_continue_patches(self.repo_root)
        ensure_install(self.repo_root, python)
        ensure_grok_registry_model(python, DEFAULT_MODEL_API)

        log_path = artifacts / "finance_agent.log"
        cmd = [
            python,
            "-m",
            "finance_agent.run_agent",
            "--question-file",
            str(public),
            "--model",
            model,
            "--parallelism",
            str(proto.extra.get("parallelism") or "8"),
        ]
        if tools:
            cmd.extend(["--tools", *tools])
        env = xai_env(pythonpath_dirs=[self.module_path, self.repo_root])
        env["OPENAI_API_KEY"] = key
        env["OPENAI_BASE_URL"] = "https://api.x.ai/v1"
        proc = run_logged(cmd, cwd=self.module_path, env=env, log_path=log_path)
        results_file = find_results_json(self.module_path, artifacts)
        harvested = harvest_results(results_file, public, self.module_path)
        return suite_from_harvest(
            proto,
            harvested=harvested,
            results_file=results_file,
            log_path=log_path,
            traces_dir=self.module_path / "logs",
            artifacts=artifacts,
            model=model,
            tools=tools,
            skipped_tools=list(proto.extra.get("tools_skipped") or []),
            returncode=proc.returncode,
            upstream_cli=" ".join(cmd),
        )


def _assert_protocol() -> None:
    _: EnvAdapter = ValsFinanceAgentEnvAdapter()  # type: ignore[assignment]


__all__ = ["SUITE_ID", "ValsFinanceAgentEnvAdapter", "harvest_existing_run", "apply_continue_patches"]
