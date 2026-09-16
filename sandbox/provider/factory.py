"""SandboxFactory — provider registry (not a plugin).

Yahoo harvest and MCP do not belong here.
"""

from __future__ import annotations

import importlib

from sandbox.provider.base import BaseSandbox


def _load_symbol(path: str) -> type:
    module_name, sep, attr = path.partition(":")
    if not sep or not attr:
        raise ValueError(f"import path must be 'module:Class', got {path!r}")
    module = importlib.import_module(module_name)
    return getattr(module, attr)


class SandboxFactory:
    _MAP: dict[str, str] = {
        "local-process": "sandbox.provider.local_process:LocalProcessSandbox",
    }

    @classmethod
    def create(cls, name: str = "local-process", **kwargs: object) -> BaseSandbox:
        if name not in cls._MAP:
            raise ValueError(f"unknown sandbox {name!r}; known: {sorted(cls._MAP)}")
        klass = _load_symbol(cls._MAP[name])
        return klass(**kwargs)
