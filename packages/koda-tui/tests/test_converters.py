"""Tests for koda_tui.converters.convert_messages."""

from koda_service.types import (
    AssistantMessage,
    ToolCall,
    ToolMessage,
    ToolOutput,
    ToolResult,
    UserMessage,
)
from koda_tui.converters import convert_messages
from koda_tui.state import MessageRole


def _make_tool_call(call_id: str = "call_1", tool_name: str = "search") -> ToolCall:
    return ToolCall(tool_name=tool_name, arguments={}, call_id=call_id)


def _make_tool_result(
    call_id: str = "call_1",
    display: str | None = "result",
    *,
    is_error: bool = False,
    error_message: str | None = None,
) -> ToolResult:
    return ToolResult(
        call_id=call_id,
        output=ToolOutput(display=display, is_error=is_error, error_message=error_message),
    )


class TestConvertMessages:
    def test_empty_list(self) -> None:
        result, usage = convert_messages([])

        assert result == []
        assert usage is None

    def test_user_message(self) -> None:
        result, usage = convert_messages([UserMessage(content="hello")])

        assert len(result) == 1
        assert result[0].role == MessageRole.USER
        assert result[0].content == "hello"
        assert usage is None

    def test_assistant_message(self) -> None:
        result, usage = convert_messages([AssistantMessage(content="hi there")])

        assert len(result) == 1
        assert result[0].role == MessageRole.ASSISTANT
        assert result[0].content == "hi there"
        assert usage is None

    def test_assistant_message_with_thinking(self) -> None:
        result, usage = convert_messages(
            [AssistantMessage(content="hi there", thinking_content="Compare options")]
        )

        assert len(result) == 1
        assert result[0].role == MessageRole.ASSISTANT
        assert result[0].content == "hi there"
        assert result[0].thinking_content == "Compare options"
        assert usage is None

    def test_assistant_message_with_only_thinking(self) -> None:
        result, usage = convert_messages(
            [AssistantMessage(content="", thinking_content="Need a tool")]
        )

        assert len(result) == 1
        assert result[0].role == MessageRole.ASSISTANT
        assert result[0].content == ""
        assert result[0].thinking_content == "Need a tool"
        assert usage is None

    def test_user_assistant_roundtrip(self) -> None:
        messages = [
            UserMessage(content="hello"),
            AssistantMessage(content="hi"),
        ]

        result, usage = convert_messages(messages)

        assert len(result) == 2
        assert result[0].role == MessageRole.USER
        assert result[1].role == MessageRole.ASSISTANT
        assert usage is None

    def test_tool_call_linked_to_result(self) -> None:
        tc = _make_tool_call(call_id="c1", tool_name="search")
        tr = _make_tool_result(call_id="c1", display="found it")

        messages = [
            UserMessage(content="find something"),
            AssistantMessage(content="", tool_calls=[tc]),
            ToolMessage(tool_name="search", tool_result=tr),
        ]

        result, usage = convert_messages(messages)

        # user + tool entry (assistant with no content is skipped, tool result merged)
        assert len(result) == 2
        tool_msg = result[1]
        assert tool_msg.role == MessageRole.TOOL
        assert tool_msg.tool_call == tc
        assert tool_msg.tool_running is False
        assert tool_msg.tool_result_display == "found it"
        assert tool_msg.tool_error is False
        assert usage is None

    def test_tool_call_with_error_result(self) -> None:
        tc = _make_tool_call(call_id="c1")
        tr = _make_tool_result(call_id="c1", is_error=True, error_message="not found")

        messages = [
            AssistantMessage(content="", tool_calls=[tc]),
            ToolMessage(tool_name="search", tool_result=tr),
        ]

        result, usage = convert_messages(messages)

        assert len(result) == 1
        assert result[0].tool_error is True
        assert result[0].tool_error_message == "not found"
        assert usage is None

    def test_multiple_tool_calls_linked(self) -> None:
        tc1 = _make_tool_call(call_id="c1", tool_name="search")
        tc2 = _make_tool_call(call_id="c2", tool_name="read")
        tr1 = _make_tool_result(call_id="c1", display="search result")
        tr2 = _make_tool_result(call_id="c2", display="file content")

        messages = [
            AssistantMessage(content="", tool_calls=[tc1, tc2]),
            ToolMessage(tool_name="search", tool_result=tr1),
            ToolMessage(tool_name="read", tool_result=tr2),
        ]

        result, usage = convert_messages(messages)

        assert len(result) == 2
        assert result[0].tool_result_display == "search result"
        assert result[1].tool_result_display == "file content"
        assert usage is None

    def test_orphan_tool_result(self) -> None:
        tr = _make_tool_result(call_id="orphan", display="orphan result")

        messages = [
            ToolMessage(tool_name="unknown", tool_result=tr),
        ]

        result, usage = convert_messages(messages)

        assert len(result) == 1
        assert result[0].role == MessageRole.TOOL
        assert result[0].content == "Tool: unknown"
        assert result[0].tool_result_display == "orphan result"
        assert result[0].tool_call is None
        assert usage is None

    def test_assistant_with_content_and_tool_calls(self) -> None:
        tc = _make_tool_call(call_id="c1")
        tr = _make_tool_result(call_id="c1")

        messages = [
            AssistantMessage(content="Let me search", tool_calls=[tc]),
            ToolMessage(tool_name="search", tool_result=tr),
        ]

        result, usage = convert_messages(messages)

        # assistant text + tool entry
        assert len(result) == 2
        assert result[0].role == MessageRole.ASSISTANT
        assert result[0].content == "Let me search"
        assert result[1].role == MessageRole.TOOL
        assert usage is None

    def test_assistant_empty_content_no_tools(self) -> None:
        result, usage = convert_messages([AssistantMessage(content="")])

        assert result == []
        assert usage is None
