"""Layout composition for Koda TUI."""

from prompt_toolkit.filters import Condition
from prompt_toolkit.layout import (
    ConditionalContainer,
    FloatContainer,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.widgets import Box

from koda_tui.appearance import Tokens
from koda_tui.components import (
    ActivityIndicator,
    ChatAreaControl,
    ChatScrollbarMargin,
    FileSuggestions,
    InputArea,
    QueuedInputs,
    StatusBar,
)
from koda_tui.rendering import MessageRenderer
from koda_tui.state import AppState
from koda_tui.ui.primitives import Spacer

SEPARATOR_HEIGHT = 1


class TUILayout:
    """Manages the TUI layout composition."""

    def __init__(self, state: AppState) -> None:
        self._state = state
        self.renderer = MessageRenderer()

        # Initialize components
        self.chat_area = ChatAreaControl(state, self.renderer)
        self.activity = ActivityIndicator()
        self.queued_inputs = QueuedInputs(state)
        self.input_area = InputArea(state)
        self.file_suggestions = FileSuggestions(self.input_area)
        self.status_bar = StatusBar(state)
        self.root_container: FloatContainer | None = None

    def create_layout(self) -> Layout:
        """Create the full-screen layout."""
        chat_area = Window(
            content=self.chat_area,
            right_margins=[ChatScrollbarMargin(self.chat_area, self._state)],
        )
        activity = ConditionalContainer(
            content=HSplit([self.activity, Spacer()]),
            filter=Condition(lambda: self._state.is_streaming),
        )
        separator = Window(
            height=SEPARATOR_HEIGHT,
            char="",
            style=Tokens.BORDER,
        )
        queued_inputs = self.queued_inputs.create_window()
        file_suggestions = self.file_suggestions.create_window()
        input = self.input_area.create_window()

        # Main layout body. Wrapped in FloatContainer for command palette support
        root_container = FloatContainer(
            content=HSplit(
                [
                    Box(chat_area, padding=0, padding_left=1, padding_top=1),
                    separator,
                    activity,
                    queued_inputs,
                    file_suggestions,
                    input,  # Dynamic height 1-10 lines
                    separator,
                    self.status_bar,  # Fixed 1 line
                ]
            ),
            floats=[],  # Floats added dynamically for palette
        )
        self.root_container = root_container

        return Layout(
            container=root_container,
            focused_element=self.input_area.buffer,
        )
