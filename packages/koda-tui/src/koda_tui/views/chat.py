"""Chat: the conversation, rendered and scrolled."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.layout import HSplit

from koda_tui.appearance import Spacing
from koda_tui.ui.primitives import Scroll, ScrollState, Spacer

if TYPE_CHECKING:
    from prompt_toolkit.filters import FilterOrBool

    from koda_tui.rendering import MessageRenderer


class Chat:
    """The messages, a blank line apart, following the end; the reply being streamed
    is the last one. ``renderer`` renders them, each once per width.
    """

    def __init__(self, renderer: MessageRenderer, *, scrollbar: FilterOrBool = True) -> None:
        self._container = HSplit(
            [
                Spacer(),
                Scroll(ScrollState(), renderer.render, gap=Spacing.GAP, scrollbar=scrollbar),
            ],
        )

    def __pt_container__(self) -> HSplit:
        return self._container
