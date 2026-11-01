"""Pending: messages waiting while a response is running, steering or queued."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.filters import Condition
from prompt_toolkit.layout import ConditionalContainer, DynamicContainer, HSplit
from prompt_toolkit.widgets import Box

from koda_tui.appearance import Spacing, Tokens, compose
from koda_tui.ui.primitives import Overflow, Text

if TYPE_CHECKING:
    from koda_tui.state import AppState, PendingInput

SHOWN = 3  # Most recent queued messages shown under the count.
STEERING = "steering: "
TITLE_STYLE = compose(Tokens.Text.MUTED, Tokens.Text.STRONG)
MESSAGE_STYLE = compose(Tokens.Text.MUTED, Tokens.Text.EMPHASIS)


class PendingMessages:
    """While messages wait: each steer, then how many are queued and the latest few,
    word-wrapped."""

    def __init__(self, state: AppState) -> None:
        self._container = ConditionalContainer(
            # Indented from the chat: waiting, not sent.
            Box(
                DynamicContainer(lambda: _rows(state.pending_inputs)),
                padding=0,
                padding_left=Spacing.GAP,
            ),
            filter=Condition(lambda: bool(state.pending_inputs)),
        )

    def __pt_container__(self) -> ConditionalContainer:
        return self._container


def _rows(pending: list[PendingInput]) -> HSplit:
    steering = [item.text for item in pending if item.steer]
    queued = [item.text for item in pending if not item.steer]
    rows = [
        Text([(TITLE_STYLE, STEERING), (MESSAGE_STYLE, text)], overflow=Overflow.WRAP)
        for text in steering
    ]
    if queued:
        rows.append(Text(_title(len(queued)), style=TITLE_STYLE, overflow=Overflow.WRAP))
        rows += [
            Text(text, style=MESSAGE_STYLE, overflow=Overflow.WRAP) for text in queued[-SHOWN:]
        ]
    return HSplit(rows)


def _title(count: int) -> str:
    messages = "message" if count == 1 else "messages"
    return f"{count} {messages} queued (esc to send now, alt/option-up to edit)"
