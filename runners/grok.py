"""Grok CLI runner under test.

Invokes local `grok` (CLI backend) or the xAI HTTP API with the same locked
prompts (API backend). Grok CLI `-p` carries a ~15k-token agent system prompt
even with `--system-prompt-override`, so overnight volume defaults to the API
with identical decision schemas. Set GROK_EVAL_BACKEND=cli to force the binary.

On HTTP 403, refresh XAI_API_KEY from ~/.grok/auth.json (nested `key` field).
"""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from adapters.base import AgentAdapter, Decision, Observation

DEFAULT_MODEL_API = os.environ.get("GROK_EVAL_MODEL", "grok-4.20-0309-non-reasoning")
DEFAULT_MODEL_CLI = os.environ.get("GROK_EVAL_CLI_MODEL", "grok-4.6")
XAI_CHAT_URL = os.environ.get("XAI_API_BASE_URL", "https://api.x.ai/v1") + "/chat/completions"
AUTH_JSON = Path(os.environ.get("GROK_AUTH_JSON", str(Path.home() / ".grok" / "auth.json")))
AUTH_LOCK = AUTH_JSON.with_name(AUTH_JSON.name + ".lock")
OIDC_TOKEN_URL = os.environ.get("XAI_OIDC_TOKEN_URL", "https://auth.x.ai/oauth2/token")
OIDC_MIN_TTL_SEC = int(os.environ.get("XAI_OIDC_MIN_TTL_SEC") or "900")

LOCKED_SYSTEM = (
    "You are the Grok CLI finance-agent harness under evaluation. "
    "Follow the user JSON schema exactly. Do not call tools unless the prompt "
    "lists a tool manifest. Prefer HOLD when evidence is thin. Never invent "
    "fill prices or look-ahead data. Output JSON only."
)

DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "action": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
        "reasoning": {"type": "string"},
        "allocations": {
            "type": "object",
            "additionalProperties": {"type": "number"},
        },
        "tool_calls": {
            "type": "array",
            "items": {"type": "object"},
        },
    },
    "required": ["action", "reasoning"],
}

STOCKBENCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "decisions": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["increase", "decrease", "hold", "close"],
                    },
                    "target_cash_amount": {"type": "number"},
                    "reasons": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number"},
                },
                "required": ["action", "target_cash_amount"],
            },
        },
        "reasoning": {"type": "string"},
    },
    "required": ["decisions", "reasoning"],
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _auth_record(blob: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    if isinstance(blob.get("key"), str) and blob.get("key"):
        return None, blob
    for name, value in blob.items():
        if isinstance(value, dict) and isinstance(value.get("key"), str) and value.get("key"):
            return str(name), value
    return None, {}


def _parse_expires_at(raw: Any) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _ttl_seconds(rec: dict[str, Any]) -> float | None:
    exp = _parse_expires_at(rec.get("expires_at"))
    if exp is None:
        return None
    return (exp - datetime.now(timezone.utc)).total_seconds()


def _install_api_key(key: str) -> str:
    os.environ["XAI_API_KEY"] = key
    os.environ["OPENAI_API_KEY"] = key
    return key


def _oidc_refresh_locked(blob: dict[str, Any], rec_name: str | None, rec: dict[str, Any]) -> str:
    """Refresh the OIDC access token. Caller holds AUTH_LOCK."""

    refresh_token = rec.get("refresh_token")
    client_id = rec.get("oidc_client_id") or rec.get("client_id")
    if not isinstance(refresh_token, str) or not refresh_token:
        key = rec.get("key")
        return key if isinstance(key, str) else ""
    if not isinstance(client_id, str) or not client_id:
        key = rec.get("key")
        return key if isinstance(key, str) else ""
    body = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        OIDC_TOKEN_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    access = payload.get("access_token")
    if not isinstance(access, str) or not access:
        key = rec.get("key")
        return key if isinstance(key, str) else ""
    rec["key"] = access
    if isinstance(payload.get("refresh_token"), str) and payload["refresh_token"]:
        rec["refresh_token"] = payload["refresh_token"]
    expires_in = payload.get("expires_in")
    try:
        ttl = int(expires_in) if expires_in is not None else 21600
    except (TypeError, ValueError):
        ttl = 21600
    rec["expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=ttl)).isoformat().replace(
        "+00:00", "Z"
    )
    if rec_name is None:
        blob.update(rec)
    else:
        blob[rec_name] = rec
    AUTH_JSON.parent.mkdir(parents=True, exist_ok=True)
    AUTH_JSON.write_text(json.dumps(blob, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(AUTH_JSON, 0o600)
    except OSError:
        pass
    return access


def refresh_xai_api_key(*, force: bool = False, min_ttl_sec: int | None = None) -> str:
    """Load XAI_API_KEY from ~/.grok/auth.json and OIDC-refresh when near expiry.

    Always overwrites XAI_API_KEY and OPENAI_API_KEY so rotated JWTs propagate
    into long-running suite processes that re-read this helper.
    """

    ttl_need = OIDC_MIN_TTL_SEC if min_ttl_sec is None else min_ttl_sec
    current = os.environ.get("XAI_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    if not AUTH_JSON.is_file():
        return current

    AUTH_LOCK.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_f = AUTH_LOCK.open("a+", encoding="utf-8")
    except OSError:
        lock_f = None
    try:
        if lock_f is not None:
            try:
                fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
            except OSError:
                pass
        try:
            blob = json.loads(AUTH_JSON.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return current
        rec_name, rec = _auth_record(blob if isinstance(blob, dict) else {})
        disk_key = rec.get("key") if isinstance(rec.get("key"), str) else ""
        ttl = _ttl_seconds(rec) if rec else None
        need_oidc = force or ttl is None or ttl < ttl_need
        key = disk_key
        if need_oidc and rec.get("refresh_token"):
            try:
                key = _oidc_refresh_locked(blob, rec_name, rec) or disk_key
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError):
                key = disk_key
        if isinstance(key, str) and key:
            return _install_api_key(key)
        return current
    finally:
        if lock_f is not None:
            try:
                fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            lock_f.close()


def _canonical_hash(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class GrokCompletion:
    text: str
    parsed: dict[str, Any] | None
    backend: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    cached: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


class GrokRunner:
    """stdin/file in → structured JSON out, with trajectory logging."""

    def __init__(
        self,
        *,
        backend: str | None = None,
        model: str | None = None,
        artifacts_dir: str | Path | None = None,
        timeout_sec: int = 180,
    ) -> None:
        self.backend = (backend or os.environ.get("GROK_EVAL_BACKEND") or "api").lower()
        self.model = model or (
            DEFAULT_MODEL_CLI if self.backend == "cli" else DEFAULT_MODEL_API
        )
        root = Path(artifacts_dir or os.environ.get("GROK_EVAL_ARTIFACTS") or "artifacts/grok_cli")
        self.artifacts_dir = root
        self.cache_dir = root / "cache"
        self.traj_path = root / "trajectories.jsonl"
        self.timeout_sec = timeout_sec
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.traj_path.parent.mkdir(parents=True, exist_ok=True)
        refresh_xai_api_key()

    def complete_json(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | None = None,
        system: str | None = None,
        cache_key: str | None = None,
    ) -> GrokCompletion:
        schema = schema or DECISION_SCHEMA
        system = system or LOCKED_SYSTEM
        key_payload = {
            "backend": self.backend,
            "model": self.model,
            "system": system,
            "prompt": prompt,
            "schema": schema,
        }
        key = cache_key or _canonical_hash(key_payload)
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.is_file():
            try:
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
                completion = GrokCompletion(
                    text=cached.get("text") or "",
                    parsed=cached.get("parsed"),
                    backend=cached.get("backend") or self.backend,
                    model=cached.get("model") or self.model,
                    usage=cached.get("usage") or {},
                    cached=True,
                    raw=cached.get("raw") or {},
                )
                self._log_traj(prompt, completion, cached=True)
                return completion
            except (OSError, json.JSONDecodeError):
                pass

        if self.backend == "cli":
            completion = self._complete_cli(prompt, schema=schema, system=system)
        else:
            completion = self._complete_api(prompt, schema=schema, system=system)

        try:
            cache_file.write_text(
                json.dumps(
                    {
                        "text": completion.text,
                        "parsed": completion.parsed,
                        "backend": completion.backend,
                        "model": completion.model,
                        "usage": completion.usage,
                        "raw": completion.raw,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass
        self._log_traj(prompt, completion, cached=False)
        return completion

    def _log_traj(self, prompt: str, completion: GrokCompletion, *, cached: bool) -> None:
        rec = {
            "ts": _utc_now(),
            "backend": completion.backend,
            "model": completion.model,
            "cached": cached,
            "prompt_sha256": sha256(prompt.encode("utf-8")).hexdigest(),
            "prompt_chars": len(prompt),
            "parsed": completion.parsed,
            "usage": completion.usage,
        }
        try:
            with self.traj_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _complete_cli(
        self,
        prompt: str,
        *,
        schema: dict[str, Any],
        system: str,
    ) -> GrokCompletion:
        grok_bin = os.environ.get("GROK_BIN", "grok")
        cmd = [
            grok_bin,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(schema, separators=(",", ":")),
            "--system-prompt-override",
            system,
            "--no-plan",
            "--no-subagents",
            "--max-turns",
            "1",
            "--verbatim",
            "-m",
            self.model,
        ]
        env = os.environ.copy()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
                env=env,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return GrokCompletion(
                text="",
                parsed=None,
                backend="cli",
                model=self.model,
                raw={"error": str(exc)},
            )
        parsed_out, text = _parse_cli_json(proc.stdout)
        return GrokCompletion(
            text=text,
            parsed=parsed_out,
            backend="cli",
            model=self.model,
            usage=(parsed_out or {}).get("usage") if isinstance(parsed_out, dict) else {},
            raw={"returncode": proc.returncode, "stderr_tail": (proc.stderr or "")[-2000:]},
        )

    def _complete_api(
        self,
        prompt: str,
        *,
        schema: dict[str, Any],
        system: str,
        retried_auth: bool = False,
        retried_schema: bool = False,
    ) -> GrokCompletion:
        last_err = ""
        for attempt in range(6):
            key = refresh_xai_api_key(force=attempt > 0 and not retried_auth)
            body = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.0,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "harness_decision",
                        "strict": True,
                        "schema": schema,
                    },
                },
            }
            data = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(
                XAI_CHAT_URL,
                data=data,
                method="POST",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                err_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
                last_err = f"http {exc.code}: {err_body[:500]}"
                if exc.code == 403 and not retried_auth:
                    refresh_xai_api_key(force=True)
                    retried_auth = True
                    time.sleep(1)
                    continue
                if exc.code in {400, 422} and "json_schema" in err_body.lower() and not retried_schema:
                    return self._complete_api_json_object(prompt, schema=schema, system=system)
                if exc.code == 429:
                    time.sleep(min(60.0, 2.0 ** attempt))
                    continue
                if exc.code in {500, 502, 503, 504}:
                    time.sleep(min(30.0, 1.5 ** attempt))
                    continue
                return GrokCompletion(
                    text="",
                    parsed=None,
                    backend="api",
                    model=self.model,
                    raw={"http": exc.code, "body": err_body[:2000]},
                )
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
                last_err = str(exc)
                time.sleep(min(20.0, 1.5 ** attempt))
                continue
            text = ""
            try:
                text = payload["choices"][0]["message"]["content"] or ""
            except (KeyError, IndexError, TypeError):
                text = ""
            parsed = _loads_json_maybe(text)
            return GrokCompletion(
                text=text,
                parsed=parsed if isinstance(parsed, dict) else None,
                backend="api",
                model=self.model,
                usage=payload.get("usage") or {},
                raw={"id": payload.get("id")},
            )
        return GrokCompletion(
            text="",
            parsed=None,
            backend="api",
            model=self.model,
            raw={"error": last_err or "retries exhausted"},
        )

    def _complete_api_json_object(
        self,
        prompt: str,
        *,
        schema: dict[str, Any],
        system: str,
    ) -> GrokCompletion:
        key = refresh_xai_api_key(force=True)
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": prompt + "\n\nRespond with JSON matching this schema:\n"
                    + json.dumps(schema),
                },
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }
        req = urllib.request.Request(
            XAI_CHAT_URL,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            text = payload["choices"][0]["message"]["content"] or ""
        except Exception as exc:  # noqa: BLE001 — runner must fail closed
            return GrokCompletion(
                text="",
                parsed=None,
                backend="api",
                model=self.model,
                raw={"error": str(exc)},
            )
        parsed = _loads_json_maybe(text)
        return GrokCompletion(
            text=text,
            parsed=parsed if isinstance(parsed, dict) else None,
            backend="api",
            model=self.model,
            usage=payload.get("usage") or {},
            raw={"fallback": "json_object"},
        )


def _parse_cli_json(stdout: str) -> tuple[dict[str, Any] | None, str]:
    text = (stdout or "").strip()
    if not text:
        return None, ""
    # grok --output-format json may wrap with metadata; prefer last JSON object.
    parsed = _loads_json_maybe(text)
    if isinstance(parsed, dict):
        structured = parsed.get("structuredOutput")
        if isinstance(structured, dict):
            return structured, json.dumps(structured)
        if "action" in parsed or "decisions" in parsed or "tool_calls" in parsed:
            return parsed, text
        inner = parsed.get("text")
        if isinstance(inner, str):
            inner_p = _loads_json_maybe(inner)
            if isinstance(inner_p, dict):
                return inner_p, inner
        return parsed, text
    # Scan for a JSON object in mixed output.
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        chunk = text[start : end + 1]
        parsed2 = _loads_json_maybe(chunk)
        if isinstance(parsed2, dict):
            structured = parsed2.get("structuredOutput")
            if isinstance(structured, dict):
                return structured, json.dumps(structured)
            return parsed2, chunk
    return None, text


def _loads_json_maybe(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
        return None


def observation_prompt(obs: Observation) -> str:
    raw = obs.raw or {}
    payload = {
        "as_of": obs.as_of,
        "symbols": obs.symbols,
        "prices": obs.prices,
        "history_price": _clip(raw.get("history_price") or raw.get("history") or {}, 4000),
        "news": _clip(obs.news, 4000),
        "filings": _clip(obs.filings, 3000),
        "portfolio": obs.portfolio,
        "query": obs.query,
        "tools": obs.tools[:40] if obs.tools else [],
    }
    return (
        "Decide a trading action for this observation.\n"
        "Use prices and history_price (oldest→newest closes) as the tape. "
        "News may be empty; that is not by itself a reason to HOLD if the tape is informative.\n"
        "action ∈ {BUY, SELL, HOLD}. BUY = open/add long, SELL = open/add short "
        "or flatten long, HOLD = stay flat / no new risk.\n"
        + json.dumps(payload, ensure_ascii=False, default=str)
    )


def _clip(value: Any, limit: int) -> Any:
    if isinstance(value, str):
        return value[:limit]
    if isinstance(value, dict):
        return {str(k): _clip(v, max(200, limit // max(1, len(value)))) for k, v in list(value.items())[:20]}
    if isinstance(value, list):
        return [_clip(v, limit) for v in value[:10]]
    return value


class GrokCliAgentAdapter:
    """AgentAdapter backed by the Grok CLI runner (API or grok binary)."""

    agent_id = "grok-cli"

    def __init__(self, runner: GrokRunner | None = None) -> None:
        self.runner = runner or GrokRunner()

    def capabilities(self) -> set[str]:
        return {
            "ama.multi_market_live",
            "finsaber.long_horizon",
            "stockbench.daily_sim",
            "fintoolbench.tool_compliance",
            "deepfund.fund_arena",
        }

    def decide(self, observation: Observation) -> Decision:
        completion = self.runner.complete_json(
            observation_prompt(observation),
            schema=DECISION_SCHEMA,
            system=LOCKED_SYSTEM,
        )
        parsed = completion.parsed or {}
        action = str(parsed.get("action") or "HOLD").upper()
        if action not in {"BUY", "SELL", "HOLD"}:
            action = "HOLD"
        allocations = parsed.get("allocations") if isinstance(parsed.get("allocations"), dict) else {}
        tool_calls = parsed.get("tool_calls") if isinstance(parsed.get("tool_calls"), list) else []
        reasoning = str(parsed.get("reasoning") or "")
        if not reasoning and not completion.parsed:
            reasoning = "runner produced no structured decision; fail closed to HOLD"
        return Decision(
            action=action,
            symbols=list(observation.symbols),
            reasoning=reasoning,
            allocations={str(k): float(v) for k, v in allocations.items() if _is_number(v)},
            tool_calls=tool_calls,
            raw={
                "backend": completion.backend,
                "model": completion.model,
                "cached": completion.cached,
                "usage": completion.usage,
            },
        )


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
