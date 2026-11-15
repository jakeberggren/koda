"""Tests for the chat: which rows it renders again, and which it keeps."""

from koda.messages import AssistantMessage, UserMessage
from koda.tools import ToolCall
from koda_tui.rendering import Renderer
from koda_tui.state import AppState
from koda_tui.views.chat import Chat


def test_rows_are_rendered_once_per_width(state: AppState) -> None:
    state.session.messages = [UserMessage(content="hi"), UserMessage(content="there")]
    chat = Chat(state, Renderer())
    first = chat.blocks(40)
    assert all(a is b for a, b in zip(chat.blocks(40), first, strict=True))
    assert chat.blocks(30)[0] is not first[0]


def test_a_new_message_is_rendered_alongside_the_kept_ones(state: AppState) -> None:
    state.session.messages = [UserMessage(content="hi")]
    chat = Chat(state, Renderer())
    first = chat.blocks(40)[0]
    state.session.add(UserMessage(content="there"))
    blocks = chat.blocks(40)
    assert blocks[0] is first
    assert len(blocks) == 2


def test_a_message_that_is_gone_is_rendered_again_if_it_comes_back(state: AppState) -> None:
    message = UserMessage(content="hi")
    state.session.messages = [message]
    chat = Chat(state, Renderer())
    first = chat.blocks(40)[0]
    state.session.messages = []
    chat.blocks(40)
    state.session.messages = [message]
    assert chat.blocks(40)[0] is not first


def test_a_tool_row_is_kept_until_its_output_changes(state: AppState) -> None:
    call = ToolCall(tool_name="read_file", arguments={"path": "a.py"}, call_id="read")
    state.session.messages = [AssistantMessage(tool_calls=[call])]
    chat = Chat(state, Renderer())
    first = chat.blocks(40)[0]
    assert chat.blocks(40)[0] is first
