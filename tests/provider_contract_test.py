"""
Provider contract tests.

These tests define the behavioral contract that ALL provider adapters must satisfy.
Any new provider implementation should pass all these tests.
"""

from __future__ import annotations

from pydantic import BaseModel

from koda.core import message
from koda.providers import adapter as provider_adapter
from koda.tools import base as tools_base


class TestAdaptMessages:
    """Contract tests for adapt_messages()."""

    def test_user_message_produces_output(self, adapter: provider_adapter.ProviderAdapter) -> None:
        """User messages must produce non-empty output."""
        msg = message.UserMessage(content="Hello")
        result = adapter.adapt_messages([msg])
        assert result  # Non-empty

    def test_assistant_message_produces_output(
        self, adapter: provider_adapter.ProviderAdapter
    ) -> None:
        """Assistant messages must produce non-empty output."""
        msg = message.AssistantMessage(content="Hi there")
        result = adapter.adapt_messages([msg])
        assert result

    def test_system_message_produces_output(
        self, adapter: provider_adapter.ProviderAdapter
    ) -> None:
        """System messages must produce non-empty output."""
        msg = message.SystemMessage(content="You are helpful")
        result = adapter.adapt_messages([msg])
        assert result

    def test_empty_message_list_returns_empty(
        self, adapter: provider_adapter.ProviderAdapter
    ) -> None:
        """Empty input must return empty output (not None or error)."""
        result = adapter.adapt_messages([])
        assert result == [] or result == ()

    def test_multiple_messages_preserves_count(
        self, adapter: provider_adapter.ProviderAdapter
    ) -> None:
        """Multiple messages must all be included in output."""
        messages: list[message.Message] = [
            message.SystemMessage(content="System"),
            message.UserMessage(content="User"),
            message.AssistantMessage(content="Assistant"),
        ]
        result = adapter.adapt_messages(messages)
        assert len(result) == 3


class TestToolCallRoundtrip:
    """Contract tests for tool call -> tool result roundtrip."""

    def test_call_id_preserved_in_tool_message(
        self, adapter: provider_adapter.ProviderAdapter
    ) -> None:
        """Tool results must preserve the original call_id."""
        call_id = "call_abc123"
        tool_msg = message.ToolMessage(
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
        self, adapter: provider_adapter.ProviderAdapter
    ) -> None:
        """Error tool results must include error information."""
        error_msg = message.ToolMessage(
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
        self, adapter: provider_adapter.ProviderAdapter
    ) -> None:
        """Successful tool results should not include error_message field."""
        success_msg = message.ToolMessage(
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

    def test_multiple_tool_results(self, adapter: provider_adapter.ProviderAdapter) -> None:
        """Multiple tool results in one batch must all be included."""
        messages: list[message.Message] = [
            message.ToolMessage(
                tool_name="tool_a",
                tool_result=tools_base.ToolResult(
                    output=tools_base.ToolOutput(content={"a": 1}),
                    call_id="call_a",
                ),
            ),
            message.ToolMessage(
                tool_name="tool_b",
                tool_result=tools_base.ToolResult(
                    output=tools_base.ToolOutput(content={"b": 2}),
                    call_id="call_b",
                ),
            ),
        ]

        result = adapter.adapt_messages(messages)
        assert len(result) == 2

        # Both call_ids should be present
        result_str = str(result)
        assert "call_a" in result_str
        assert "call_b" in result_str


class TestAdaptTools:
    """Contract tests for adapt_tools()."""

    def test_none_tools_does_not_raise(self, adapter: provider_adapter.ProviderAdapter) -> None:
        """Passing None for tools must not raise an exception."""
        # Should not raise - result may be empty list, None, or sentinel
        adapter.adapt_tools(None)

    def test_empty_tools_does_not_raise(self, adapter: provider_adapter.ProviderAdapter) -> None:
        """Passing empty list for tools must not raise an exception."""
        adapter.adapt_tools([])

    def test_single_tool_produces_output(
        self,
        adapter: provider_adapter.ProviderAdapter,
        sample_tool_definition: tools_base.ToolDefinition,
    ) -> None:
        """A single tool definition must be processable without error."""
        # Should not raise
        result = adapter.adapt_tools([sample_tool_definition])
        # Result structure varies by provider, just ensure no exception
        assert result is not None or result == []

    def test_multiple_tools_all_included(
        self,
        adapter: provider_adapter.ProviderAdapter,
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

        result = adapter.adapt_tools([sample_tool_definition, other_tool])

        # If result is a list, it should have 2 items
        if isinstance(result, list):
            assert len(result) == 2


class TestEmptyAndEdgeCases:
    """Contract tests for edge cases and empty inputs."""

    def test_empty_content_user_message(self, adapter: provider_adapter.ProviderAdapter) -> None:
        """User message with empty content should not raise."""
        msg = message.UserMessage(content="")
        result = adapter.adapt_messages([msg])
        assert result is not None

    def test_empty_content_assistant_message(
        self, adapter: provider_adapter.ProviderAdapter
    ) -> None:
        """Assistant message with empty content should not raise."""
        msg = message.AssistantMessage(content="")
        result = adapter.adapt_messages([msg])
        assert result is not None

    def test_tool_result_with_empty_content(
        self, adapter: provider_adapter.ProviderAdapter
    ) -> None:
        """Tool result with empty content dict should not raise."""
        tool_msg = message.ToolMessage(
            tool_name="tool",
            tool_result=tools_base.ToolResult(
                output=tools_base.ToolOutput(content={}),
                call_id="call_empty",
            ),
        )
        result = adapter.adapt_messages([tool_msg])
        assert result is not None


def validate_adapter_contract(adapter: provider_adapter.ProviderAdapter) -> list[str]:
    """
    Validate an adapter implementation meets the contract.

    Returns list of failures (empty = all passed).
    Useful for runtime validation when adding new providers.
    """
    failures: list[str] = []

    # Test empty messages
    try:
        result = adapter.adapt_messages([])
        if result is None:
            failures.append("adapt_messages([]) returned None instead of empty list")
    except Exception as e:
        failures.append(f"adapt_messages([]) raised: {e}")

    # Test None tools
    try:
        adapter.adapt_tools(None)
    except Exception as e:
        failures.append(f"adapt_tools(None) raised: {e}")

    # Test basic message
    try:
        adapter.adapt_messages([message.UserMessage(content="test")])
    except Exception as e:
        failures.append(f"adapt_messages with UserMessage raised: {e}")

    # Test tool message with call_id
    try:
        tool_msg = message.ToolMessage(
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

    return failures
