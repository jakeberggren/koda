from collections.abc import Sequence
from pathlib import Path

from koda import messages as core
from koda.agent import (
    AgentResponseCompleted,
    AgentTextDelta,
    AgentThinkingDelta,
    AgentToolCallRequested,
    AgentToolCompleted,
    AgentToolResultReady,
)
from koda.messages import TokenUsage
from koda.sessions import Session
from koda.tools import ToolCall, ToolOutput, ToolResult
from koda_service import ServiceStatus, ServiceStatusCode
from koda_tui.messaging import Conversation
from koda_tui.state import (
    AppState,
    AssistantMessage,
    Message,
    ResponsePhase,
    ToolMessage,
    Usage,
    UserMessage,
)

READY = ServiceStatus(code=ServiceStatusCode.READY, summary="Ready")


def _tool(message: Message) -> ToolMessage:
    assert isinstance(message, ToolMessage)
    return message


def _output(message: Message) -> ToolOutput:
    output = _tool(message).result
    assert output is not None
    return output


def _reply(message: Message) -> AssistantMessage:
    assert isinstance(message, AssistantMessage)
    return message


def _completed(usage: TokenUsage | None) -> AgentResponseCompleted:
    return AgentResponseCompleted(message=core.AssistantMessage(content="", usage=usage))


def _running(state: AppState) -> list[ToolCall]:
    """The calls still running."""
    return [m.call for m in state.messages if isinstance(m, ToolMessage) and m.result is None]


def _text(message: Message) -> str:
    assert isinstance(message, UserMessage | AssistantMessage)
    return message.text


def _done(call_id: str, output: ToolOutput) -> AgentToolCompleted:
    return AgentToolCompleted(tool_name="tool", result=ToolResult(call_id=call_id, output=output))


class TestResponse:
    """A response, from begin to end, applied to the conversation."""

    def test_streaming_conversation(self, state: AppState, conversation: Conversation) -> None:
        """Streaming should go through begin, append, end cycle."""
        conversation.start("user message")
        assert state.responding is True
        assert state.response_phase is ResponsePhase.WORKING
        assert len(state.messages) == 1  # User message added

        conversation.apply(AgentTextDelta(text="Hello "))
        conversation.apply(AgentTextDelta(text="world"))
        assert _text(state.messages[-1]) == "Hello world"
        assert state.response_phase is ResponsePhase.RESPONDING

        conversation.end()
        assert state.responding is False
        assert state.response_phase is ResponsePhase.IDLE
        assert _text(state.messages[1]) == "Hello world"

    def test_end_persists_thinking_content(
        self, state: AppState, conversation: Conversation
    ) -> None:
        """Thinking content should persist on the finalized assistant message."""
        conversation.start("user message")
        conversation.apply(AgentThinkingDelta(text="Comparing approaches"))
        assert state.response_phase is ResponsePhase.THINKING
        conversation.apply(AgentTextDelta(text="Final answer"))
        assert state.response_phase is ResponsePhase.RESPONDING

        conversation.end()

        assert isinstance(state.messages[1], AssistantMessage)
        assert _reply(state.messages[1]).thinking == "Comparing approaches"
        assert _text(state.messages[1]) == "Final answer"

    def test_single_tool_conversation(self, state: AppState, conversation: Conversation) -> None:
        """A single tool should be tracked through transition and completion."""
        tool = ToolCall(tool_name="read_file", arguments={"path": "/tmp/a"}, call_id="c1")

        conversation.start("msg")
        conversation.apply(AgentToolCallRequested(call=tool))
        expected_messages = 2  # user + tool

        assert state.response_phase is ResponsePhase.TOOLS
        assert _running(state) == [tool]
        assert len(state.messages) == expected_messages
        assert _tool(state.messages[1]).result is None

        conversation.apply(
            _done(
                "c1",
                ToolOutput(display="ok", content={"stdout": "hello", "stderr": "", "exit_code": 0}),
            )
        )

        assert _running(state) == []
        assert state.response_phase is ResponsePhase.WORKING
        assert _tool(state.messages[1]).result is not None
        assert _output(state.messages[1]).is_error is False
        assert _output(state.messages[1]).display == "ok"
        assert _output(state.messages[1]).content == {
            "stdout": "hello",
            "stderr": "",
            "exit_code": 0,
        }
        assert _output(state.messages[1]).error_message is None

        conversation.end()
        assert _running(state) == []
        assert state.response_phase is ResponsePhase.IDLE

    def test_parallel_tool_conversation(self, state: AppState, conversation: Conversation) -> None:
        """Multiple tools should be tracked concurrently."""
        tool_a = ToolCall(tool_name="read_file", arguments={}, call_id="a")
        tool_b = ToolCall(tool_name="grep", arguments={}, call_id="b")

        conversation.start("msg")
        conversation.apply(AgentToolCallRequested(call=tool_a))
        conversation.apply(AgentToolCallRequested(call=tool_b))

        assert state.response_phase is ResponsePhase.TOOLS
        assert _running(state) == [tool_a, tool_b]
        assert _tool(state.messages[1]).result is None
        assert _tool(state.messages[2]).result is None

        # Complete first tool
        conversation.apply(_done("a", ToolOutput(display="found")))
        assert _running(state) == [tool_b]
        assert state.response_phase is ResponsePhase.TOOLS
        assert _tool(state.messages[1]).result is not None

        # Complete second tool
        conversation.apply(_done("b", ToolOutput(display="matched")))
        assert _running(state) == []
        assert state.response_phase is ResponsePhase.WORKING
        assert _tool(state.messages[2]).result is not None

        conversation.end()
        assert _running(state) == []
        assert state.response_phase is ResponsePhase.IDLE

    def test_result_ready_updates_tool_before_ordered_completion(
        self, state: AppState, conversation: Conversation
    ) -> None:
        """Progress result events should mark tools done before persisted completion events."""
        tool_a = ToolCall(tool_name="read_file", arguments={}, call_id="a")
        tool_b = ToolCall(tool_name="grep", arguments={}, call_id="b")
        result_b = ToolResult(call_id="b", output=ToolOutput(display="matched"))

        conversation.start("msg")
        conversation.apply(AgentToolCallRequested(call=tool_a))
        conversation.apply(AgentToolCallRequested(call=tool_b))

        conversation.apply(AgentToolResultReady(tool_name="grep", result=result_b))

        assert _running(state) == [tool_a]
        assert _tool(state.messages[1]).result is None
        assert _tool(state.messages[2]).result is not None
        assert _output(state.messages[2]).display == "matched"

        conversation.apply(AgentToolCompleted(tool_name="grep", result=result_b))

        assert _running(state) == [tool_a]
        assert _output(state.messages[2]).display == "matched"

    def test_end_completes_running_tools(self, state: AppState, conversation: Conversation) -> None:
        """end() should complete all remaining active tools."""
        tool_a = ToolCall(tool_name="read_file", arguments={}, call_id="a")
        tool_b = ToolCall(tool_name="grep", arguments={}, call_id="b")

        conversation.start("msg")
        conversation.apply(AgentToolCallRequested(call=tool_a))
        conversation.apply(AgentToolCallRequested(call=tool_b))
        conversation.end()

        assert _running(state) == []
        assert state.response_phase is ResponsePhase.IDLE
        assert _tool(state.messages[1]).result is not None
        assert _tool(state.messages[2]).result is not None
        assert _output(state.messages[1]).is_error is False
        assert _output(state.messages[2]).is_error is False

    def test_failed_tool_is_flagged(self, state: AppState, conversation: Conversation) -> None:
        """A tool that fails should be flagged, with its error message."""
        tool = ToolCall(tool_name="read_file", arguments={}, call_id="c1")

        conversation.start("msg")
        conversation.apply(AgentToolCallRequested(call=tool))
        conversation.apply(
            _done(
                "c1", ToolOutput(display="not found", is_error=True, error_message="missing file")
            )
        )

        assert _running(state) == []
        assert _output(state.messages[1]).is_error is True
        assert _output(state.messages[1]).display == "not found"
        assert _output(state.messages[1]).error_message == "missing file"

    def test_tool_without_error_is_not_flagged(
        self, state: AppState, conversation: Conversation
    ) -> None:
        """A tool completed without an error should not be flagged."""
        tool = ToolCall(tool_name="read_file", arguments={}, call_id="c1")

        conversation.start("msg")
        conversation.apply(AgentToolCallRequested(call=tool))
        conversation.apply(_done("c1", ToolOutput()))

        assert _running(state) == []
        assert _output(state.messages[1]).is_error is False

    def test_tool_start_finalizes_streaming_content(
        self, state: AppState, conversation: Conversation
    ) -> None:
        """Starting a tool should keep the reply streamed so far as a message."""
        conversation.start("msg")
        conversation.apply(AgentTextDelta(text="partial text"))
        tool = ToolCall(tool_name="search", arguments={}, call_id="c1")
        conversation.apply(AgentToolCallRequested(call=tool))

        # Streaming content saved as assistant message
        assert isinstance(state.messages[1], AssistantMessage)
        assert _text(state.messages[1]) == "partial text"
        assert state.response_phase is ResponsePhase.TOOLS
        # Tool message follows
        assert isinstance(state.messages[2], ToolMessage)

    def test_tool_start_discards_whitespace_only_streaming_content(
        self, state: AppState, conversation: Conversation
    ) -> None:
        """Whitespace-only text before a tool should not create a blank assistant row."""
        conversation.start("msg")
        conversation.apply(AgentTextDelta(text="\n\n"))
        tool = ToolCall(tool_name="search", arguments={}, call_id="c1")

        conversation.apply(AgentToolCallRequested(call=tool))

        assert len(state.messages) == 2
        assert isinstance(state.messages[1], ToolMessage)
        assert _tool(state.messages[1]).call == tool

    def test_end_discards_whitespace_only_streaming_content(
        self, state: AppState, conversation: Conversation
    ) -> None:
        """Whitespace-only final content should not persist as an assistant message."""
        conversation.start("msg")
        conversation.apply(AgentTextDelta(text=" \n\t"))

        conversation.end()

        assert len(state.messages) == 1
        assert state.response_phase is ResponsePhase.IDLE

    def test_tool_start_persists_thinking_content(
        self, state: AppState, conversation: Conversation
    ) -> None:
        """Starting a tool should keep the streamed thinking on that message."""
        conversation.start("msg")
        conversation.apply(AgentThinkingDelta(text="Need to search first"))
        tool = ToolCall(tool_name="search", arguments={}, call_id="c1")

        conversation.apply(AgentToolCallRequested(call=tool))

        assert isinstance(state.messages[1], AssistantMessage)
        assert _reply(state.messages[1]).thinking == "Need to search first"
        assert _text(state.messages[1]) == ""
        assert state.response_phase is ResponsePhase.TOOLS

    def test_duplicate_tool_transition_is_idempotent(
        self, state: AppState, conversation: Conversation
    ) -> None:
        """Repeated start events for the same tool should not duplicate tool messages."""
        tool = ToolCall(tool_name="search", arguments={}, call_id="c1")

        conversation.start("msg")
        conversation.apply(AgentToolCallRequested(call=tool))
        conversation.apply(AgentToolCallRequested(call=tool))

        assert _running(state) == [tool]
        assert len(state.messages) == 2
        assert isinstance(state.messages[1], ToolMessage)
        assert state.response_phase is ResponsePhase.TOOLS

    def test_after_tools_phase_returns_to_responding_when_text_is_present(
        self, state: AppState, conversation: Conversation
    ) -> None:
        """After a tool completes, buffered text should restore responding phase."""
        tool = ToolCall(tool_name="search", arguments={}, call_id="c1")

        conversation.start("msg")
        conversation.apply(AgentToolCallRequested(call=tool))
        conversation.apply(AgentTextDelta(text="Buffered answer"))

        conversation.apply(_done("c1", ToolOutput()))

        assert state.response_phase is ResponsePhase.RESPONDING

    def test_after_tools_phase_returns_to_thinking_when_thinking_is_present(
        self, state: AppState, conversation: Conversation
    ) -> None:
        """After a tool completes, streamed thinking shows the phase as thinking."""
        tool = ToolCall(tool_name="search", arguments={}, call_id="c1")

        conversation.start("msg")
        conversation.apply(AgentToolCallRequested(call=tool))
        conversation.apply(AgentThinkingDelta(text="Need one more step"))

        conversation.apply(_done("c1", ToolOutput()))

        assert state.response_phase is ResponsePhase.THINKING

    def test_response_completed_persists_usage(
        self, state: AppState, conversation: Conversation
    ) -> None:
        """AgentResponseCompleted should persist latest usage for the status bar."""
        conversation.start("msg")

        conversation.apply(
            AgentResponseCompleted(
                message=core.AssistantMessage(
                    content="done",
                    usage=TokenUsage(
                        input_tokens=2_000,
                        output_tokens=500,
                        cached_tokens=100,
                        total_tokens=2_500,
                    ),
                ),
            )
        )

        expected = TokenUsage(
            input_tokens=2_000,
            output_tokens=500,
            cached_tokens=100,
            total_tokens=2_500,
        )
        assert state.usage == Usage(latest=expected, total=expected)

    def test_usage_adds_up_across_responses(
        self,
        state: AppState,
        conversation: Conversation,
    ) -> None:
        """Each response's usage becomes the latest, and is added to the total."""
        conversation.start("msg")
        first = TokenUsage(input_tokens=100, output_tokens=10)
        second = TokenUsage(input_tokens=150, output_tokens=20)
        for usage in (first, second):
            conversation.apply(_completed(usage))

        assert state.usage == Usage(
            latest=second,
            total=TokenUsage(input_tokens=250, output_tokens=30),
        )

    def test_response_without_usage_keeps_the_last(
        self,
        state: AppState,
        conversation: Conversation,
    ) -> None:
        """A response that reports no usage leaves the usage as it was."""
        usage = TokenUsage(input_tokens=100, output_tokens=10)
        conversation.start("msg")
        conversation.apply(_completed(usage))
        conversation.apply(_completed(None))

        assert state.usage == Usage(latest=usage, total=usage)

    def test_end_persists_buffered_content_even_after_response_completed(
        self, state: AppState, conversation: Conversation
    ) -> None:
        """AgentResponseCompleted should not replace the buffered assistant content path."""
        conversation.start("msg")
        conversation.apply(AgentThinkingDelta(text="partial thinking"))
        conversation.apply(AgentTextDelta(text="partial content"))

        conversation.apply(
            AgentResponseCompleted(
                message=core.AssistantMessage(
                    content="final content",
                    thinking_content="final thinking",
                )
            )
        )

        conversation.end()

        assert isinstance(state.messages[1], AssistantMessage)
        assert _text(state.messages[1]) == "partial content"
        assert _reply(state.messages[1]).thinking == "partial thinking"


def _load(
    history: Sequence[core.UserMessage | core.AssistantMessage | core.ToolMessage],
) -> list[Message]:
    state = AppState(workspace=Path("/workspace"), service_status=READY)
    Conversation(state).load(Session(messages=list(history)))
    return state.messages


def _make_tool_call(call_id: str = "call_1", tool_name: str = "search") -> ToolCall:
    return ToolCall(tool_name=tool_name, arguments={}, call_id=call_id)


def _make_tool_result(
    call_id: str = "call_1",
    display: str | None = "result",
    *,
    content: dict[str, object] | None = None,
    is_error: bool = False,
    error_message: str | None = None,
) -> ToolResult:
    return ToolResult(
        call_id=call_id,
        output=ToolOutput(
            content={} if content is None else content,
            display=display,
            is_error=is_error,
            error_message=error_message,
        ),
    )


class TestLoad:
    """A saved session's history, loaded as messages."""

    def test_empty_list(self) -> None:
        result = _load([])

        assert result == []

    def test_user_message(self) -> None:
        result = _load([core.UserMessage(content="hello")])

        assert len(result) == 1
        assert isinstance(result[0], UserMessage)
        assert _text(result[0]) == "hello"

    def test_assistant_message(self) -> None:
        result = _load([core.AssistantMessage(content="hi there")])

        assert len(result) == 1
        assert isinstance(result[0], AssistantMessage)
        assert _text(result[0]) == "hi there"

    def test_assistant_message_with_thinking(self) -> None:
        result = _load(
            [core.AssistantMessage(content="hi there", thinking_content="Compare options")]
        )

        assert len(result) == 1
        assert isinstance(result[0], AssistantMessage)
        assert _text(result[0]) == "hi there"
        assert _reply(result[0]).thinking == "Compare options"

    def test_assistant_message_with_only_thinking(self) -> None:
        result = _load([core.AssistantMessage(content="", thinking_content="Need a tool")])

        assert len(result) == 1
        assert isinstance(result[0], AssistantMessage)
        assert _text(result[0]) == ""
        assert _reply(result[0]).thinking == "Need a tool"

    def test_user_assistant_roundtrip(self) -> None:
        messages = [
            core.UserMessage(content="hello"),
            core.AssistantMessage(content="hi"),
        ]

        result = _load(messages)

        assert len(result) == 2
        assert isinstance(result[0], UserMessage)
        assert isinstance(result[1], AssistantMessage)

    def test_tool_call_linked_to_result(self) -> None:
        tc = _make_tool_call(call_id="c1", tool_name="search")
        tr = _make_tool_result(call_id="c1", display="found it")

        messages = [
            core.UserMessage(content="find something"),
            core.AssistantMessage(content="", tool_calls=[tc]),
            core.ToolMessage(tool_name="search", tool_result=tr),
        ]

        result = _load(messages)

        # user + tool entry (assistant with no content is skipped, tool result merged)
        assert len(result) == 2
        tool_msg = result[1]
        assert isinstance(tool_msg, ToolMessage)
        assert _tool(tool_msg).call == tc
        assert _tool(tool_msg).result is not None
        assert _output(tool_msg).display == "found it"
        assert _output(tool_msg).content == {}
        assert _output(tool_msg).is_error is False

    def test_tool_call_with_error_result(self) -> None:
        tc = _make_tool_call(call_id="c1")
        tr = _make_tool_result(call_id="c1", is_error=True, error_message="not found")

        messages = [
            core.AssistantMessage(content="", tool_calls=[tc]),
            core.ToolMessage(tool_name="search", tool_result=tr),
        ]

        result = _load(messages)

        assert len(result) == 1
        assert _output(result[0]).is_error is True
        assert _output(result[0]).error_message == "not found"

    def test_failed_tool_keeps_its_output(self) -> None:
        tc = _make_tool_call(call_id="c1")
        tr = _make_tool_result(call_id="c1", display=None, is_error=True, error_message="not found")

        result = _load(
            [
                core.AssistantMessage(content="", tool_calls=[tc]),
                core.ToolMessage(tool_name="search", tool_result=tr),
            ],
        )

        assert _output(result[0]).is_error is True
        assert _output(result[0]).error_message == "not found"

    def test_multiple_tool_calls_linked(self) -> None:
        tc1 = _make_tool_call(call_id="c1", tool_name="search")
        tc2 = _make_tool_call(call_id="c2", tool_name="read")
        tr1 = _make_tool_result(call_id="c1", display="search result")
        tr2 = _make_tool_result(call_id="c2", display="file content")

        messages = [
            core.AssistantMessage(content="", tool_calls=[tc1, tc2]),
            core.ToolMessage(tool_name="search", tool_result=tr1),
            core.ToolMessage(tool_name="read", tool_result=tr2),
        ]

        result = _load(messages)

        assert len(result) == 2
        assert _output(result[0]).display == "search result"
        assert _output(result[1]).display == "file content"

    def test_result_without_its_call_is_left_out(self) -> None:
        tr = _make_tool_result(call_id="orphan", display="orphan result")

        messages = [
            core.ToolMessage(tool_name="unknown", tool_result=tr),
        ]

        result = _load(messages)

        assert result == []  # A result with no call to show it under is left out.

    def test_assistant_with_content_and_tool_calls(self) -> None:
        tc = _make_tool_call(call_id="c1")
        tr = _make_tool_result(call_id="c1")

        messages = [
            core.AssistantMessage(content="Let me search", tool_calls=[tc]),
            core.ToolMessage(tool_name="search", tool_result=tr),
        ]

        result = _load(messages)

        # assistant text + tool entry
        assert len(result) == 2
        assert isinstance(result[0], AssistantMessage)
        assert _text(result[0]) == "Let me search"
        assert isinstance(result[1], ToolMessage)

    def test_assistant_empty_content_no_tools(self) -> None:
        result = _load([core.AssistantMessage(content="")])

        assert result == []

    def test_assistant_whitespace_only_content_no_tools(self) -> None:
        result = _load([core.AssistantMessage(content="\n\n")])

        assert result == []

    def test_assistant_whitespace_only_content_with_tool_call(self) -> None:
        tc = _make_tool_call(call_id="c1", tool_name="search")

        result = _load([core.AssistantMessage(content="\n\n", tool_calls=[tc])])

        assert len(result) == 1
        assert isinstance(result[0], ToolMessage)
        assert _tool(result[0]).call == tc
