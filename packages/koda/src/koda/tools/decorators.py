from __future__ import annotations

from koda.tools.base import Tool

_builtin_tools: list[type[Tool]] = []


class ToolDecoratorError(TypeError):
    """Raised when a class decorated with @tool is missing required attributes."""

    def __init__(self, cls_name: str, missing: str) -> None:
        super().__init__(f"Tool {cls_name} must have {missing}")


def _require_attr(cls: type, attr: str, label: str) -> None:
    if not hasattr(cls, attr):
        raise ToolDecoratorError(cls.__name__, label)


def tool[T: Tool](cls: type[T]) -> type[T]:
    """Decorator to mark a class as a tool.

    Validates the class has required attributes and registers it
    for later collection via get_builtin_tools().
    """
    _require_attr(cls, "name", "a 'name' attribute")
    _require_attr(cls, "description", "a 'description' attribute")
    _require_attr(cls, "parameters_model", "a 'parameters_model' attribute")

    if not callable(getattr(cls, "execute", None)):
        raise ToolDecoratorError(cls.__name__, "an 'execute' method")

    _builtin_tools.append(cls)
    return cls


def get_builtin_tools() -> list[Tool]:
    """Get instances of all registered builtin tools."""
    # Import builtins to ensure all @tool decorators have run
    import koda.tools.builtins  # noqa: F401, PLC0415

    return [cls() for cls in _builtin_tools]
