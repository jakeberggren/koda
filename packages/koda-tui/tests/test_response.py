from koda_service.types import AssistantMessage, ResponseCompleted, TokenUsage, ToolCall
from koda_tui.app.response import ResponseLifecycle
from koda_tui.state import AppState, MessageRole, ResponsePhase


class TestResponseLifecycle:
    """Tests for response lifecycle management."""

    def test_streaming_lifecycle(self, state: AppState, lifecycle: ResponseLifecycle) -> None:
        """Streaming should go through begin, append, end cycle."""
        lifecycle.begin("user message")
        assert state.is_streaming is True
        assert state.is_thinking is False
        assert state.response_phase is ResponsePhase.WORKING
        assert state.current_streaming_content == ""
        assert len(state.messages) == 1  # User message added

        lifecycle.append_content("Hello ")
        lifecycle.append_content("world")
        assert state.current_streaming_content == "Hello world"
        assert state.response_phase is ResponsePhase.RESPONDING

        lifecycle.end()
        assert state.is_streaming is False
        assert state.response_phase is ResponsePhase.IDLE
        assert state.current_streaming_content == ""
        assert state.messages[1].content == "Hello world"

    def test_end_persists_thinking_content(
        self, state: AppState, lifecycle: ResponseLifecycle
    ) -> None:
        """Thinking content should persist on the finalized assistant message."""
        lifecycle.begin("user message")
        lifecycle.append_thinking("Comparing approaches")
        assert state.is_thinking is True
        assert state.response_phase is ResponsePhase.WORKING
        lifecycle.append_content("Final answer")
        assert state.is_thinking is False
        assert state.response_phase is ResponsePhase.RESPONDING

        lifecycle.end()

        assert state.messages[1].role == MessageRole.ASSISTANT
        assert state.messages[1].thinking_content == "Comparing approaches"
        assert state.messages[1].content == "Final answer"
        assert state.current_thinking_content == ""

    def test_single_tool_lifecycle(self, state: AppState, lifecycle: ResponseLifecycle) -> None:
        """A single tool should be tracked through transition and completion."""
        tool = ToolCall(tool_name="read_file", arguments={"path": "/tmp/a"}, call_id="c1")

        lifecycle.begin("msg")
        lifecycle.transition_to_tool(tool)
        expected_messages = 2  # user + tool

        assert state.response_phase is ResponsePhase.TOOLS
        assert state.active_tools == {"c1": tool}
        assert len(state.messages) == expected_messages
        assert state.messages[1].tool_running is True

        lifecycle.complete_tool(
            call_id="c1",
            display="ok",
            content={"stdout": "hello", "stderr": "", "exit_code": 0},
        )

        assert state.active_tools == {}
        assert state.is_thinking is False
        assert state.response_phase is ResponsePhase.WORKING
        assert state.messages[1].tool_running is False
        assert state.messages[1].tool_error is False
        assert state.messages[1].tool_result_display == "ok"
        assert state.messages[1].tool_result_content == {
            "stdout": "hello",
            "stderr": "",
            "exit_code": 0,
        }
        assert state.messages[1].tool_error_message is None

        lifecycle.end()
        assert state.active_tools == {}
        assert state.response_phase is ResponsePhase.IDLE

    def test_parallel_tool_lifecycle(self, state: AppState, lifecycle: ResponseLifecycle) -> None:
        """Multiple tools should be tracked concurrently."""
        tool_a = ToolCall(tool_name="read_file", arguments={}, call_id="a")
        tool_b = ToolCall(tool_name="grep", arguments={}, call_id="b")

        lifecycle.begin("msg")
        lifecycle.transition_to_tool(tool_a)
        lifecycle.transition_to_tool(tool_b)

        assert state.response_phase is ResponsePhase.TOOLS
        assert state.active_tools == {"a": tool_a, "b": tool_b}
        assert state.messages[1].tool_running is True
        assert state.messages[2].tool_running is True

        # Complete first tool
        lifecycle.complete_tool(call_id="a", display="found")
        assert state.active_tools == {"b": tool_b}
        assert state.response_phase is ResponsePhase.TOOLS
        assert state.messages[1].tool_running is False

        # Complete second tool
        lifecycle.complete_tool(call_id="b", display="matched")
        assert state.active_tools == {}
        assert state.is_thinking is False
        assert state.response_phase is ResponsePhase.WORKING
        assert state.messages[2].tool_running is False

        lifecycle.end()
        assert state.active_tools == {}
        assert state.response_phase is ResponsePhase.IDLE

    def test_end_completes_active_tools(
        self, state: AppState, lifecycle: ResponseLifecycle
    ) -> None:
        """end() should complete all remaining active tools."""
        tool_a = ToolCall(tool_name="read_file", arguments={}, call_id="a")
        tool_b = ToolCall(tool_name="grep", arguments={}, call_id="b")

        lifecycle.begin("msg")
        lifecycle.transition_to_tool(tool_a)
        lifecycle.transition_to_tool(tool_b)
        lifecycle.end()

        assert state.active_tools == {}
        assert state.response_phase is ResponsePhase.IDLE
        assert state.messages[1].tool_running is False
        assert state.messages[2].tool_running is False
        assert state.messages[1].tool_error is False
        assert state.messages[2].tool_error is False

    def test_complete_tool_error(self, state: AppState, lifecycle: ResponseLifecycle) -> None:
        """complete_tool() with is_error=True should flag the message."""
        tool = ToolCall(tool_name="read_file", arguments={}, call_id="c1")

        lifecycle.begin("msg")
        lifecycle.transition_to_tool(tool)
        lifecycle.complete_tool(
            call_id="c1",
            display="not found",
            is_error=True,
            error_message="missing file",
        )

        assert state.active_tools == {}
        assert state.messages[1].tool_error is True
        assert state.messages[1].tool_result_display == "not found"
        assert state.messages[1].tool_error_message == "missing file"

    def test_complete_tool_defaults_to_no_error(
        self, state: AppState, lifecycle: ResponseLifecycle
    ) -> None:
        """complete_tool() without is_error should default to False."""
        tool = ToolCall(tool_name="read_file", arguments={}, call_id="c1")

        lifecycle.begin("msg")
        lifecycle.transition_to_tool(tool)
        lifecycle.complete_tool(call_id="c1")

        assert state.active_tools == {}
        assert state.messages[1].tool_error is False

    def test_transition_to_tool_finalizes_streaming_content(
        self, state: AppState, lifecycle: ResponseLifecycle
    ) -> None:
        """transition_to_tool() should save pending streaming content as a message."""
        lifecycle.begin("msg")
        lifecycle.append_content("partial text")
        tool = ToolCall(tool_name="search", arguments={}, call_id="c1")
        lifecycle.transition_to_tool(tool)

        # Streaming content saved as assistant message
        assert state.messages[1].role == MessageRole.ASSISTANT
        assert state.messages[1].content == "partial text"
        assert state.current_streaming_content == ""
        assert state.response_phase is ResponsePhase.TOOLS
        # Tool message follows
        assert state.messages[2].role == MessageRole.TOOL

    def test_transition_to_tool_persists_thinking_content(
        self, state: AppState, lifecycle: ResponseLifecycle
    ) -> None:
        """transition_to_tool() should keep thinking content on the finalized message."""
        lifecycle.begin("msg")
        lifecycle.append_thinking("Need to search first")
        tool = ToolCall(tool_name="search", arguments={}, call_id="c1")

        lifecycle.transition_to_tool(tool)

        assert state.messages[1].role == MessageRole.ASSISTANT
        assert state.messages[1].thinking_content == "Need to search first"
        assert state.messages[1].content == ""
        assert state.current_thinking_content == ""
        assert state.response_phase is ResponsePhase.TOOLS

    def test_duplicate_tool_transition_is_idempotent(
        self, state: AppState, lifecycle: ResponseLifecycle
    ) -> None:
        """Repeated start events for the same tool should not duplicate tool messages."""
        tool = ToolCall(tool_name="search", arguments={}, call_id="c1")

        lifecycle.begin("msg")
        lifecycle.transition_to_tool(tool)
        lifecycle.transition_to_tool(tool)

        assert state.active_tools == {"c1": tool}
        assert len(state.messages) == 2
        assert state.messages[1].role == MessageRole.TOOL
        assert state.response_phase is ResponsePhase.TOOLS

    def test_complete_tool_returns_to_responding_when_text_is_present(
        self, state: AppState, lifecycle: ResponseLifecycle
    ) -> None:
        """After a tool completes, buffered text should restore responding phase."""
        tool = ToolCall(tool_name="search", arguments={}, call_id="c1")

        lifecycle.begin("msg")
        lifecycle.transition_to_tool(tool)
        state.current_streaming_content = "Buffered answer"

        lifecycle.complete_tool(call_id="c1")

        assert state.response_phase is ResponsePhase.RESPONDING

    def test_complete_tool_returns_to_thinking_when_thinking_is_present(
        self, state: AppState, lifecycle: ResponseLifecycle
    ) -> None:
        """After a tool completes, buffered thinking should restore working + thinking."""
        tool = ToolCall(tool_name="search", arguments={}, call_id="c1")

        lifecycle.begin("msg")
        lifecycle.transition_to_tool(tool)
        state.current_thinking_content = "Need one more step"

        lifecycle.complete_tool(call_id="c1")

        assert state.is_thinking is True
        assert state.response_phase is ResponsePhase.WORKING

    def test_response_completed_persists_usage(
        self, state: AppState, lifecycle: ResponseLifecycle
    ) -> None:
        """ResponseCompleted should persist latest usage for the status bar."""
        lifecycle.begin("msg")

        lifecycle.apply_event(
            ResponseCompleted(
                output=AssistantMessage(content="done"),
                usage=TokenUsage(
                    input_tokens=2_000,
                    output_tokens=500,
                    cached_tokens=100,
                    total_tokens=2_500,
                ),
            )
        )

        assert state.usage is not None
        assert state.total_usage is not None
        assert state.usage.input_tokens == 2_000
        assert state.usage.output_tokens == 500
        assert state.usage.cached_tokens == 100
        assert state.usage.total_tokens == 2_500
        assert state.total_usage.input_tokens == 2_000
        assert state.total_usage.output_tokens == 500
        assert state.total_usage.cached_tokens == 100
        assert state.total_usage.total_tokens == 2_500

    def test_end_persists_buffered_content_even_after_response_completed(
        self, state: AppState, lifecycle: ResponseLifecycle
    ) -> None:
        """ResponseCompleted should not replace the buffered assistant content path."""
        lifecycle.begin("msg")
        lifecycle.append_thinking("partial thinking")
        lifecycle.append_content("partial content")

        lifecycle.apply_event(
            ResponseCompleted(
                output=AssistantMessage(
                    content="final content",
                    thinking_content="final thinking",
                )
            )
        )

        lifecycle.end()

        assert state.messages[1].role == MessageRole.ASSISTANT
        assert state.messages[1].content == "partial content"
        assert state.messages[1].thinking_content == "partial thinking"
