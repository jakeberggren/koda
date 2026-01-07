"""
Provider contract tests.

These tests define the behavioral contract that ALL provider adapters must satisfy.
Any new provider implementation should pass all these tests.
"""

from pydantic import BaseModel

from koda.messages import AssistantMessage, Message, SystemMessage, ToolMessage, UserMessage
from koda.providers import ProviderAdapter
from koda.tools import base as tools_base


class TestAdaptMessages:
    """Contract tests for adapt_messages()."""

    def test_user_message_produces_output(self, adapter: ProviderAdapter) -> None:
        """User messages must produce non-empty output."""
        msg = UserMessage(content="Hello")
        result = adapter.adapt_messages([msg])
        assert result  # Non-empty

    def test_assistant_message_produces_output(
        self,
        adapter: ProviderAdapter,
    ) -> None:
        """Assistant messages must produce non-empty output."""
        msg = AssistantMessage(content="Hi there")
        result = adapter.adapt_messages([msg])
        assert result

    def test_system_message_produces_output(
        self,
        adapter: ProviderAdapter,
    ) -> None:
        """System messages must produce non-empty output."""
        msg = SystemMessage(content="You are helpful")
        result = adapter.adapt_messages([msg])
        assert result

    def test_empty_message_list_returns_empty(
        self,
        adapter: ProviderAdapter,
    ) -> None:
        """Empty input must return empty output (not None or error)."""
        result = adapter.adapt_messages([])
        assert result in ([], ())

    def test_multiple_messages_preserves_count(
        self,
        adapter: ProviderAdapter,
    ) -> None:
        """Multiple messages must all be included in output."""
        messages: list[Message] = [
            SystemMessage(content="System"),
            UserMessage(content="User"),
            AssistantMessage(content="Assistant"),
        ]
        result = adapter.adapt_messages(messages)
        assert len(result) == len(messages)


class TestToolCallRoundtrip:
    """Contract tests for tool call -> tool result roundtrip."""

    def test_call_id_preserved_in_tool_message(
        self,
        adapter: ProviderAdapter,
    ) -> None:
        """Tool results must preserve the original call_id."""
        call_id = "call_abc123"
        tool_msg = ToolMessage(
            tool_name="test_tool",
            tool_result=tools_base.ToolResult(
                output=tools_base.ToolOutput(content={"result": "ok"}),
                call_id=call_id,
            ),
        )

        result = adapter.adapt_messages([tool_msg])
        assert result  # Must produce output

        # The call_id should be somewhere in the serialized result
        result_str = str(result)
        assert call_id in result_str, f"call_id '{call_id}' not found in adapted output"

    def test_tool_error_includes_error_state(
        self,
        adapter: ProviderAdapter,
    ) -> None:
        """Error tool results must include error information."""
        error_msg = ToolMessage(
            tool_name="tool",
            tool_result=tools_base.ToolResult(
                output=tools_base.ToolOutput(is_error=True, error_message="Something failed"),
                call_id="call_err",
            ),
        )

        result = adapter.adapt_messages([error_msg])
        result_str = str(result).lower()

        # Error state should be reflected in output
        assert "error" in result_str or "fail" in result_str

    def test_tool_success_does_not_include_error_message(
        self,
        adapter: ProviderAdapter,
    ) -> None:
        """Successful tool results should not include error_message field."""
        success_msg = ToolMessage(
            tool_name="tool",
            tool_result=tools_base.ToolResult(
                output=tools_base.ToolOutput(content={"data": 1}),
                call_id="call_ok",
            ),
        )

        result = adapter.adapt_messages([success_msg])
        result_str = str(result)

        # error_message key should not appear (it's None)
        assert "error_message" not in result_str

    def test_multiple_tool_results(self, adapter: ProviderAdapter) -> None:
        """Multiple tool results in one batch must all be included."""
        messages: list[Message] = [
            ToolMessage(
                tool_name="tool_a",
                tool_result=tools_base.ToolResult(
                    output=tools_base.ToolOutput(content={"a": 1}),
                    call_id="call_a",
                ),
            ),
            ToolMessage(
                tool_name="tool_b",
                tool_result=tools_base.ToolResult(
                    output=tools_base.ToolOutput(content={"b": 2}),
                    call_id="call_b",
                ),
            ),
        ]

        result = adapter.adapt_messages(messages)
        assert len(result) == len(messages)

        # Both call_ids should be present
        result_str = str(result)
        assert "call_a" in result_str
        assert "call_b" in result_str


class TestAdaptTools:
    """Contract tests for adapt_tools()."""

    def test_none_tools_does_not_raise(self, adapter: ProviderAdapter) -> None:
        """Passing None for tools must not raise an exception."""
        # Should not raise - result may be empty list, None, or sentinel
        adapter.adapt_tools(None)

    def test_empty_tools_does_not_raise(self, adapter: ProviderAdapter) -> None:
        """Passing empty list for tools must not raise an exception."""
        adapter.adapt_tools([])

    def test_single_tool_produces_output(
        self,
        adapter: ProviderAdapter,
        sample_tool_definition: tools_base.ToolDefinition,
    ) -> None:
        """A single tool definition must be processable without error."""
        # Should not raise
        result = adapter.adapt_tools([sample_tool_definition])
        # Result structure varies by provider, just ensure no exception
        assert result is not None or result == []

    def test_multiple_tools_all_included(
        self,
        adapter: ProviderAdapter,
        sample_tool_definition: tools_base.ToolDefinition,
    ) -> None:
        """Multiple tools must all be adapted."""

        class OtherParams(BaseModel):
            name: str

        other_tool = tools_base.ToolDefinition(
            name="other",
            description="Another tool",
            parameters_model=OtherParams,
        )

        tools = [sample_tool_definition, other_tool]
        result = adapter.adapt_tools(tools)

        # If result is a list, it should have 2 items
        if isinstance(result, list):
            assert len(result) == len(tools)


class TestEmptyAndEdgeCases:
    """Contract tests for edge cases and empty inputs."""

    def test_empty_content_user_message(self, adapter: ProviderAdapter) -> None:
        """User message with empty content should not raise."""
        msg = UserMessage(content="")
        result = adapter.adapt_messages([msg])
        assert result is not None

    def test_empty_content_assistant_message(
        self,
        adapter: ProviderAdapter,
    ) -> None:
        """Assistant message with empty content should not raise."""
        msg = AssistantMessage(content="")
        result = adapter.adapt_messages([msg])
        assert result is not None

    def test_tool_result_with_empty_content(
        self,
        adapter: ProviderAdapter,
    ) -> None:
        """Tool result with empty content dict should not raise."""
        tool_msg = ToolMessage(
            tool_name="tool",
            tool_result=tools_base.ToolResult(
                output=tools_base.ToolOutput(content={}),
                call_id="call_empty",
            ),
        )
        result = adapter.adapt_messages([tool_msg])
        assert result is not None


def _validate_empty_messages(
    adapter: ProviderAdapter,
    failures: list[str],
) -> None:
    """Validate that empty messages are handled correctly."""
    try:
        result = adapter.adapt_messages([])
        if result is None:
            failures.append("adapt_messages([]) returned None instead of empty list")
    except Exception as e:
        failures.append(f"adapt_messages([]) raised: {e}")


def _validate_none_tools(
    adapter: ProviderAdapter,
    failures: list[str],
) -> None:
    """Validate that None tools are handled correctly."""
    try:
        adapter.adapt_tools(None)
    except Exception as e:
        failures.append(f"adapt_tools(None) raised: {e}")


def _validate_user_message(
    adapter: ProviderAdapter,
    failures: list[str],
) -> None:
    """Validate that user messages are handled correctly."""
    try:
        adapter.adapt_messages([UserMessage(content="test")])
    except Exception as e:
        failures.append(f"adapt_messages with UserMessage raised: {e}")


def _validate_tool_message(
    adapter: ProviderAdapter,
    failures: list[str],
) -> None:
    """Validate that tool messages preserve call_id."""
    try:
        tool_msg = ToolMessage(
            tool_name="test",
            tool_result=tools_base.ToolResult(
                output=tools_base.ToolOutput(content={"ok": True}),
                call_id="test_call_id",
            ),
        )
        result = adapter.adapt_messages([tool_msg])
        if "test_call_id" not in str(result):
            failures.append("call_id not preserved in tool message output")
    except Exception as e:
        failures.append(f"adapt_messages with ToolMessage raised: {e}")


def validate_adapter_contract(adapter: ProviderAdapter) -> list[str]:
    """
    Validate an adapter implementation meets the contract.

    Returns list of failures (empty = all passed).
    Useful for runtime validation when adding new providers.
    """
    failures: list[str] = []
    _validate_empty_messages(adapter, failures)
    _validate_none_tools(adapter, failures)
    _validate_user_message(adapter, failures)
    _validate_tool_message(adapter, failures)
    return failures
