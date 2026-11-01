"""Screen: the whole of Koda's screen, composed from the other views."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.layout import FloatContainer, HSplit
from prompt_toolkit.widgets import Box

from koda_tui.appearance import Spacing
from koda_tui.ui.primitives import Spacer
from koda_tui.views.chat import Chat
from koda_tui.views.composer import Composer
from koda_tui.views.pending import PendingMessages
from koda_tui.views.status import ActivityIndicator, StatusBar

if TYPE_CHECKING:
    from prompt_toolkit.filters import FilterOrBool

    from koda_tui.rendering import MessageRenderer
    from koda_tui.state import AppState
    from koda_tui.views.composer import Submit


class Screen:
    """The chat, then activity, queued messages, the composer and the status bar.

    Everything but the composer is kept ``Spacing.EDGE`` clear of the screen's sides;
    the composer's raised surface runs edge to edge. ``root`` hosts overlays as floats.
    """

    def __init__(
        self,
        state: AppState,
        *,
        renderer: MessageRenderer,
        on_submit: Submit,
        show_scrollbar: FilterOrBool = True,
    ) -> None:
        self.chat = Chat(renderer, scrollbar=show_scrollbar)
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
        self.root = FloatContainer(
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

    def __pt_container__(self) -> FloatContainer:
        return self.root
