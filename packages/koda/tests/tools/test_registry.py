"""Tests for tools/registry.py: the tools an agent can use, by name."""

import pytest

from koda.tools import ToolRegistry
from koda.tools.exceptions import ToolAlreadyRegisteredError

from .conftest import ErrorTool, SimpleParams, SimpleTool


def test_tools_are_found_by_name() -> None:
    simple, error = SimpleTool(), ErrorTool()
    registry = ToolRegistry([simple, error])

    assert registry.get("simple_tool") is simple
    assert registry.get("error_tool") is error
    assert registry.get("missing") is None
    assert list(registry) == [simple, error]


def test_two_tools_with_one_name_are_refused() -> None:
    with pytest.raises(ToolAlreadyRegisteredError) as exc_info:
        ToolRegistry([SimpleTool(), SimpleTool()])

    assert exc_info.value.name == "simple_tool"


def test_definitions_describe_the_tools() -> None:
    [definition] = ToolRegistry([SimpleTool()]).definitions()

    assert definition.name == "simple_tool"
    assert definition.description == "A simple test tool"
    assert definition.parameters_model is SimpleParams
