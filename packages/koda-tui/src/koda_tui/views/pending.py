"""Pending: messages queued while a response is running."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.filters import Condition
from prompt_toolkit.layout import ConditionalContainer, DynamicContainer, HSplit, VSplit, Window

from koda_tui.appearance import Spacing, Tokens, compose
from koda_tui.ui.primitives import Overflow, Text

if TYPE_CHECKING:
    from koda_tui.state import AppState

SHOWN = 3  # Most recent queued messages shown under the count.
TITLE_STYLE = compose(Tokens.Text.MUTED, Tokens.Text.STRONG)
MESSAGE_STYLE = compose(Tokens.Text.MUTED, Tokens.Text.EMPHASIS)


class PendingMessages:
    """While messages are queued: how many, then the latest few, word-wrapped."""

    def __init__(self, state: AppState) -> None:
        self._container = ConditionalContainer(
            VSplit(
                [
                    Window(width=Spacing.INSET),
                    DynamicContainer(lambda: _rows(state.pending_inputs)),
                ],
            ),
            filter=Condition(lambda: bool(state.pending_inputs)),
        )

    def __pt_container__(self) -> ConditionalContainer:
        return self._container


def _rows(pending: list[str]) -> HSplit:
    return HSplit(
        [
            Text(_title(len(pending)), style=TITLE_STYLE, overflow=Overflow.WRAP),
            *(
                Text(message, style=MESSAGE_STYLE, overflow=Overflow.WRAP)
                for message in pending[-SHOWN:]
            ),
        ],
    )


def _title(count: int) -> str:
    messages = "message" if count == 1 else "messages"
    return f"{count} {messages} queued (esc to send now, alt/option-up to edit)"
