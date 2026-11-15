"""Tests for what the chat shows: the session's messages and the agent's turn as items."""

from __future__ import annotations

from pathlib import Path

from koda.agent import Turn
from koda.llm import LLMError
from koda.messages import AssistantMessage, InterruptionMessage, Message, ToolMessage, UserMessage
from koda.sessions import Session
from koda.tools import ToolCall, ToolOutput, ToolResult
from koda_tui.rendering import ToolRun
from koda_tui.state import AppState, TurnError
from koda_tui.views.chat import NO_OUTPUT, chat_messages

READ = ToolCall(tool_name="read_file", arguments={"path": "a.py"}, call_id="read")
GREP = ToolCall(tool_name="grep", arguments={"pattern": "x"}, call_id="grep")
SEARCH = ToolCall(tool_name="web_search", arguments={"query": "koda"}, call_id="search")


def _state(*messages: Message, turn: Turn | None = None) -> AppState:
    return AppState(
        workspace=Path("/workspace"),
        session=Session(messages=list(messages)),
        turn=turn or Turn(),
    )


def _answer(call: ToolCall, text: str = "ok", *, error: bool = False) -> ToolMessage:
    output = ToolOutput(display=text, is_error=error)
    return ToolMessage(
        tool_name=call.tool_name,
        tool_result=ToolResult(call_id=call.call_id, output=output),
    )


class TestSession:
    def test_messages_are_shown_as_they_are(self) -> None:
        user = UserMessage(content="hi")
        reply = AssistantMessage(content="hello", thinking_content="greeting")
        interruption = InterruptionMessage()

        assert chat_messages(_state(user, reply, interruption)) == [user, reply, interruption]

    def test_a_blank_reply_is_left_out_but_its_calls_are_shown(self) -> None:
        state = _state(AssistantMessage(content=" \n", tool_calls=[READ]), _answer(READ))

        assert chat_messages(state) == [ToolRun(READ, _answer(READ).tool_result.output)]

    def test_each_call_is_shown_with_its_output(self) -> None:
        reply = AssistantMessage(content="Reading", tool_calls=[READ, GREP])
        grep, read = _answer(GREP, "found"), _answer(READ, "file", error=True)

        assert chat_messages(_state(reply, grep, read)) == [
            reply,
            ToolRun(READ, read.tool_result.output),
            ToolRun(GREP, grep.tool_result.output),
        ]

    def test_a_call_whose_output_wasnt_kept_shows_as_done(self) -> None:
        state = _state(AssistantMessage(tool_calls=[READ]))

        assert chat_messages(state) == [ToolRun(READ, NO_OUTPUT)]

    def test_an_output_without_its_call_is_left_out(self) -> None:
        user = UserMessage(content="hi")

        assert chat_messages(_state(user, _answer(READ))) == [user]

    def test_a_failed_turn_is_shown_where_it_failed(self) -> None:
        first, second = UserMessage(content="first"), UserMessage(content="second")
        state = _state(first, second)
        error = TurnError(at=1, error=LLMError("boom"))
        state.errors = [error]

        assert chat_messages(state) == [first, error, second]


class TestTurn:
    def test_the_response_streaming_in_is_last(self) -> None:
        user = UserMessage(content="hi")
        live = AssistantMessage(content="Hel")

        assert chat_messages(_state(user, turn=Turn(running=True, response=live))) == [user, live]

    def test_a_call_runs_until_its_output_is_ready(self) -> None:
        reply = AssistantMessage(tool_calls=[READ, GREP])
        ready = ToolResult(call_id=GREP.call_id, output=ToolOutput(display="found"))
        state = _state(reply, turn=Turn(running=True, results={GREP.call_id: ready}))

        assert chat_messages(state) == [ToolRun(READ), ToolRun(GREP, ready.output)]

    def test_tools_the_provider_ran_lead_the_turn(self) -> None:
        user = UserMessage(content="search")
        live = AssistantMessage(content="Found it")
        turn = Turn(running=True, response=live, provider_calls=[SEARCH])

        assert chat_messages(_state(user, turn=turn)) == [user, ToolRun(SEARCH), live]
