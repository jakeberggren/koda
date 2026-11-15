"""Chat: the conversation, rendered and scrolled."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.layout import HSplit

from koda.messages import AssistantMessage, InterruptionMessage, ToolMessage, UserMessage
from koda.tools import ToolOutput
from koda_tui.appearance import Spacing
from koda_tui.rendering import ToolRun
from koda_tui.ui.primitives import Scroll, ScrollState, Spacer

if TYPE_CHECKING:
    from prompt_toolkit.filters import FilterOrBool
    from prompt_toolkit.formatted_text import StyleAndTextTuples

    from koda.tools import ToolCall
    from koda_tui.rendering import ChatMessage, Renderer
    from koda_tui.state import AppState

    type Calls = dict[str, tuple[int, ToolCall]]  # Calls without an answer yet, and where they are.


class Chat:
    """What the session and the turn hold, as ``chat_messages`` shows them, a blank line apart,
    following the end; the reply being streamed is the last one. ``renderer`` renders them.

    The chat is drawn many times a second while a reply streams, so it keeps each message's
    fragments until the message is gone or the width changes. Messages never change; a message
    with news, like a tool's output, is a new object.
    """

    def __init__(
        self,
        state: AppState,
        renderer: Renderer,
        *,
        scrollbar: FilterOrBool = True,
    ) -> None:
        self._state = state
        self._renderer = renderer
        self._kept: dict[object, tuple[object, int, StyleAndTextTuples]] = {}
        self._container = HSplit(
            [
                Spacer(),
                Scroll(ScrollState(), self.blocks, gap=Spacing.GAP, scrollbar=scrollbar),
            ],
        )

    def __pt_container__(self) -> HSplit:
        return self._container

    def blocks(self, width: int) -> list[StyleAndTextTuples]:
        """Each message's fragments at ``width``, rendered again only if the message is new or the
        width changed."""
        kept, self._kept = self._kept, {}
        blocks: list[StyleAndTextTuples] = []
        for message in chat_messages(self._state):
            key, held = key_of(message)
            entry = kept.get(key)
            if entry is None or entry[0] is not held or entry[1] != width:
                entry = (held, width, self._renderer.render(message, width))
            self._kept[key] = entry
            blocks.append(entry[2])
        return blocks


def chat_messages(state: AppState) -> list[ChatMessage]:
    """What the chat shows: the session's messages, each tool call with its output and
    each failed turn where it failed, then what the turn has so far. Tools the provider
    ran lead the latest turn, as they ran first."""
    shown, calls, start = from_session(state)
    if state.turn.response is not None:
        add_response(shown, calls, state.turn.response)
    for row, call in calls.values():
        shown[row] = ToolRun(call, output_of(call, state))
    shown[start:start] = [
        ToolRun(call, output_of(call, state)) for call in state.turn.provider_calls
    ]
    return shown


def from_session(state: AppState) -> tuple[list[ChatMessage], Calls, int]:  # noqa: C901 - one case per kind of message
    """The session's messages; the calls without an answer yet, by call id, with where their
    message is; and where the latest turn's messages start, after its user message."""
    shown: list[ChatMessage] = []
    calls: Calls = {}
    errors = list(state.errors)
    start = 0
    for index, message in enumerate(state.session.messages):
        while errors and errors[0].at <= index:
            shown.append(errors.pop(0))
        match message:
            case AssistantMessage():
                add_response(shown, calls, message)
            case ToolMessage(tool_result=result):
                if answered := calls.pop(result.call_id, None):
                    row, call = answered
                    shown[row] = ToolRun(call, result.output)
            case UserMessage():
                shown.append(message)
                start = len(shown)
            case InterruptionMessage():
                shown.append(message)
    shown.extend(errors)
    return shown, calls, start


def add_response(shown: list[ChatMessage], calls: Calls, response: AssistantMessage) -> None:
    """The response, unless it is blank, then a message for each tool call it made."""
    if (response.content + response.thinking_content).strip():
        shown.append(response)
    for call in response.tool_calls:
        calls[call.call_id] = (len(shown), call)
        shown.append(ToolRun(call))


NO_OUTPUT = ToolOutput()  # A call whose output wasn't kept.


def output_of(call: ToolCall, state: AppState) -> ToolOutput | None:
    """The output of a call the session doesn't have: ready in the turn, still running, or
    not kept."""
    if result := state.turn.results.get(call.call_id):
        return result.output
    return None if state.turn.running else NO_OUTPUT


def key_of(message: ChatMessage) -> tuple[object, object]:
    """What tells a message apart from the last draw, and the object that must still be the
    same for it to be. A tool run is made again each draw, so it is its call and output;
    any other message is kept in the session, so it is the message itself."""
    if isinstance(message, ToolRun):
        return (message.call.call_id, id(message.output)), message.output
    return id(message), message
