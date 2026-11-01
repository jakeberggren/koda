"""Tests for the chat: which messages it renders again, and which it keeps."""

from koda_tui.rendering import Renderer
from koda_tui.state import AppState, UserMessage
from koda_tui.views.chat import Chat


def test_messages_are_rendered_once_per_width(state: AppState) -> None:
    state.messages = [UserMessage("hi"), UserMessage("there")]
    chat = Chat(state, Renderer())
    first = chat.blocks(40)
    assert all(a is b for a, b in zip(chat.blocks(40), first, strict=True))
    assert chat.blocks(30)[0] is not first[0]


def test_a_new_message_is_rendered_alongside_the_kept_ones(state: AppState) -> None:
    state.messages = [UserMessage("hi")]
    chat = Chat(state, Renderer())
    first = chat.blocks(40)[0]
    state.messages = [*state.messages, UserMessage("there")]
    blocks = chat.blocks(40)
    assert blocks[0] is first
    assert len(blocks) == 2


def test_a_message_that_is_gone_is_rendered_again_if_it_comes_back(state: AppState) -> None:
    message = UserMessage("hi")
    state.messages = [message]
    chat = Chat(state, Renderer())
    first = chat.blocks(40)[0]
    state.messages = []
    chat.blocks(40)
    state.messages = [message]
    assert chat.blocks(40)[0] is not first
