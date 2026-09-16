"""Sandbox providers (Harbor EnvironmentFactory analogue).

Isolation (local-process session HOME), not a market-data or MCP plugin —
those go in PluginFactory. Do not put Yahoo or MCP in SandboxFactory.
"""

from finagent.provider.base import BaseSandbox, ExecResult
from finagent.provider.factory import SandboxFactory
from finagent.provider.local_process import LocalProcessSandbox

__all__ = ["BaseSandbox", "ExecResult", "LocalProcessSandbox", "SandboxFactory"]
