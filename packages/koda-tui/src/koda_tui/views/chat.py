"""Chat: the conversation, rendered and scrolled."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.layout import HSplit

from koda_tui.appearance import Spacing
from koda_tui.ui.primitives import Scroll, ScrollState, Spacer

if TYPE_CHECKING:
    from prompt_toolkit.filters import FilterOrBool
    from prompt_toolkit.formatted_text import StyleAndTextTuples

    from koda_tui.rendering import Renderer
    from koda_tui.state import AppState, Message


class Chat:
    """The messages, a blank line apart, following the end; the reply being streamed
    is the last one. ``renderer`` renders them.

    The chat is drawn many times a second while a reply streams, so it keeps each
    message's fragments until the message is gone or the width changes. Messages never
    change; a message with news, like a tool's result, is a new object.
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
        self._kept: dict[int, tuple[Message, int, StyleAndTextTuples]] = {}
        self._container = HSplit(
            [
                Spacer(),
                Scroll(ScrollState(), self.blocks, gap=Spacing.GAP, scrollbar=scrollbar),
            ],
        )

    def __pt_container__(self) -> HSplit:
        return self._container

    def blocks(self, width: int) -> list[StyleAndTextTuples]:
        """Each message's fragments at ``width``, rendered again only if the message is
        new or the width changed."""
        kept, self._kept = self._kept, {}
        blocks: list[StyleAndTextTuples] = []
        for message in self._state.messages:
            entry = kept.get(id(message))
            if entry is None or entry[0] is not message or entry[1] != width:
                entry = (message, width, self._renderer.render(message, width))
            self._kept[id(message)] = entry
            blocks.append(entry[2])
        return blocks
