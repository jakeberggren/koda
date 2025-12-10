from __future__ import annotations

import importlib
from types import ModuleType

__all__ = ["braintrust", "langfuse", "noop"]


def __getattr__(name: str) -> ModuleType:
    # Lazy-load platform modules so optional deps don't break package import
    if name in __all__:
        return importlib.import_module(f"{__name__}.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name}")


def __dir__() -> list[str]:
    return sorted(__all__)
