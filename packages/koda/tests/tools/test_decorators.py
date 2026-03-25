from collections.abc import Generator
from typing import Any

import pytest

from koda.tools import ToolContext, ToolOutput, tool
from koda.tools.decorators import ToolDecoratorError, _builtin_tools

from .conftest import SimpleParams


@pytest.fixture(autouse=True)
def clear_builtin_tools() -> Generator[None]:
    _builtin_tools.clear()
    yield
    _builtin_tools.clear()


def assert_tool_error(cls: type[Any], expected: str) -> None:
    with pytest.raises(ToolDecoratorError) as exc_info:
        tool(cls)

    assert expected in str(exc_info.value)


class TestToolDecorator:
    """Tests for @tool decorator validation."""

    def test_missing_name_raises(self) -> None:
        """Missing name attribute raises ToolDecoratorError."""

        class NoName:
            description = "No name"
            parameters_model = SimpleParams

            async def execute(self, params: SimpleParams, ctx: ToolContext) -> ToolOutput:
                return ToolOutput(content={})

        assert_tool_error(NoName, "name")

    def test_missing_description_raises(self) -> None:
        """Missing description attribute raises ToolDecoratorError."""

        class NoDescription:
            name = "no_desc"
            parameters_model = SimpleParams

            async def execute(self, params: SimpleParams, ctx: ToolContext) -> ToolOutput:
                return ToolOutput(content={})

        assert_tool_error(NoDescription, "description")

    def test_missing_parameters_model_raises(self) -> None:
        """Missing parameters_model attribute raises ToolDecoratorError."""

        class NoParams:
            name = "no_params"
            description = "No params"

            async def execute(self, params: SimpleParams, ctx: ToolContext) -> ToolOutput:
                return ToolOutput(content={})

        assert_tool_error(NoParams, "parameters_model")

    def test_missing_execute_raises(self) -> None:
        """Missing execute method raises ToolDecoratorError."""

        class NoExecute:
            name = "no_execute"
            description = "No execute"
            parameters_model = SimpleParams

        assert_tool_error(NoExecute, "execute")

    def test_non_callable_execute_raises(self) -> None:
        """Non-callable execute attribute raises ToolDecoratorError."""

        class BadExecute:
            name = "bad_execute"
            description = "Bad execute"
            parameters_model = SimpleParams
            execute = "not a method"

        assert_tool_error(BadExecute, "execute")
