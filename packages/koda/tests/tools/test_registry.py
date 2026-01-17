"""Tests for tools/registry.py - ToolRegistry operations."""

import pytest

from koda.tools import ToolRegistry
from koda.tools.exceptions import ToolAlreadyRegisteredError

from .conftest import ErrorTool, SimpleParams, SimpleTool


class TestToolRegistry:
    """Tests for ToolRegistry operations."""

    def test_register_and_get(self, registry: ToolRegistry, simple_tool: SimpleTool) -> None:
        """Tools can be registered and retrieved by name."""
        registry.register(simple_tool)
        retrieved = registry.get("simple_tool")

        assert retrieved is simple_tool

    def test_register_all(self, registry: ToolRegistry) -> None:
        """Multiple tools can be registered at once."""
        registry.register_all([SimpleTool(), ErrorTool()])

        assert registry.get("simple_tool") is not None
        assert registry.get("error_tool") is not None

    def test_duplicate_registration_raises(self, registry: ToolRegistry) -> None:
        """Registering the same tool twice raises ToolAlreadyRegisteredError."""
        registry.register(SimpleTool())

        with pytest.raises(ToolAlreadyRegisteredError) as exc_info:
            registry.register(SimpleTool())

        assert exc_info.value.name == "simple_tool"

    def test_get_definitions(self, registry: ToolRegistry, simple_tool: SimpleTool) -> None:
        """get_definitions returns correct ToolDefinitions."""
        registry.register(simple_tool)

        definitions = registry.get_definitions()

        assert len(definitions) == 1
        assert definitions[0].name == "simple_tool"
        assert definitions[0].description == "A simple test tool"
        assert definitions[0].parameters_model is SimpleParams

    def test_clear(self, registry: ToolRegistry, simple_tool: SimpleTool) -> None:
        """clear removes all registered tools."""
        registry.register(simple_tool)
        assert registry.get("simple_tool") is not None

        registry.clear()

        assert registry.get("simple_tool") is None
        assert registry.get_all() == []
