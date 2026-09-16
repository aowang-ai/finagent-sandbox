"""Phase D: LocalProcessSandbox start → exec_sync → stop; session HOME overlay."""

from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

from finagent.provider.factory import SandboxFactory
from finagent.provider.local_process import LocalProcessSandbox


class LocalProcessSandboxTests(unittest.TestCase):
    def test_factory_map_is_local_process_only(self) -> None:
        self.assertEqual(list(SandboxFactory._MAP), ["local-process"])
        self.assertNotIn("mcp", SandboxFactory._MAP)
        self.assertNotIn("yahoo", SandboxFactory._MAP)
        with self.assertRaises(ValueError) as ctx:
            SandboxFactory.create("docker")
        self.assertIn("local-process", str(ctx.exception))

    def test_round_trip_echo_and_session_home(self) -> None:
        async def _run() -> None:
            with tempfile.TemporaryDirectory() as tmp:
                sb = LocalProcessSandbox(
                    python=Path(sys.executable),
                    session_id="unit-echo",
                    artifacts_dir=tmp,
                )
                await sb.start()
                try:
                    self.assertTrue(sb.session_home.exists())
                    self.assertEqual(sb.session_home, Path(tmp) / "unit-echo" / "home")
                    result = sb.exec_sync(["echo", "ok"])
                    self.assertEqual(result.return_code, 0)
                    self.assertEqual((result.stdout or "").strip(), "ok")
                    home = sb.exec_sync(
                        [sys.executable, "-c", "import os; print(os.environ['HOME'])"]
                    )
                    self.assertEqual(home.return_code, 0)
                    self.assertEqual((home.stdout or "").strip(), str(sb.session_home))
                finally:
                    home_path = sb.session_home
                    await sb.stop(delete=True)
                    self.assertFalse(home_path.exists())

        asyncio.run(_run())

    def test_python_kwarg_is_stored_not_argv0(self) -> None:
        sb = LocalProcessSandbox(python=Path("/tmp/venvs/v2_finsearch/bin/python"))
        self.assertEqual(sb.python, Path("/tmp/venvs/v2_finsearch/bin/python"))


if __name__ == "__main__":
    unittest.main()
