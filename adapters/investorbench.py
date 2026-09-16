"""InvestorBench — cross-asset (stock / crypto / ETF) decision exam room.

Upstream: https://github.com/felis33/INVESTOR-BENCH  ·  arXiv:2412.18174  ·  ACL 2025

Official surface: docker `devon warmup|test|eval` wrapping `python run.py`.
Full protocol needs vLLM + Qdrant + OpenAI embeddings. Never fake pass metrics.
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
from .v2_runtime import execute_or_skip, port_open, skip_message, which

SUITE_ID = "investorbench.decision"
MODULE_REL = "modules/investorbench"
UPSTREAM_CLI = (
    "docker run -it -v .:/workspace --network host devon warmup && "
    "docker run -it -v .:/workspace --network host devon test && "
    "docker run -it -v .:/workspace --network host devon eval"
)
DEFAULT_UNIVERSE = ["HON", "JNJ", "MSFT", "NFLX", "UVV", "BTC-USD", "ETH-USD"]
DEFAULT_FROM = "2020-10-01"
DEFAULT_TO = "2021-05-06"


class InvestorBenchEnvAdapter:
    suite_id = SUITE_ID
    module_dir = MODULE_REL

    def __init__(self, repo_root: str | Path = ".") -> None:
        self.repo_root = Path(repo_root).resolve()
        self.module_path = self.repo_root / MODULE_REL

    def describe(self) -> Mapping[str, Any]:
        return {
            "suite_id": SUITE_ID,
            "role": "exam_room",
            "layer": "environment.decision_trading",
            "task_suite": "cross_asset_single_name",
            "tier": "optional",
            "required_for_promote": False,
            "module": str(self.module_path),
            "entry": "python run.py warmup|test|eval (docker devon)",
            "artifacts": "results/<run_name>/<chat_model>/<trading_symbols>/metrics",
            "metrics": ["cumulative_return", "sharpe_ratio"],
            "pitfalls": [
                "Needs vLLM server, Qdrant, OPENAI_API_KEY embeddings, optional GuardRails",
                "ETF window is documented in README but no ETF json ships in data/",
                "Official CLI is docker devon warmup|test|eval — no smaller documented smoke",
            ],
            "wired": True,
        }

    def run(self, agent: AgentAdapter, protocol: ProtocolSpec) -> SuiteResult:
        _ = agent
        proto = ProtocolSpec(
            suite_id=SUITE_ID,
            date_from=protocol.date_from or DEFAULT_FROM,
            date_to=protocol.date_to or DEFAULT_TO,
            universe=list(protocol.universe or DEFAULT_UNIVERSE),
            data_vintage=protocol.data_vintage or "investorbench data/{hon,jnj,msft,nflx,uvv,btc,eth}.json",
            extra=dict(protocol.extra),
        )
        proto.extra.setdefault("warmup_from", "2020-07-01")
        proto.extra.setdefault("warmup_to", "2020-09-30")
        proto.extra.setdefault("assets", "equities+crypto")
        skipped = execute_or_skip(
            suite_id=SUITE_ID,
            protocol=proto,
            upstream_cli=UPSTREAM_CLI,
            blockers=_runtime_blockers(self.module_path),
            skip_notes=_skip_notes(self.module_path, dry=True),
        )
        return skipped or skipped_suite(
            SUITE_ID,
            protocol=proto,
            upstream_cli=UPSTREAM_CLI,
            notes="skip: " + "; ".join(_runtime_blockers(self.module_path)),
        )


def _runtime_blockers(module_path: Path) -> list[str]:
    blockers: list[str] = []
    if not module_path.is_dir():
        blockers.append("modules/investorbench missing (run scripts/clone_modules.sh)")
    if not (module_path / "run.py").is_file():
        blockers.append("run.py missing")
    docker = which("docker")
    if docker is None:
        blockers.append("docker binary not available (official CLI is `docker run … devon warmup|test|eval`)")
    if not port_open("127.0.0.1", 8000):
        blockers.append("vLLM server not listening on 127.0.0.1:8000 (chat_vllm_endpoint)")
    if not port_open("127.0.0.1", 6333):
        blockers.append("Qdrant not listening on 127.0.0.1:6333 (vector memory)")
    blockers.append(
        "official protocol also needs OPENAI embeddings model text-embedding-3-large "
        "(not an xAI model) plus a compiled configs/main.json from Pkl; "
        "no smaller official smoke is documented beyond warmup|test|eval. "
        "Not inventing a non-docker protocol."
    )
    return blockers


def _skip_notes(module_path: Path, *, dry: bool) -> str:
    return skip_message(_runtime_blockers(module_path), dry=dry)


def _assert_protocol() -> None:
    _: EnvAdapter = InvestorBenchEnvAdapter()  # type: ignore[assignment]


__all__ = ["SUITE_ID", "InvestorBenchEnvAdapter"]
