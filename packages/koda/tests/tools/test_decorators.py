"""Tests for tools/decorators.py - @tool decorator validation."""

import pytest

from koda.tools import ToolContext, ToolOutput, tool
from koda.tools.decorators import ToolDecoratorError

from .conftest import SimpleParams


class TestToolDecorator:
    """Tests for @tool decorator validation."""

    def test_missing_name_raises(self) -> None:
        """Missing name attribute raises ToolDecoratorError."""
        with pytest.raises(ToolDecoratorError) as exc_info:

            @tool  # type: ignore[arg-type]
            class NoName:
                description = "No name"
                parameters_model = SimpleParams

                async def execute(self, params: SimpleParams, ctx: ToolContext) -> ToolOutput:
                    return ToolOutput(content={})

        assert "name" in str(exc_info.value)

    def test_missing_description_raises(self) -> None:
        """Missing description attribute raises ToolDecoratorError."""
        with pytest.raises(ToolDecoratorError) as exc_info:

            @tool  # type: ignore[arg-type]
            class NoDescription:
                name = "no_desc"
                parameters_model = SimpleParams

                async def execute(self, params: SimpleParams, ctx: ToolContext) -> ToolOutput:
                    return ToolOutput(content={})

        assert "description" in str(exc_info.value)

    def test_missing_parameters_model_raises(self) -> None:
        """Missing parameters_model attribute raises ToolDecoratorError."""
        with pytest.raises(ToolDecoratorError) as exc_info:

            @tool  # type: ignore[arg-type]
            class NoParams:
                name = "no_params"
                description = "No params"

                async def execute(self, params: SimpleParams, ctx: ToolContext) -> ToolOutput:
                    return ToolOutput(content={})

        assert "parameters_model" in str(exc_info.value)

    def test_missing_execute_raises(self) -> None:
        """Missing execute method raises ToolDecoratorError."""
        with pytest.raises(ToolDecoratorError) as exc_info:

            @tool  # type: ignore[arg-type]
            class NoExecute:
                name = "no_execute"
                description = "No execute"
                parameters_model = SimpleParams

        assert "execute" in str(exc_info.value)

    def test_non_callable_execute_raises(self) -> None:
        """Non-callable execute attribute raises ToolDecoratorError."""
        with pytest.raises(ToolDecoratorError) as exc_info:

            @tool  # type: ignore[arg-type]
            class BadExecute:
                name = "bad_execute"
                description = "Bad execute"
                parameters_model = SimpleParams
                execute = "not a method"

        assert "execute" in str(exc_info.value)
