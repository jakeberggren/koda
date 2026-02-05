from koda.tools import ToolCall
from koda_tui.state import AppState, MessageRole


class TestAppState:
    """Tests for application state management."""

    def test_streaming_lifecycle(self, state: AppState) -> None:
        """Streaming should go through begin, append, end cycle."""
        state.begin_response("user message")
        assert state.is_streaming is True
        assert state.current_streaming_content == ""
        assert len(state.messages) == 1  # User message added

        state.append_delta("Hello ")
        state.append_delta("world")
        assert state.current_streaming_content == "Hello world"

        state.end_response()
        assert state.is_streaming is False
        assert state.current_streaming_content == ""
        assert state.messages[1].content == "Hello world"

    def test_single_tool_lifecycle(self, state: AppState) -> None:
        """A single tool should be tracked through transition and completion."""
        tool = ToolCall(tool_name="read_file", arguments={"path": "/tmp/a"}, call_id="c1")

        state.begin_response("msg")
        state.transition_to_tool(tool)
        expected_messages = 2  # user + tool

        assert state.active_tools == {"c1": tool}
        assert len(state.messages) == expected_messages
        assert state.messages[1].tool_running is True

        state.complete_tool_message(call_id="c1", display="ok")

        # active_tools persists until end_response (for status bar)
        assert state.active_tools == {"c1": tool}
        assert state.messages[1].tool_running is False
        assert state.messages[1].tool_error is False
        assert state.messages[1].tool_result_display == "ok"
        assert state.messages[1].tool_error_message is None

        state.end_response()
        assert state.active_tools == {}

    def test_parallel_tool_lifecycle(self, state: AppState) -> None:
        """Multiple tools should be tracked concurrently."""
        tool_a = ToolCall(tool_name="read_file", arguments={}, call_id="a")
        tool_b = ToolCall(tool_name="grep", arguments={}, call_id="b")

        state.begin_response("msg")
        state.transition_to_tool(tool_a)
        state.transition_to_tool(tool_b)

        assert state.active_tools == {"a": tool_a, "b": tool_b}
        assert state.messages[1].tool_running is True
        assert state.messages[2].tool_running is True

        # Complete first tool
        state.complete_tool_message(call_id="a", display="found")
        assert state.active_tools == {"a": tool_a, "b": tool_b}
        assert state.messages[1].tool_running is False

        # Complete second tool
        state.complete_tool_message(call_id="b", display="matched")
        assert state.active_tools == {"a": tool_a, "b": tool_b}
        assert state.messages[2].tool_running is False

        # active_tools cleared only on end_response
        state.end_response()
        assert state.active_tools == {}

    def test_end_response_completes_active_tools(self, state: AppState) -> None:
        """end_response() should complete all remaining active tools."""
        tool_a = ToolCall(tool_name="read_file", arguments={}, call_id="a")
        tool_b = ToolCall(tool_name="grep", arguments={}, call_id="b")

        state.begin_response("msg")
        state.transition_to_tool(tool_a)
        state.transition_to_tool(tool_b)
        state.end_response()

        assert state.active_tools == {}
        assert state.messages[1].tool_running is False
        assert state.messages[2].tool_running is False
        # is_error=None means tool_error stays at default (False)
        assert state.messages[1].tool_error is False
        assert state.messages[2].tool_error is False

    def test_complete_tool_message_error(self, state: AppState) -> None:
        """complete_tool_message() with is_error=True should flag the message."""
        tool = ToolCall(tool_name="read_file", arguments={}, call_id="c1")

        state.begin_response("msg")
        state.transition_to_tool(tool)
        state.complete_tool_message(
            call_id="c1",
            display="not found",
            is_error=True,
            error_message="missing file",
        )

        assert state.messages[1].tool_error is True
        assert state.messages[1].tool_result_display == "not found"
        assert state.messages[1].tool_error_message == "missing file"

    def test_complete_tool_message_defaults_to_no_error(self, state: AppState) -> None:
        """complete_tool_message() without is_error should default to False."""
        tool = ToolCall(tool_name="read_file", arguments={}, call_id="c1")

        state.begin_response("msg")
        state.transition_to_tool(tool)
        state.complete_tool_message(call_id="c1")

        assert state.messages[1].tool_error is False

    def test_transition_to_tool_finalizes_streaming_content(self, state: AppState) -> None:
        """transition_to_tool() should save pending streaming content as a message."""
        state.begin_response("msg")
        state.append_delta("partial text")
        tool = ToolCall(tool_name="search", arguments={}, call_id="c1")
        state.transition_to_tool(tool)

        # Streaming content saved as assistant message
        assert state.messages[1].role == MessageRole.ASSISTANT
        assert state.messages[1].content == "partial text"
        assert state.current_streaming_content == ""
        # Tool message follows
        assert state.messages[2].role == MessageRole.TOOL

    def test_exit_request(self, state: AppState) -> None:
        """request_exit() should require two calls to exit."""
        assert state.request_exit() is False
        assert state.request_exit() is True
