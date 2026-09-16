"""HarnessFactory — Harbor AgentFactory analogue.

Phase B: create("grok-cli") returns GrokCliHarness. Unknown names raise
ValueError listing keys. Import-path escape: name containing ':' is loaded
directly (Harbor create_agent_from_config).
"""

from __future__ import annotations

import importlib

from finagent.harness.base import BaseHarness


def _load_symbol(path: str) -> type:
    module_name, sep, attr = path.partition(":")
    if not sep or not attr:
        raise ValueError(f"import path must be 'module:Class', got {path!r}")
    module = importlib.import_module(module_name)
    return getattr(module, attr)


class HarnessFactory:
    _MAP: dict[str, str] = {
        "grok-cli": "finagent.harness.grok_cli:GrokCliHarness",
    }

    @classmethod
    def create(
        cls,
        name: str | None = None,
        *,
        import_path: str | None = None,
        **kwargs: object,
    ) -> BaseHarness:
        path = import_path
        if path is None:
            if name is None:
                raise ValueError("harness name or import_path required")
            if ":" in name and name not in cls._MAP:
                path = name
            elif name not in cls._MAP:
                raise ValueError(f"unknown harness {name!r}; known: {sorted(cls._MAP)}")
            else:
                path = cls._MAP[name]
        klass = _load_symbol(path)
        return klass(**kwargs)
