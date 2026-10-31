"""Tests for the chat: messages rendered once per width."""

# ruff: noqa: SLF001 - the render cache is private

from koda_tui.state import AppState, UserMessage
from koda_tui.views import Chat


def test_messages_are_rendered_once_per_width(state: AppState) -> None:
    state.messages = [UserMessage("hi"), UserMessage("there")]
    chat = Chat(state)
    first = chat._blocks(40)
    assert all(a is b for a, b in zip(chat._blocks(40), first, strict=True))
    assert chat._blocks(30)[0] is not first[0]


def test_a_new_message_is_rendered_alongside_the_cached_ones(state: AppState) -> None:
    state.messages = [UserMessage("hi")]
    chat = Chat(state)
    first = chat._blocks(40)[0]
    state.messages = [*state.messages, UserMessage("there")]
    blocks = chat._blocks(40)
    assert blocks[0] is first
    assert len(blocks) == 2
