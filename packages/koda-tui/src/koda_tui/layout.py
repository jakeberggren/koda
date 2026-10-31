"""Layout composition for Koda TUI."""

from prompt_toolkit.filters import Condition
from prompt_toolkit.layout import (
    ConditionalContainer,
    FloatContainer,
    HSplit,
    Layout,
    Window,
)

from koda_tui.appearance import Tokens
from koda_tui.state import AppState
from koda_tui.ui.primitives import Spacer
from koda_tui.views import (
    ActivityIndicator,
    Chat,
    Composer,
    PendingMessages,
    StatusBar,
)

SEPARATOR_HEIGHT = 1


class TUILayout:
    """Manages the TUI layout composition."""

    def __init__(self, state: AppState) -> None:
        self._state = state
        self.chat = Chat(state)
        self.activity = ActivityIndicator()
        self.pending = PendingMessages(state)
        self.composer = Composer(state)
        self.status_bar = StatusBar(state)
        self.root_container: FloatContainer | None = None

    def create_layout(self) -> Layout:
        """Create the full-screen layout."""
        activity = ConditionalContainer(
            content=HSplit([self.activity, Spacer()]),
            filter=Condition(lambda: self._state.is_streaming),
        )
        separator = Window(
            height=SEPARATOR_HEIGHT,
            char="",
            style=Tokens.BORDER,
        )

        # Main layout body. Wrapped in FloatContainer for command palette support
        root_container = FloatContainer(
            content=HSplit(
                [
                    self.chat,
                    separator,
                    activity,
                    self.pending,
                    self.composer.suggestions,
                    self.composer,  # Grows with its text, up to 10 rows
                    separator,
                    self.status_bar,  # Fixed 1 line
                ]
            ),
            floats=[],  # Floats added dynamically for palette
        )
        self.root_container = root_container

        return Layout(
            container=root_container,
            focused_element=self.composer.buffer,
        )
