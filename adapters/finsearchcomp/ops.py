"""FinSearchComp patches, harvest, and official resume.

Not an EnvAdapter. `adapters.finsearchcomp` invokes official chat.py + eval.py.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from adapters.base import Artifact, Metric, ProtocolSpec, SuiteResult, SuiteStatus
from adapters._ops.runtime import (
    apply_text_patch,
    artifacts_dir,
    json_list_len,
    load_json,
    python_imports_ok,
    repo_venv_python,
    run_logged,
    skip_message,
    tail_text,
    uv_pip_install,
    xai_env,
)

SUITE_ID = "finsearchcomp.search"
MODULE_REL = "modules/finsearchcomp"
UPSTREAM_CLI = (
    "python finsearchcomp/chat/chat.py --model_name <model> "
    "--input_file data/finsearchcomp_data.json --output_path result/chat-result/chat.json "
    "&& python finsearchcomp/eval/eval.py --model_name <model> "
    "--input finsearchcomp/result/chat-result/chat.json "
    "--output finsearchcomp/result/eval-result/eval.json"
)
N_QUESTIONS = 635
TASKS = (
    "time_sensitive_data_fetching",
    "simple_historical_lookup",
    "complex_historical_investigation",
)
VENV_NAME = "v2_finsearch"


def module_path(repo_root: Path) -> Path:
    return repo_root / MODULE_REL


def hard_blockers(mod: Path) -> list[str]:
    blockers: list[str] = []
    if not mod.is_dir():
        blockers.append("modules/finsearchcomp missing (run scripts/clone_modules.sh)")
    if not (mod / "data" / "finsearchcomp_data.json").is_file():
        blockers.append("data/finsearchcomp_data.json missing")
    if not (mod / "finsearchcomp" / "chat" / "chat.py").is_file():
        blockers.append("finsearchcomp/chat/chat.py missing")
    if not (mod / "finsearchcomp" / "eval" / "eval.py").is_file():
        blockers.append("finsearchcomp/eval/eval.py missing")
    return blockers


def skip_notes(mod: Path, *, dry: bool) -> str:
    return skip_message(hard_blockers(mod), dry=dry)


def ensure_install(python: str, mod: Path) -> None:
    if python_imports_ok(python, "openai", "yaml", "tqdm", "tenacity", "akshare"):
        return
    req = mod / "finsearchcomp" / "requirements.txt"
    print("[finsearch] installing requirements.txt", flush=True)
    if req.is_file():
        uv_pip_install(python, "-r", str(req))
    else:
        uv_pip_install(python, "openai", "pyyaml", "tqdm", "tenacity", "akshare", "pandas", "requests")


def write_xai_config(mod: Path, key: str) -> None:
    cfg = mod / "finsearchcomp" / "config" / "config.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        (
            "# runtime overlay: Grok/xAI as model + judge (not committed)\n"
            "api:\n"
            "  openai:\n"
            f"    api_key: {json.dumps(key)}\n"
            '    api_url: "https://api.x.ai/v1"\n'
            "  deepseek:\n"
            '    api_key: ""\n'
            '    api_url: ""\n'
            "  anthropic:\n"
            '    api_key: ""\n'
            '    api_url: ""\n'
            "  gemini:\n"
            '    api_key: ""\n'
            '    api_url: ""\n'
            "chat_defaults:\n"
            "  max_tokens: 2048\n"
            "  temperature: 0.0\n"
            "  top_p: 1.0\n"
            "  frequency_penalty: 0.0\n"
            "  presence_penalty: 0.0\n"
            "  max_retries: 3\n"
            "  retry_delay: 5\n"
            "  max_retry_delay: 60\n"
            "extra_body: {}\n"
        ),
        encoding="utf-8",
    )


def fix_chat_merge_conflict(mod: Path) -> None:
    path = mod / "finsearchcomp" / "chat" / "chat.py"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if "<<<<<<< HEAD" not in text:
        return
    text = re.sub(
        r"<<<<<<< HEAD\n.*?\n=======\n(.*?)\n>>>>>>> [^\n]+\n",
        r"\1\n",
        text,
        flags=re.S,
    )
    path.write_text(text, encoding="utf-8")
    print("[finsearch] resolved chat.py merge conflict → --limit default 0 (all)", flush=True)


def patch_openai_compat(mod: Path) -> None:
    apply_text_patch(
        mod / "finsearchcomp" / "models" / "openai_api.py",
        marker="finance-agent-eval-infra xAI OpenAI()",
        needle=(
            "        self.client = openai.AzureOpenAI(\n"
            "            azure_endpoint=base_url,\n"
            "            api_version=api_version,\n"
            "            api_key=api_key,\n"
            "        )\n"
        ),
        replacement=(
            "        # finance-agent-eval-infra xAI OpenAI()\n"
            "        self.client = openai.OpenAI(\n"
            "            base_url=base_url,\n"
            "            api_key=api_key,\n"
            "        )\n"
            "        self.extra_headers = {}\n"
        ),
        label="finsearch",
    )


def patch_openai_load_kwargs(mod: Path) -> None:
    apply_text_patch(
        mod / "finsearchcomp" / "models" / "openai_api.py",
        marker="finance-agent-eval-infra drop api_key kwarg",
        needle=(
            "def load_model(model_name, **kwargs):\n"
            "    return OpenAIChat(model_name, **kwargs)\n"
        ),
        replacement=(
            "def load_model(model_name, **kwargs):\n"
            "    # finance-agent-eval-infra drop api_key kwarg\n"
            "    kwargs.pop('api_key', None)\n"
            "    return OpenAIChat(model_name, **kwargs)\n"
        ),
        label="finsearch",
    )


def patch_load_model_grok(mod: Path) -> None:
    apply_text_patch(
        mod / "finsearchcomp" / "chat" / "chat.py",
        marker="finance-agent-eval-infra grok route",
        needle=(
            "    if 'deepseek' in model_name_lower:\n"
            "        return load_deepseek(model_name, api_key=api_key)\n"
            "    elif 'gpt' in model_name_lower:\n"
            "        return load_openai(model_name, api_key=api_key)\n"
            "    elif 'gemini' in model_name_lower:\n"
            "        return load_gemini(model_name)\n"
            "    else:\n"
            "        raise ValueError(f\"Unsupported model type: {model_name}\")\n"
        ),
        replacement=(
            "    if 'deepseek' in model_name_lower:\n"
            "        return load_deepseek(model_name, api_key=api_key)\n"
            "    elif 'gpt' in model_name_lower:\n"
            "        return load_openai(model_name, api_key=api_key)\n"
            "    elif 'gemini' in model_name_lower:\n"
            "        return load_gemini(model_name)\n"
            "    elif any(s in model_name_lower for s in ('grok', 'xai', 'x-ai')):\n"
            "        # finance-agent-eval-infra grok route\n"
            "        return load_openai(model_name, api_key=api_key)\n"
            "    else:\n"
            "        # OpenAI-compatible fallback (xAI / Grok)\n"
            "        return load_openai(model_name, api_key=api_key)\n"
        ),
        label="finsearch",
    )


def patch_incremental_chat_save(mod: Path) -> None:
    apply_text_patch(
        mod / "finsearchcomp" / "chat" / "chat.py",
        marker="finance-agent-eval-infra incremental save",
        needle=(
            "            result = process_game(data, model, output_path)\n"
            "            results.append(result)\n"
            "            print(f\"Processed record {idx}/{len(subset)}\")\n"
        ),
        replacement=(
            "            result = process_game(data, model, output_path)\n"
            "            results.append(result)\n"
            "            print(f\"Processed record {idx}/{len(subset)}\")\n"
            "            # finance-agent-eval-infra incremental save\n"
            "            with open(output_path, 'w', encoding='utf-8') as _hf:\n"
            "                json.dump(results, _hf, ensure_ascii=False, indent=2)\n"
            "                _hf.flush()\n"
        ),
        label="finsearch",
    )


def patch_resume_chat(mod: Path) -> None:
    apply_text_patch(
        mod / "finsearchcomp" / "chat" / "chat.py",
        marker="finance-agent-eval-infra resume/append",
        needle=(
            "    # Read and process all dialogue data\n"
            "    results = []\n"
            "    with open(input_path, 'r', encoding='utf-8') as f:\n"
            "        records = json.load(f)\n"
            "        random.shuffle(records)\n"
            "        subset = records[:args.limit] if (args.limit and args.limit > 0) else records\n"
            "        for idx, data in enumerate(subset, start=1):\n"
            "            result = process_game(data, model, output_path)\n"
            "            results.append(result)\n"
            "            print(f\"Processed record {idx}/{len(subset)}\")\n"
            "            # finance-agent-eval-infra incremental save\n"
            "            with open(output_path, 'w', encoding='utf-8') as _hf:\n"
            "                json.dump(results, _hf, ensure_ascii=False, indent=2)\n"
            "                _hf.flush()\n"
        ),
        replacement=(
            "    # Read and process all dialogue data\n"
            "    # finance-agent-eval-infra resume/append\n"
            "    def _rec_key(row):\n"
            "        pid = row.get('prompt_id') if isinstance(row, dict) else None\n"
            "        while isinstance(pid, list):\n"
            "            pid = pid[0] if pid else ''\n"
            "        prompt = row.get('prompt') if isinstance(row, dict) else None\n"
            "        return (str(pid), str(prompt or ''))\n"
            "\n"
            "    results = []\n"
            "    done_counts = {}\n"
            "    if os.path.isfile(output_path):\n"
            "        try:\n"
            "            with open(output_path, 'r', encoding='utf-8') as _rf:\n"
            "                existing = json.load(_rf)\n"
            "            if isinstance(existing, list):\n"
            "                results = existing\n"
            "                for row in results:\n"
            "                    k = _rec_key(row)\n"
            "                    done_counts[k] = done_counts.get(k, 0) + 1\n"
            "        except Exception as _exc:\n"
            "            print(f\"Resume load failed ({_exc}); starting results empty\")\n"
            "            results = []\n"
            "            done_counts = {}\n"
            "\n"
            "    with open(input_path, 'r', encoding='utf-8') as f:\n"
            "        records = json.load(f)\n"
            "        remaining = []\n"
            "        consume = dict(done_counts)\n"
            "        for data in records:\n"
            "            k = _rec_key(data)\n"
            "            if consume.get(k, 0) > 0:\n"
            "                consume[k] -= 1\n"
            "                continue\n"
            "            remaining.append(data)\n"
            "        random.shuffle(remaining)\n"
            "        subset = remaining[:args.limit] if (args.limit and args.limit > 0) else remaining\n"
            "        print(\n"
            "            f\"Resume/append: {len(results)} existing, {len(subset)} remaining \"\n"
            "            f\"of {len(records)} input\"\n"
            "        )\n"
            "        for idx, data in enumerate(subset, start=1):\n"
            "            result = process_game(data, model, output_path)\n"
            "            results.append(result)\n"
            "            print(\n"
            "                f\"Processed record {len(results)}/{len(records)} \"\n"
            "                f\"(this-pass {idx}/{len(subset)})\"\n"
            "            )\n"
            "            # finance-agent-eval-infra incremental save\n"
            "            with open(output_path, 'w', encoding='utf-8') as _hf:\n"
            "                json.dump(results, _hf, ensure_ascii=False, indent=2)\n"
            "                _hf.flush()\n"
        ),
        label="finsearch",
    )


def patch_judge_parse(mod: Path) -> None:
    path = mod / "finsearchcomp" / "eval" / "eval.py"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if "finance-agent-eval-infra judge parse" in text:
        return
    start = text.find("        # Extract JSON part\n")
    end = text.find("        return float(score)\n", start)
    if start < 0 or end < 0:
        print("[finsearch] judge parse needle not found; leaving official parser", flush=True)
        return
    end = end + len("        return float(score)\n")
    replacement = '''        # finance-agent-eval-infra judge parse
        payload = None
        for _pat in (
            r"```json\\s*(\\{.*?\\})\\s*```",
            r"```(?:json)?\\s*(\\{.*?\\})\\s*```",
            r"(\\{\\s*\\"answer_score\\"\\s*:.+?\\})",
        ):
            json_match = re.search(_pat, judge_output, re.DOTALL)
            if not json_match:
                continue
            try:
                payload = json.loads(json_match.group(1))
                break
            except json.JSONDecodeError:
                continue
        if not isinstance(payload, dict):
            logger.warning(f"Unable to find JSON block from judge output: {judge_output}")
            return DEFAULT_ERROR_SCORE
        score = payload.get("answer_score", DEFAULT_ERROR_SCORE)
        if isinstance(score, list):
            if score and isinstance(score[0], list):
                score = score[0][0] if score[0] else DEFAULT_ERROR_SCORE
            elif score:
                score = score[0]
        return float(score)
'''
    path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
    print("[finsearch] patched eval.py judge JSON parse for answer_score int|list", flush=True)


def patch_resume_eval(mod: Path) -> None:
    path = mod / "finsearchcomp" / "eval" / "eval.py"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if "finance-agent-eval-infra resume eval" in text:
        return
    needle = (
        "        # Check if data is a list\n"
        "        if isinstance(data, list):\n"
        "            logger.info(f\"Processing a list of {len(data)} dialogue objects\")\n"
        "            all_results = []\n"
    )
    replacement = (
        "        # Check if data is a list\n"
        "        if isinstance(data, list):\n"
        "            logger.info(f\"Processing a list of {len(data)} dialogue objects\")\n"
        "            all_results = []\n"
        "            # finance-agent-eval-infra resume eval\n"
        "            _done_eval = set()\n"
        "            if output_path and os.path.isfile(output_path):\n"
        "                try:\n"
        "                    with open(output_path, 'r', encoding='utf-8') as _ef:\n"
        "                        _prev = json.load(_ef)\n"
        "                    if isinstance(_prev, list):\n"
        "                        all_results = _prev\n"
        "                        for _row in all_results:\n"
        "                            if not isinstance(_row, dict):\n"
        "                                continue\n"
        "                            _pid = _row.get('prompt_id')\n"
        "                            _done_eval.add(str(_pid))\n"
        "                        logger.info(\n"
        "                            f\"Resume eval: {len(all_results)} existing judged rows\"\n"
        "                        )\n"
        "                except Exception as _exc:\n"
        "                    logger.warning(f\"Resume eval load failed: {_exc}\")\n"
        "                    all_results = []\n"
        "                    _done_eval = set()\n"
    )
    if needle not in text:
        return
    text = text.replace(needle, replacement, 1)
    needle2 = (
        "            for i, item in enumerate(data):\n"
        "                # Use a temporary output file for individual results if needed\n"
        "                temp_output = None\n"
        "                \n"
        "                # Process each dialogue object\n"
        "                result = process_file(item, model, temp_output)\n"
        "                all_results.append(result)\n"
    )
    replacement2 = (
        "            for i, item in enumerate(data):\n"
        "                _pid = str(item.get('prompt_id') if isinstance(item, dict) else '')\n"
        "                if _pid and _pid in _done_eval:\n"
        "                    logger.info(f\"Resume eval skip already judged {_pid}\")\n"
        "                    continue\n"
        "                # Use a temporary output file for individual results if needed\n"
        "                temp_output = None\n"
        "                \n"
        "                # Process each dialogue object\n"
        "                result = process_file(item, model, temp_output)\n"
        "                all_results.append(result)\n"
        "                _done_eval.add(str(result.get('prompt_id') if isinstance(result, dict) else _pid))\n"
    )
    if needle2 not in text:
        path.write_text(text, encoding="utf-8")
        print("[finsearch] patched eval.py resume load but item-skip needle missing", flush=True)
        return
    path.write_text(text.replace(needle2, replacement2, 1), encoding="utf-8")
    print("[finsearch] patched eval.py resume/append of remaining judged rows", flush=True)


def patch_incremental_eval_save(mod: Path) -> None:
    apply_text_patch(
        mod / "finsearchcomp" / "eval" / "eval.py",
        marker="finance-agent-eval-infra incremental eval save",
        needle=(
            "                result = process_file(item, model, temp_output)\n"
            "                all_results.append(result)\n"
        ),
        replacement=(
            "                result = process_file(item, model, temp_output)\n"
            "                all_results.append(result)\n"
            "                # finance-agent-eval-infra incremental eval save\n"
            "                if output_path:\n"
            "                    with open(output_path, 'w', encoding='utf-8') as _hf:\n"
            "                        json.dump(all_results, _hf, ensure_ascii=False, indent=2)\n"
            "                        _hf.flush()\n"
        ),
        label="finsearch",
    )


def apply_continue_patches(repo_root: str | Path = ".") -> None:
    """Apply xAI + resume glue so official chat.py can append remaining records."""

    from finagent.harness.grok import refresh_xai_api_key

    root = Path(repo_root).resolve()
    mod = module_path(root)
    key = refresh_xai_api_key()
    if key:
        write_xai_config(mod, key)
    fix_chat_merge_conflict(mod)
    patch_openai_compat(mod)
    patch_openai_load_kwargs(mod)
    patch_load_model_grok(mod)
    patch_incremental_chat_save(mod)
    patch_resume_chat(mod)
    patch_incremental_eval_save(mod)
    patch_judge_parse(mod)
    patch_resume_eval(mod)


def load_chat_list(chat_out: Path) -> list[Any]:
    chat = load_json(chat_out)
    return chat if isinstance(chat, list) else []


def count_chat_rows(chat_out: Path) -> int:
    return len(load_chat_list(chat_out))


def count_model_responses(chat_out: Path) -> int:
    n = 0
    for row in load_chat_list(chat_out):
        if not isinstance(row, dict):
            continue
        dialogues = row.get("dialogues")
        if not isinstance(dialogues, list):
            continue
        if any(
            isinstance(d, dict) and str(d.get("model_response") or "").strip()
            for d in dialogues
        ):
            n += 1
    return n


def harvest_eval(eval_out: Path, chat_out: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    n_chat = count_chat_rows(chat_out)
    n_with = count_model_responses(chat_out)
    out["n_questions"] = float(N_QUESTIONS)
    out["n_chat"] = float(n_chat)
    out["n_total"] = float(N_QUESTIONS)
    out["n_with_response"] = float(n_with)
    data = load_json(eval_out)
    if data is None:
        return out
    items: list[Any]
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = [data]
        for key in (
            "accuracy",
            "time_sensitive",
            "simple_historical",
            "complex_historical",
            "avg_score",
            "score",
        ):
            val = data.get(key)
            if isinstance(val, (int, float)):
                out[key] = float(val)
        metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
        for key, val in metrics.items():
            if isinstance(val, (int, float)):
                out[str(key)] = float(val)
    else:
        return out
    out["n_eval"] = float(len(items))
    scored: list[float] = []
    by_task: dict[str, list[float]] = {
        "time_sensitive": [],
        "simple_historical": [],
        "complex_historical": [],
    }
    for item in items:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("prompt_id") or "")
        label = str(item.get("label") or "")
        acc = item.get("original_accuracy")
        if not isinstance(acc, (int, float)):
            acc = item.get("accuracy")
        if not isinstance(acc, (int, float)):
            ev_scores = [
                float(ev["score"])
                for ev in (item.get("evaluations") or [])
                if isinstance(ev, dict) and isinstance(ev.get("score"), (int, float))
            ]
            acc = sum(ev_scores) / len(ev_scores) if ev_scores else None
        if not isinstance(acc, (int, float)):
            continue
        if acc < -1:
            continue
        scored.append(float(acc))
        blob = pid + " " + label
        if "T1" in blob or "Time-Sensitive" in blob or "Time_Sensitive" in blob:
            by_task["time_sensitive"].append(float(acc))
        elif "T2" in blob or "Simple_Historical" in blob:
            by_task["simple_historical"].append(float(acc))
        elif "T3" in blob or "Complex_Historical" in blob:
            by_task["complex_historical"].append(float(acc))
    if scored:
        out["accuracy"] = sum(scored) / len(scored)
        out["n_scored"] = float(len(scored))
    for name, vals in by_task.items():
        if vals:
            out[name] = sum(vals) / len(vals)
    return out


def eval_crash_note(eval_log: Path) -> str:
    if not eval_log.is_file():
        return ""
    text = eval_log.read_text(encoding="utf-8", errors="replace")
    if "KeyError: 'tags'" in text or 'KeyError: "tags"' in text:
        return "KeyError tags in get_judge_user_input (eval.py)"
    if "Traceback (most recent call last):" in text:
        last = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
        return last[-1][:160] if last else "eval.py traceback"
    return ""


def source_n_tags(mod: Path) -> tuple[int, int]:
    rows = load_json(mod / "data" / "finsearchcomp_data.json")
    if not isinstance(rows, list):
        return 0, 0
    n_tags = sum(1 for row in rows if isinstance(row, dict) and "tags" in row)
    return len(rows), n_tags


def harvest_existing_run(repo_root: str | Path = ".") -> SuiteResult:
    """SuiteResult from official chat.py + attempted eval.py (limit=0)."""

    from finagent.harness.grok import DEFAULT_MODEL_API

    root = Path(repo_root).resolve()
    mod = module_path(root)
    artifacts = artifacts_dir(root, "finsearchcomp")
    python = repo_venv_python(root, VENV_NAME)
    model = str(DEFAULT_MODEL_API)
    chat_out = artifacts / "chat.json"
    eval_out = artifacts / "eval.json"
    chat_log = artifacts / "chat.log"
    eval_log = artifacts / "eval.log"
    proto = ProtocolSpec(
        suite_id=SUITE_ID,
        universe=["global", "greater_china"],
        data_vintage="data/finsearchcomp_data.json (635) + akshare split (594)",
        extra={
            "n_questions": N_QUESTIONS,
            "tasks": list(TASKS),
            "questions": "modules/finsearchcomp/data/finsearchcomp_data.json",
            "execute": True,
            "artifacts_dir": str(artifacts),
            "python": python,
            "model": model,
            "harvest": "official_chat_judge_attempt",
        },
    )
    n_chat = count_chat_rows(chat_out)
    n_with_response = count_model_responses(chat_out)
    harvested = harvest_eval(eval_out, chat_out)
    harvested["n_chat"] = float(n_chat)
    harvested["n_total"] = float(N_QUESTIONS)
    harvested["n_questions"] = float(N_QUESTIONS)
    harvested["n_with_response"] = float(n_with_response)
    n_eval = int(harvested.get("n_eval") or 0)
    n_src, n_src_tags = source_n_tags(mod)
    crash = eval_crash_note(eval_log)
    proto.extra["n_chat"] = n_chat
    proto.extra["n_total"] = N_QUESTIONS
    proto.extra["n_eval"] = n_eval
    proto.extra["n_source"] = n_src
    proto.extra["n_source_with_tags"] = n_src_tags
    proto.extra["eval_crash"] = crash
    judge_complete = (
        n_chat >= N_QUESTIONS
        and n_eval >= N_QUESTIONS
        and not crash
        and eval_out.is_file()
    )
    proto.extra["stopped_reason"] = (
        "continue: official chat+eval complete"
        if judge_complete
        else (
            f"official eval.py crashed after n_eval={n_eval}: {crash}"
            if crash
            else "continue: resume/append remaining chat records then official eval.py judge"
        )
    )
    if not judge_complete:
        harvested.pop("accuracy", None)
    status = (
        SuiteStatus.PASS.value
        if judge_complete
        else SuiteStatus.FAIL.value
        if n_chat > 0
        else SuiteStatus.ERROR.value
    )
    eval_metric_names = {"n_eval", "n_scored", "accuracy"}
    metrics = [
        Metric(
            name=k,
            value=v,
            source=str(eval_out) if k in eval_metric_names and eval_out.is_file() else "chat.json",
        )
        for k, v in harvested.items()
        if isinstance(v, (int, float))
    ]
    arts = []
    for kind, path, mt in (
        ("chat_log", chat_log, "text/plain"),
        ("eval_log", eval_log, "text/plain"),
        ("chat_json", chat_out, "application/json"),
        ("eval_json", eval_out, "application/json"),
    ):
        if path.is_file():
            arts.append(Artifact(kind=kind, path=str(path), media_type=mt))
    acc = harvested.get("accuracy")
    acc_txt = f" accuracy={acc:.4f}" if isinstance(acc, float) else " accuracy=n/a (not a 635-question score)"
    if crash:
        judge_txt = (
            f"Judge official eval.py attempted then crashed at item {n_eval + 1}/{N_QUESTIONS}: {crash}. "
            f"eval.json has n_eval={n_eval} judged rows. "
            f"Upstream data/finsearchcomp_data.json n={n_src} with tags={n_src_tags}. "
            "T1 (time-sensitive) path in get_judge_user_input requires data['tags'] for AkShare GT; "
            "eval.py argparse has no skip-T1 / tags flag. Not inventing a custom judge. "
            "Status fail (chat complete; judge incomplete). No fake accuracy. "
        )
    elif eval_out.is_file():
        judge_txt = f"Judge eval.py ran n_eval={n_eval}. "
    else:
        judge_txt = "Judge eval.py not yet (waiting for n_chat=635). "
    notes = (
        f"Official FinSearchComp chat.py --limit 0 (all {N_QUESTIONS}; documented). "
        f"Harvest n_chat={n_chat}/n_total={N_QUESTIONS} "
        f"n_with_response={n_with_response} n_eval={n_eval}{acc_txt} "
        f"model={model}. Live xAI HTTP. "
        + judge_txt
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
        upstream_cli=UPSTREAM_CLI,
    )


def resume_official(repo_root: str | Path = ".") -> int:
    """Resume official chat.py (limit=0) then eval.py judge."""

    from finagent.harness.grok import DEFAULT_MODEL_API, refresh_xai_api_key

    root = Path(repo_root).resolve()
    refresh_xai_api_key(force=True)
    apply_continue_patches(root)
    python = repo_venv_python(root, VENV_NAME)
    mod = module_path(root)
    inner = mod / "finsearchcomp"
    artifacts = artifacts_dir(root, "finsearchcomp")
    chat_out = artifacts / "chat.json"
    eval_out = artifacts / "eval.json"
    chat_log = artifacts / "chat.log"
    eval_log = artifacts / "eval.log"
    bak = artifacts / "chat.json.bak_continue"
    if chat_out.is_file() and not bak.is_file():
        shutil.copy2(chat_out, bak)
        print(f"[finsearch] backed up {chat_out} -> {bak} n={count_chat_rows(chat_out)}", flush=True)
    env = xai_env(pythonpath_dirs=[inner, mod, root])
    data_file = mod / "data" / "finsearchcomp_data.json"
    n_before = count_chat_rows(chat_out)
    print(f"[finsearch] starting chat.py resume n_chat={n_before}/{N_QUESTIONS}", flush=True)
    chat_cmd = [
        python,
        str(inner / "chat" / "chat.py"),
        "--model_name",
        DEFAULT_MODEL_API,
        "--input_file",
        str(data_file),
        "--output_path",
        str(chat_out),
        "--limit",
        "0",
    ]
    proc = run_logged(chat_cmd, cwd=inner, env=env, log_path=chat_log, append=True)
    n_after = count_chat_rows(chat_out)
    print(f"[finsearch] chat.py rc={proc.returncode} n_chat={n_after}/{N_QUESTIONS}", flush=True)
    if n_after <= 0:
        return proc.returncode or 1
    eval_cmd = [
        python,
        str(inner / "eval" / "eval.py"),
        "--model_name",
        DEFAULT_MODEL_API,
        "--input",
        str(chat_out),
        "--output",
        str(eval_out),
    ]
    print(f"[finsearch] starting eval.py judge n_chat={n_after}", flush=True)
    proc_eval = run_logged(eval_cmd, cwd=inner, env=env, log_path=eval_log, append=True)
    print(f"[finsearch] eval.py rc={proc_eval.returncode} eval_exists={eval_out.is_file()}", flush=True)
    print(f"[finsearch] n_eval={json_list_len(eval_out)}", flush=True)
    if proc.returncode != 0:
        return proc.returncode
    return int(proc_eval.returncode)
