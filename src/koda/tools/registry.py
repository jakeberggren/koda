from koda.tools.base import Tool, ToolDefinition


class ToolRegistry:
    """Registry for managing available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
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
        return [
            ToolDefinition(
                name=tool.name,
                description=tool.description,
                parameters_model=tool.parameters_model,
            )
            for tool in self._tools.values()
        ]

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
