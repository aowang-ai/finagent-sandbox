"""Vals Finance Agent patches, harvest, and official resume.

Not an EnvAdapter. `adapters.vals_finance_agent` invokes `finance_agent.run_agent`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from adapters.base import Artifact, Metric, ProtocolSpec, SuiteResult, SuiteStatus
from adapters._ops.runtime import (
    apply_text_patch,
    artifacts_dir,
    load_json,
    python_imports_ok,
    repo_venv_python,
    run_logged,
    skip_message,
    tail_text,
    uv_pip_install,
    xai_env,
)

SUITE_ID = "vals_finance_agent.research"
MODULE_REL = "modules/vals_finance_agent"
UPSTREAM_CLI = "finance-agent --question-file data/public.txt --model <model>"
N_PUBLIC = 50
N_FULL = 537
TOOLS = ("web_search", "edgar_search", "parse_html_page", "retrieve_information")
VENV_NAME = "v2_vals"


def module_path(repo_root: Path) -> Path:
    return repo_root / MODULE_REL


def hard_blockers(mod: Path) -> list[str]:
    blockers: list[str] = []
    if not mod.is_dir():
        blockers.append("modules/vals_finance_agent missing (run scripts/clone_modules.sh)")
    if not (mod / "data" / "public.txt").is_file():
        blockers.append("data/public.txt missing")
    return blockers


def skip_notes(mod: Path, *, dry: bool) -> str:
    extras: list[str] = []
    if not os.environ.get("TAVILY_API_KEY"):
        extras.append("TAVILY_API_KEY missing (web_search will be skipped on execute)")
    if not (os.environ.get("SEC_EDGAR_API_KEY") or os.environ.get("SEC_API_KEY")):
        extras.append("SEC_EDGAR_API_KEY missing (edgar_search will be skipped on execute)")
    if not os.environ.get("VALS_API_KEY"):
        extras.append(
            "VALS_API_KEY missing (gated 537 unavailable; public.txt 50 is the official open protocol)"
        )
    return skip_message(hard_blockers(mod), dry=dry, extras=extras)


def available_tools() -> list[str]:
    tools: list[str] = []
    if os.environ.get("TAVILY_API_KEY"):
        tools.append("web_search")
    if os.environ.get("SEC_EDGAR_API_KEY") or os.environ.get("SEC_API_KEY"):
        tools.append("edgar_search")
    tools.extend(["parse_html_page", "retrieve_information"])
    return tools


def write_vals_env(mod: Path, key: str) -> None:
    env_path = mod / ".env"
    lines = [
        f"OPENAI_API_KEY={key}",
        "OPENAI_BASE_URL=https://api.x.ai/v1",
        f"XAI_API_KEY={key}",
    ]
    existing = env_path.read_text(encoding="utf-8") if env_path.is_file() else ""
    if "OPENAI_BASE_URL=https://api.x.ai/v1" in existing and "OPENAI_API_KEY=" in existing:
        return
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def patch_vals_resume(mod: Path) -> None:
    apply_text_patch(
        mod / "finance_agent" / "run_agent.py",
        marker="finance-agent-eval-infra resume skip finished qids",
        needle=(
            "    async def process_question(question: str, question_index: int):\n"
            "        async with semaphore:\n"
            "            agent = get_agent(parameters)\n"
            "            prompt = INSTRUCTIONS_PROMPT.format(question=question)\n"
            "            result = await agent.run([TextInput(text=prompt)], question_id=f\"q{question_index:03d}\")\n"
            "            return result\n"
            "\n"
            "    tasks = [process_question(question, i + 1) for i, question in enumerate(questions)]\n"
            "\n"
            "    results: list[AgentResult] = await tqdm.gather(*tasks, desc=\"Processing questions\")\n"
            "\n"
            "    formatted_results = []\n"
            "    for question, result in zip(questions, results):\n"
        ),
        replacement=(
            "    async def process_question(question: str, question_index: int):\n"
            "        async with semaphore:\n"
            "            agent = get_agent(parameters)\n"
            "            prompt = INSTRUCTIONS_PROMPT.format(question=question)\n"
            "            result = await agent.run([TextInput(text=prompt)], question_id=f\"q{question_index:03d}\")\n"
            "            return result\n"
            "\n"
            "    # finance-agent-eval-infra resume skip finished qids\n"
            "    from pathlib import Path as _Path\n"
            "    _finished: set[str] = set()\n"
            "    _logs = _Path(\"logs\")\n"
            "    if _logs.is_dir():\n"
            "        for _p in _logs.rglob(\"result.json\"):\n"
            "            if \"/turns/\" in _p.as_posix():\n"
            "                continue\n"
            "            _qid = _p.parent.name\n"
            "            if _qid.startswith(\"q\") and _qid[1:].isdigit():\n"
            "                _finished.add(_qid)\n"
            "    _todo = [(i + 1, q) for i, q in enumerate(questions) if f\"q{i + 1:03d}\" not in _finished]\n"
            "    print(\n"
            "        f\"Resume vals: {len(_finished)} finished qids, {len(_todo)} remaining of {len(questions)}\",\n"
            "        flush=True,\n"
            "    )\n"
            "\n"
            "    tasks = [process_question(q, i) for i, q in _todo]\n"
            "    results: list[AgentResult] = (\n"
            "        await tqdm.gather(*tasks, desc=\"Processing questions\") if tasks else []\n"
            "    )\n"
            "\n"
            "    formatted_results = []\n"
            "    for (_qi, question), result in zip(_todo, results):\n"
        ),
        label="vals",
    )


def patch_vals_retry_cap(mod: Path) -> None:
    apply_text_patch(
        mod / "finance_agent" / "exceptions.py",
        marker="finance-agent-eval-infra retry cap",
        needle="            max_tries=100,\n",
        replacement=(
            "            max_tries=8,  # finance-agent-eval-infra retry cap "
            "(was 100; 429 must not hang remaining qs)\n"
        ),
        label="vals",
    )


def ensure_install(repo_root: Path, python: str) -> None:
    if python_imports_ok(python, "finance_agent", "model_library"):
        return
    print("[vals] installing finance-agent + model-library into venv", flush=True)
    uv_pip_install(python, "-e", str(repo_root / MODULE_REL))


def ensure_grok_registry_model(python: str, model_api: str) -> None:
    """Register the eval Grok model in model_library's xai_models.yaml if missing."""

    import subprocess

    script = (
        "import pathlib, model_library\n"
        f"model_api = {model_api!r}\n"
        "key = 'grok/' + model_api\n"
        "root = pathlib.Path(model_library.__file__).resolve().parent\n"
        "path = root / 'config' / 'xai_models.yaml'\n"
        "text = path.read_text(encoding='utf-8')\n"
        "if key in text:\n"
        "    print('[vals] yaml already has', key)\n"
        "    raise SystemExit(0)\n"
        "block = (\n"
        "    f'  {key}:\\n'\n"
        "    '    label: Grok eval (non-reasoning)\\n'\n"
        "    '    release_date: 2026-03-09\\n'\n"
        "    '    open_source: false\\n'\n"
        "    '    properties:\\n'\n"
        "    '      context_window: 2_000_000\\n'\n"
        "    '      max_tokens: 2_000_000\\n'\n"
        "    '      training_cutoff: null\\n'\n"
        "    '      reasoning_model: false\\n'\n"
        "    '    documentation_url: \"\"\\n'\n"
        "    '    costs_per_million_token:\\n'\n"
        "    '      input: 2.00\\n'\n"
        "    '      output: 6.00\\n'\n"
        "    '      cache:\\n'\n"
        "    '        read: 0.20\\n'\n"
        ")\n"
        "path.write_text(text.rstrip() + '\\n' + block, encoding='utf-8')\n"
        "print('[vals] registered yaml', key)\n"
    )
    subprocess.run([python, "-c", script], check=False)


def apply_continue_patches(repo_root: str | Path = ".") -> None:
    from finagent.harness.grok import refresh_xai_api_key

    root = Path(repo_root).resolve()
    mod = module_path(root)
    key = refresh_xai_api_key()
    if key:
        write_vals_env(mod, key)
    patch_vals_resume(mod)
    patch_vals_retry_cap(mod)


def find_results_json(mod: Path, artifacts: Path) -> Path | None:
    hits: list[Path] = []
    logs = mod / "logs"
    if logs.is_dir():
        hits.extend(logs.rglob("results.json"))
    hits.extend(artifacts.rglob("results.json"))
    if not hits:
        return None
    return max(hits, key=lambda p: p.stat().st_mtime)


def harvest_per_question(mod: Path) -> dict[str, Any] | None:
    """Unique-qid harvest: newest q*/result.json per question, ignore turn dumps."""

    logs = mod / "logs"
    if not logs.is_dir():
        return None
    newest: dict[str, tuple[float, Path]] = {}
    for path in logs.rglob("result.json"):
        if "/turns/" in path.as_posix():
            continue
        qid = path.parent.name
        if not (qid.startswith("q") and qid[1:].isdigit()):
            continue
        mtime = path.stat().st_mtime
        prev = newest.get(qid)
        if prev is None or mtime >= prev[0]:
            newest[qid] = (mtime, path)
    inflight: set[str] = set()
    for path in logs.rglob("q*"):
        if path.is_dir() and path.name.startswith("q") and path.name[1:].isdigit():
            if path.name not in newest:
                inflight.add(path.name)
    if not newest and not inflight:
        return None
    n_ok = 0
    n_err = 0
    ok_ids: list[str] = []
    fail_ids: list[str] = []
    fail_reasons: dict[str, str] = {}
    for qid, (_, path) in sorted(newest.items()):
        data = load_json(path)
        if not isinstance(data, dict):
            n_err += 1
            fail_ids.append(qid)
            fail_reasons[qid] = "unreadable_result_json"
            continue
        if data.get("success"):
            n_ok += 1
            ok_ids.append(qid)
            continue
        n_err += 1
        fail_ids.append(qid)
        err = None
        ferr = data.get("final_error")
        if isinstance(ferr, dict):
            err = str(ferr.get("type") or ferr.get("message") or "")
        err = err or data.get("stop_reason")
        fail_reasons[qid] = str(err or "success=false")[:80]
    n_finished = n_ok + n_err
    return {
        "n_questions": float(N_PUBLIC),
        "n_finished": float(n_finished),
        "n_ok": float(n_ok),
        "n_fail": float(n_err),
        "n_success": float(n_ok),
        "n_error": float(n_err),
        "n_inflight": float(len(inflight)),
        "n_unstarted": float(max(0, N_PUBLIC - n_finished - len(inflight))),
        "ok_ids": ok_ids,
        "fail_ids": fail_ids,
        "inflight_ids": sorted(inflight),
        "fail_reasons": fail_reasons,
    }


def harvest_results(
    results_file: Path | None,
    public: Path,
    mod: Path | None = None,
) -> dict[str, Any]:
    n_public = N_PUBLIC
    try:
        n_public = sum(1 for line in public.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        n_public = N_PUBLIC
    if mod is not None:
        per_q = harvest_per_question(mod)
        if per_q:
            per_q["n_questions"] = float(n_public)
            per_q["n_unstarted"] = float(
                max(0, n_public - int(per_q.get("n_finished") or 0) - int(per_q.get("n_inflight") or 0))
            )
            return per_q
    data = load_json(results_file) if results_file is not None else None
    if isinstance(data, list) and data:
        n_ok = sum(1 for row in data if isinstance(row, dict) and row.get("success"))
        n_err = len(data) - n_ok
        return {
            "n_questions": float(n_public),
            "n_finished": float(len(data)),
            "n_ok": float(n_ok),
            "n_fail": float(n_err),
            "n_success": float(n_ok),
            "n_error": float(n_err),
            "n_inflight": 0.0,
            "n_unstarted": float(max(0, n_public - len(data))),
        }
    return {
        "n_questions": float(n_public),
        "n_finished": 0.0,
        "n_ok": 0.0,
        "n_fail": 0.0,
        "n_success": 0.0,
        "n_error": 0.0,
        "n_inflight": 0.0,
        "n_unstarted": float(n_public),
    }


def suite_from_harvest(
    proto: ProtocolSpec,
    *,
    harvested: dict[str, Any],
    results_file: Path | None,
    log_path: Path,
    traces_dir: Path,
    artifacts: Path,
    model: str,
    tools: list[str],
    skipped_tools: list[str],
    returncode: int | None,
    upstream_cli: str,
) -> SuiteResult:
    n_public = int(harvested.get("n_questions") or N_PUBLIC)
    n_finished = int(harvested.get("n_finished") or 0)
    n_ok = int(harvested.get("n_ok") or harvested.get("n_success") or 0)
    n_fail = int(harvested.get("n_fail") or harvested.get("n_error") or 0)
    n_inflight = int(harvested.get("n_inflight") or 0)
    harvest_path = artifacts / "harvest.json"
    serializable = {
        k: v
        for k, v in harvested.items()
        if isinstance(v, (int, float, str, list, dict, bool)) or v is None
    }
    harvest_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    if n_finished <= 0 and n_inflight <= 0:
        status = SuiteStatus.ERROR.value
    elif n_finished >= n_public and n_fail == 0 and (returncode in (0, None)):
        status = SuiteStatus.PASS.value
    else:
        status = SuiteStatus.FAIL.value
    metrics = [
        Metric(name="n_questions", value=float(n_public), source="public.txt"),
        Metric(name="n_finished", value=float(n_finished), source="q*/result.json"),
        Metric(name="n_ok", value=float(n_ok), source="q*/result.json"),
        Metric(name="n_fail", value=float(n_fail), source="q*/result.json"),
        Metric(name="n_inflight", value=float(n_inflight), source="q*/agent.log"),
        Metric(name="n_success", value=float(n_ok), source="q*/result.json"),
        Metric(name="n_error", value=float(n_fail), source="q*/result.json"),
    ]
    notes = (
        (f"SMOKE ({proto.extra.get('smoke_sample')}). " if proto.extra.get("smoke") else "")
        + f"Official public.txt protocol n={n_public} harvested n_finished={n_finished} "
        f"n_ok={n_ok} n_fail={n_fail} n_inflight={n_inflight} model={model} "
        f"returncode={returncode}. tools_enabled={tools}; tools_skipped={skipped_tools}. "
    )
    if n_finished >= n_public:
        notes += (
            f"CONTINUE complete: unique q*/result.json {n_finished}/{n_public} finished. "
        )
    else:
        notes += "Resume remaining public.txt qids (skip terminal result.json). "
    notes += (
        "Official accuracy vs gated 537 needs VALS_API_KEY "
        "+ platform GT (not present); reporting completion counts only. No fake accuracy."
    )
    if skipped_tools:
        notes += " TAVILY_API_KEY and/or SEC_EDGAR_API_KEY absent — skipped those tools honestly."
    fail_reasons = harvested.get("fail_reasons") or {}
    if isinstance(fail_reasons, dict) and fail_reasons:
        notes += " fail_reasons=" + json.dumps(fail_reasons)[:240]
    arts = [
        Artifact(kind="log", path=str(log_path), media_type="text/plain"),
        Artifact(kind="harvest_json", path=str(harvest_path), media_type="application/json"),
    ]
    if results_file:
        arts.append(Artifact(kind="results_json", path=str(results_file), media_type="application/json"))
    return SuiteResult(
        suite_id=SUITE_ID,
        status=status,
        protocol=proto,
        metrics=metrics,
        artifacts=arts,
        traces_path=str(traces_dir),
        notes=notes + " tail=" + tail_text(log_path, 15).replace("\n", " | ")[:400],
        upstream_cli=upstream_cli,
    )


def harvest_existing_run(repo_root: str | Path = ".") -> SuiteResult:
    """Build a SuiteResult from an already-run (possibly killed) official public.txt."""

    from finagent.harness.grok import DEFAULT_MODEL_API

    root = Path(repo_root).resolve()
    mod = module_path(root)
    artifacts = artifacts_dir(root, "vals_finance_agent")
    public = mod / "data" / "public.txt"
    log_path = artifacts / "finance_agent.log"
    python = repo_venv_python(root, VENV_NAME)
    model = f"grok/{DEFAULT_MODEL_API}"
    tools = available_tools()
    proto = ProtocolSpec(
        suite_id=SUITE_ID,
        data_vintage="vals-ai/finance-agent data/public.txt (50 public; 537 gated)",
        extra={
            "n_questions_public": N_PUBLIC,
            "n_questions_full": N_FULL,
            "tools": list(TOOLS),
            "questions": "modules/vals_finance_agent/data/public.txt",
            "execute": True,
            "artifacts_dir": str(artifacts),
            "python": python,
            "model": model,
            "tools_enabled": list(tools),
            "tools_skipped": [t for t in TOOLS if t not in tools],
            "harvest": "unique_qid_qstar_result_json",
        },
    )
    results_file = find_results_json(mod, artifacts)
    harvested = harvest_results(results_file, public, mod)
    cmd = [
        python,
        "-m",
        "finance_agent.run_agent",
        "--question-file",
        str(public),
        "--model",
        model,
        "--parallelism",
        "8",
    ]
    if tools:
        cmd.extend(["--tools", *tools])
    return suite_from_harvest(
        proto,
        harvested=harvested,
        results_file=results_file,
        log_path=log_path,
        traces_dir=mod / "logs",
        artifacts=artifacts,
        model=model,
        tools=tools,
        skipped_tools=[t for t in TOOLS if t not in tools],
        returncode=None,
        upstream_cli=" ".join(cmd),
    )


def progress_snapshot(repo_root: Path) -> dict[str, int]:
    harvested = harvest_per_question(module_path(repo_root)) or {}
    return {
        "n_finished": int(harvested.get("n_finished") or 0),
        "n_ok": int(harvested.get("n_ok") or 0),
        "n_fail": int(harvested.get("n_fail") or 0),
        "n_inflight": int(harvested.get("n_inflight") or 0),
    }


def resume_official(repo_root: str | Path = ".") -> int:
    """Resume official public.txt for remaining qids (skip terminal result.json)."""

    from finagent.harness.grok import DEFAULT_MODEL_API, refresh_xai_api_key

    root = Path(repo_root).resolve()
    key = refresh_xai_api_key(force=True)
    apply_continue_patches(root)
    python = repo_venv_python(root, VENV_NAME)
    mod = module_path(root)
    ensure_install(root, python)
    ensure_grok_registry_model(python, DEFAULT_MODEL_API)
    artifacts = artifacts_dir(root, "vals_finance_agent")
    log_path = artifacts / "finance_agent.log"
    public = mod / "data" / "public.txt"
    model = f"grok/{DEFAULT_MODEL_API}"
    tools = available_tools()
    cmd = [
        python,
        "-m",
        "finance_agent.run_agent",
        "--question-file",
        str(public),
        "--model",
        model,
        "--parallelism",
        "3",
    ]
    if tools:
        cmd.extend(["--tools", *tools])
    env = xai_env(pythonpath_dirs=[mod, root])
    if key:
        env["OPENAI_API_KEY"] = key
        env["OPENAI_BASE_URL"] = "https://api.x.ai/v1"
        env["XAI_API_KEY"] = key
    print(f"[vals] starting remaining public.txt tools={tools} model={model}", flush=True)
    proc = run_logged(cmd, cwd=mod, env=env, log_path=log_path, append=True)
    print(f"[vals] run_agent rc={proc.returncode}", flush=True)
    return int(proc.returncode)
