"""McpPlugin — FinMCP first consumer: plugin_env only, empty mcp_servers.

Qieman URL is copied into PluginMount.env for sandbox.exec_sync.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from finagent.plugins.base import EnvPlugin, PluginMount

if TYPE_CHECKING:
    from finagent.provider.base import BaseSandbox


class McpPlugin(EnvPlugin):
    @staticmethod
    def name() -> str:
        return "mcp"

    def describe(self) -> dict:
        return {
            "name": "mcp",
            "kind": "plugin_env",
            "consumer": "finmcp.tool_mcp",
            "mcp_servers": False,
        }

    async def mount(self, sandbox: BaseSandbox) -> PluginMount:
        del sandbox
        env: dict[str, str] = {}
        url = (
            os.environ.get("QIEMAN_MCP_SERVER_URL")
            or os.environ.get("MCP_SERVER_URL")
            or ""
        ).strip()
        schema = (
            os.environ.get("QIEMAN_MCP_SCHEMA")
            or os.environ.get("MCP_SCHEMA_PATH")
            or ""
        ).strip()
        if url:
            env["QIEMAN_MCP_SERVER_URL"] = url
            env["MCP_SERVER_URL"] = url
        if schema:
            env["QIEMAN_MCP_SCHEMA"] = schema
            env["MCP_SCHEMA_PATH"] = schema
        return PluginMount(
            mcp_servers=[],
            env=env,
            notes="FinMCP plugin_env only; no harness-native MCP",
        )
