"""Phase E: PluginFactory + McpPlugin plugin_env; FinMCP exec_sync opt-in."""

from __future__ import annotations

import ast
import asyncio
import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adapters.base import Decision, Observation, ProtocolSpec
from sandbox.benches.factory import BenchFactory
from sandbox.benches.wrap import EnvAdapterAsBench, FinMcpEnvAdapterAsBench
from sandbox.plugins.factory import PluginFactory
from sandbox.plugins.mcp import McpPlugin
from sandbox.provider.base import ExecResult
from sandbox.runtime.config import TrialConfig
from sandbox.runtime.trial import Trial

ROOT = Path(__file__).resolve().parents[2]
MCP_PY = ROOT / "sandbox" / "plugins" / "mcp.py"
FINMCP_TIR = ROOT / "modules" / "finmcp" / "DianJin-TIR"
FINMCP_BENCH = FINMCP_TIR / "Benchmark" / "benchmark_final.json"


class DummyHarness:
    def as_agent_adapter(self):
        class _Adapter:
            agent_id = "dummy"

            def capabilities(self) -> set[str]:
                return set()

            def decide(self, observation: Observation) -> Decision:
                raise AssertionError(f"decide() must not run for FinMCP; {observation}")

        return _Adapter()


class RecordingSandbox:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.session_home = Path("/tmp")

    def exec_sync(self, argv, *, cwd=None, env=None, timeout_sec=None):
        self.calls.append({"argv": list(argv), "cwd": cwd, "env": dict(env or {})})
        return ExecResult(stdout="", stderr="", return_code=0)


class PluginFactoryTests(unittest.TestCase):
    def test_map_registers_mcp_only(self) -> None:
        self.assertEqual(list(PluginFactory._MAP), ["mcp"])
        self.assertEqual(PluginFactory._MAP["mcp"], "sandbox.plugins.mcp:McpPlugin")
        plugin = PluginFactory.create("mcp")
        self.assertIsInstance(plugin, McpPlugin)
        self.assertEqual(plugin.name(), "mcp")

    def test_unknown_plugin_lists_mcp(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            PluginFactory.create("yahoo")
        self.assertIn("mcp", str(ctx.exception))

    def test_mcp_source_has_no_harness_or_config_toml(self) -> None:
        src = MCP_PY.read_text(encoding="utf-8")
        tree = ast.parse(src)
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
            elif isinstance(node, ast.Import):
                imported.extend(a.name for a in node.names)
        self.assertFalse(any("harness" in m for m in imported), imported)
        self.assertFalse(any("sandbox.harness" in m for m in imported), imported)
        writes = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr in {"write_text", "write_bytes"}]
        self.assertEqual(writes, [])
        sig = inspect.signature(McpPlugin.mount)
        self.assertNotIn("harness", sig.parameters)

    def test_mount_returns_empty_mcp_servers_and_plugin_env(self) -> None:
        plugin = McpPlugin()

        async def _run() -> None:
            with patch.dict(
                "os.environ",
                {"QIEMAN_MCP_SERVER_URL": "http://127.0.0.1:9/mcp", "MCP_SCHEMA_PATH": "/tmp/schema.json"},
                clear=False,
            ):
                mount = await plugin.mount(RecordingSandbox())  # type: ignore[arg-type]
            self.assertEqual(mount.mcp_servers, [])
            self.assertEqual(mount.env.get("MCP_SERVER_URL"), "http://127.0.0.1:9/mcp")
            self.assertEqual(mount.env.get("MCP_SCHEMA_PATH"), "/tmp/schema.json")

        asyncio.run(_run())


class FinMcpWrapTests(unittest.TestCase):
    def test_factory_returns_finmcp_wrap(self) -> None:
        bench = BenchFactory.create("finmcp.tool_mcp", repo_root=ROOT)
        self.assertIsInstance(bench, FinMcpEnvAdapterAsBench)
        self.assertTrue(bench.opt_in_sandbox)
        self.assertEqual(bench.default_plugins, ("mcp",))
        self.assertEqual(bench.suite_id, "finmcp.tool_mcp")
        other = BenchFactory.create("stockbench.daily_sim", repo_root=ROOT)
        self.assertIsInstance(other, EnvAdapterAsBench)
        self.assertFalse(other.opt_in_sandbox)

    def test_skip_without_qieman_url_does_not_exec_sync(self) -> None:
        bench = BenchFactory.create("finmcp.tool_mcp", repo_root=ROOT)
        fake = RecordingSandbox()
        proto = ProtocolSpec(
            suite_id="finmcp.tool_mcp",
            extra={"execute": True, "python": str(ROOT / "venvs" / "v2_finmcp" / "bin" / "python")},
        )
        with patch.dict("os.environ", {"QIEMAN_MCP_SERVER_URL": "", "MCP_SERVER_URL": ""}, clear=False):
            result = bench.run_official(DummyHarness(), proto, sandbox=fake)
        self.assertEqual(result.status, "skip")
        self.assertEqual(fake.calls, [])

    @unittest.skipUnless(
        FINMCP_TIR.is_dir() and FINMCP_BENCH.is_file(),
        "FinMCP official bench JSON not present (HF DianJin/FinMCP-Bench; clone is not enough)",
    )
    def test_run_official_invokes_exec_sync_when_configured(self) -> None:
        bench = BenchFactory.create("finmcp.tool_mcp", repo_root=ROOT)
        fake = RecordingSandbox()
        with tempfile.TemporaryDirectory() as tmp:
            schema = Path(tmp) / "schema.json"
            schema.write_text("{}", encoding="utf-8")
            proto = ProtocolSpec(
                suite_id="finmcp.tool_mcp",
                extra={
                    "execute": True,
                    "python": str(ROOT / "venvs" / "v2_finmcp" / "bin" / "python"),
                    "artifacts_dir": tmp,
                    "plugin_env": {
                        "QIEMAN_MCP_SERVER_URL": "http://127.0.0.1:9/mcp",
                        "MCP_SCHEMA_PATH": str(schema),
                    },
                },
            )
            with patch("runners.grok.refresh_xai_api_key", return_value="test-key"):
                result = bench.run_official(DummyHarness(), proto, sandbox=fake)
        self.assertTrue(fake.calls, msg=f"exec_sync not called; status={result.status} notes={result.notes}")
        joined = " ".join(" ".join(c["argv"]) for c in fake.calls)
        self.assertIn("inference_api.py", joined)
        self.assertIn("v2_finmcp", fake.calls[0]["argv"][0])

    def test_trial_plugin_env_and_sandbox_python(self) -> None:
        py = str(ROOT / "venvs" / "v2_finmcp" / "bin" / "python")
        cfg = TrialConfig(
            harness="grok-cli",
            suite_id="finmcp.tool_mcp",
            execute=False,
            python=py,
            plugins=["mcp"],
            artifacts_dir=str(ROOT / "artifacts" / "finmcp"),
        )
        trial = Trial(cfg, repo_root=ROOT)
        self.assertEqual(str(trial.sandbox.python), py)
        self.assertEqual(trial.protocol.extra["python"], py)
        self.assertEqual(trial.protocol.extra["plugins"], ["mcp"])
        result = asyncio.run(trial.run())
        self.assertEqual(result.status, "skip")
        self.assertIn("plugin_env", trial.protocol.extra)
        # Grok API still sits (no skip on features().mcp_servers)
        self.assertNotIn("features().mcp_servers", result.notes or "")


if __name__ == "__main__":
    unittest.main()
