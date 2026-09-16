"""PluginFactory — finance env plugins (not sandbox providers).

Phase E: McpPlugin is the first registered plugin. Yahoo stays adapters/ama/yahoo.py.
"""

from __future__ import annotations

import importlib

from finagent.plugins.base import EnvPlugin


def _load_symbol(path: str) -> type:
    module_name, sep, attr = path.partition(":")
    if not sep or not attr:
        raise ValueError(f"import path must be 'module:Class', got {path!r}")
    module = importlib.import_module(module_name)
    return getattr(module, attr)


class PluginFactory:
    _MAP: dict[str, str] = {
        "mcp": "finagent.plugins.mcp:McpPlugin",
    }

    @classmethod
    def create(cls, name: str, **kwargs: object) -> EnvPlugin:
        if name not in cls._MAP:
            raise ValueError(f"unknown plugin {name!r}; known: {sorted(cls._MAP)}")
        klass = _load_symbol(cls._MAP[name])
        return klass(**kwargs)
