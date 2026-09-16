"""Sandbox providers (Harbor EnvironmentFactory analogue).

Isolation (local-process session HOME), not a market-data or MCP plugin —
those go in PluginFactory. Do not put Yahoo or MCP in SandboxFactory.
"""

from sandbox.provider.base import BaseSandbox, ExecResult
from sandbox.provider.factory import SandboxFactory
from sandbox.provider.local_process import LocalProcessSandbox

__all__ = ["BaseSandbox", "ExecResult", "LocalProcessSandbox", "SandboxFactory"]
