"""FinAgentSandbox — Harbor-style harness / bench / plugin registries.

Product name: FinAgentSandbox. Git path: aowang-ai/finagent-sandbox.
Phase D adds LocalProcessSandbox + thin Trial.
PluginFactory registers McpPlugin (FinMCP plugin_env).
"""

from sandbox.benches.factory import BenchFactory
from sandbox.harness.factory import HarnessFactory
from sandbox.plugins.factory import PluginFactory

__all__ = ["BenchFactory", "HarnessFactory", "PluginFactory"]
