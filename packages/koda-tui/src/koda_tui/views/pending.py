"""Pending: messages waiting while a response is running, steering or queued."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.filters import Condition
from prompt_toolkit.layout import ConditionalContainer
from prompt_toolkit.widgets import Box

from koda_tui.appearance import Spacing, Tokens, compose
from koda_tui.ui.primitives import Overflow, Text

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import StyleAndTextTuples

    from koda_tui.state import AppState

SHOWN = 3  # Most recent queued messages shown under the count.
STEERING = "steering: "
TITLE_STYLE = compose(Tokens.Text.MUTED, Tokens.Text.STRONG)
MESSAGE_STYLE = compose(Tokens.Text.MUTED, Tokens.Text.EMPHASIS)


class PendingMessages:
    """While messages wait: each steer, then how many are queued and the latest few,
    word-wrapped."""

    def __init__(self, state: AppState) -> None:
        self._state = state
        self._container = ConditionalContainer(
            Box(Text(self._lines, overflow=Overflow.WRAP), padding=0, padding_left=Spacing.GAP),
            filter=Condition(self._waiting),
        )

    def __pt_container__(self) -> ConditionalContainer:
        return self._container

    def _waiting(self) -> bool:
        return bool(self._state.pending_inputs)

    def _lines(self) -> StyleAndTextTuples:
        """Each steer, then the queue's count and its latest messages, a line each."""
        pending = self._state.pending_inputs
        steering = [item.text for item in pending if item.steer]
        queued = [item.text for item in pending if not item.steer]
        lines: list[StyleAndTextTuples] = [
            [(TITLE_STYLE, STEERING), (MESSAGE_STYLE, text)] for text in steering
        ]
        if queued:
            lines.append([(TITLE_STYLE, _title(len(queued)))])
            lines += [[(MESSAGE_STYLE, text)] for text in queued[-SHOWN:]]
        return _joined(lines)


def _title(count: int) -> str:
    messages = "message" if count == 1 else "messages"
    return f"{count} {messages} queued (esc to send now, alt/option-up to edit)"


def _joined(lines: list[StyleAndTextTuples]) -> StyleAndTextTuples:
    """``lines`` as one run of fragments, a newline between each."""
    fragments: StyleAndTextTuples = []
    for index, line in enumerate(lines):
        if index:
            fragments.append(("", "\n"))
        fragments += line
    return fragments
