from typing import Any

from koda.tools.base import Tool, ToolDefinition
from koda.tools.utils import pydantic_model_to_json_schema


class ToolRegistry:
    """Registry for managing available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Any) -> None:
        """Register a tool in the registry."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all(self) -> list[Tool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get_definitions(self) -> list[ToolDefinition]:
        """Get tool definitions for all registered tools."""
        definitions = []
        for tool in self._tools.values():
            schema = pydantic_model_to_json_schema(tool.parameters_model)
            definitions.append(
                ToolDefinition(
                    name=tool.name,
                    description=tool.description,
                    parameters=schema,
                )
            )
        return definitions

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
