"""Screen: the whole of Koda's screen, composed from the other views."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.layout import FloatContainer, HSplit

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

    ``root`` hosts overlays as floats.
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
        self.composer = Composer(
            state,
            on_submit=on_submit,
        )
        self.root = FloatContainer(
            HSplit(
                [
                    self.chat,
                    Spacer(),
                    ActivityIndicator(state),
                    PendingMessages(state),
                    self.composer.suggestions,
                    self.composer,
                    Spacer(),
                    StatusBar(state),
                ],
            ),
            floats=[],
        )

    def __pt_container__(self) -> FloatContainer:
        return self.root
