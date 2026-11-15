from __future__ import annotations

from typing import TYPE_CHECKING

from koda.tools.base import Tool, ToolDefinition
from koda.tools.exceptions import ToolAlreadyRegisteredError

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


class ToolRegistry:
    """The tools an agent can use, by name. Fixed once made."""

    def __init__(self, tools: Iterable[Tool] = ()) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ToolAlreadyRegisteredError(tool.name)
            self._tools[tool.name] = tool

    def __iter__(self) -> Iterator[Tool]:
        return iter(self._tools.values())

    def __len__(self) -> int:
        return len(self._tools)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def definitions(self) -> list[ToolDefinition]:
        """The tools as a request offers them to the model."""
        return [ToolDefinition(tool.name, tool.description, tool.parameters_model) for tool in self]
