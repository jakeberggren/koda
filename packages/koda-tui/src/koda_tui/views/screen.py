"""Screen: the whole of Koda's screen, composed from the other views."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.layout import FloatContainer, HSplit, Layout
from prompt_toolkit.widgets import Box

from koda_tui.appearance import Spacing
from koda_tui.rendering import Renderer
from koda_tui.ui.overlays import Overlays
from koda_tui.ui.primitives import Spacer
from koda_tui.views.chat import Chat
from koda_tui.views.composer import Composer
from koda_tui.views.pending import PendingMessages
from koda_tui.views.status import ActivityIndicator, StatusBar

if TYPE_CHECKING:
    from prompt_toolkit.filters import FilterOrBool

    from koda_tui.state import AppState
    from koda_tui.views.composer import Submit


class Screen:
    """The chat, then activity, queued messages, the composer and the status bar.

    Everything but the composer is kept ``Spacing.EDGE`` clear of the screen's sides;
    the composer's raised surface runs edge to edge. ``layout`` starts with the
    composer focused; ``overlays`` open above it all, and give focus back to the
    composer when they close.
    """

    def __init__(
        self,
        state: AppState,
        *,
        on_submit: Submit,
        show_scrollbar: FilterOrBool = True,
    ) -> None:
        self.chat = Chat(state, Renderer(), scrollbar=show_scrollbar)
        self.composer = Composer(state, on_submit=on_submit)
        conversation = HSplit(
            [
                self.chat,
                Spacer(),
                ActivityIndicator(state),
                PendingMessages(state),
                self.composer.suggestions,
            ],
        )
        self._root = FloatContainer(
            HSplit(
                [
                    Box(
                        conversation,
                        padding=0,
                        padding_left=Spacing.EDGE,
                        padding_right=Spacing.EDGE,
                    ),
                    self.composer,
                    Spacer(),
                    Box(
                        StatusBar(state),
                        padding=0,
                        padding_left=Spacing.EDGE,
                        padding_right=Spacing.EDGE,
                    ),
                ],
            ),
            floats=[],
        )
        self.layout = Layout(self, focused_element=self.composer.buffer)
        self.overlays = Overlays(self._root, fallback=self.composer.buffer)

    def __pt_container__(self) -> FloatContainer:
        return self._root
