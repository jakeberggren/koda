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

from koda_tui.components import (
    ChatAreaControl,
    ChatScrollbarMargin,
    FileSuggestions,
    InputArea,
    QueuedInputs,
    ResponseIndicatorControl,
    StatusBarControl,
)
from koda_tui.rendering import MessageRenderer
from koda_tui.state import AppState

SEPARATOR_HEIGHT = 1
RESPONSE_INDICATOR_HEIGHT = 2
STATUS_BAR_HEIGHT = 1


class TUILayout:
    """Manages the TUI layout composition."""

    def __init__(self, state: AppState) -> None:
        self._state = state
        self.renderer = MessageRenderer()

        # Initialize components
        self.chat_area = ChatAreaControl(state, self.renderer)
        self.response_indicator = ResponseIndicatorControl(state, self.renderer)
        self.queued_inputs = QueuedInputs(state)
        self.input_area = InputArea(state)
        self.file_suggestions = FileSuggestions(self.input_area)
        self.status_bar = StatusBarControl(state)

    def create_layout(self) -> Layout:
        """Create the full-screen layout."""
        chat_area = Window(
            content=self.chat_area,
            style="class:chat-area",
            right_margins=[ChatScrollbarMargin(self.chat_area, self._state)],
        )
        response_indicator = ConditionalContainer(
            content=Window(
                content=self.response_indicator,
                height=RESPONSE_INDICATOR_HEIGHT,
                style="class:status-bar",
            ),
            filter=Condition(lambda: self._state.is_streaming),
        )
        separator = Window(
            height=SEPARATOR_HEIGHT,
            char="",
            style="class:separator",
        )
        queued_inputs = self.queued_inputs.create_window()
        file_suggestions = self.file_suggestions.create_window()
        input = self.input_area.create_window()
        status_bar = Window(
            content=self.status_bar,
            height=STATUS_BAR_HEIGHT,
            style="class:status-bar",
        )

        # Main layout body. Wrapped in FloatContainer for command palette support
        self.root_container = FloatContainer(
            content=HSplit(
                [
                    Box(chat_area, padding=0, padding_left=1, padding_top=1),
                    separator,
                    response_indicator,
                    queued_inputs,
                    file_suggestions,
                    input,  # Dynamic height 1-10 lines
                    separator,
                    status_bar,  # Fixed 1 line
                ]
            ),
            floats=[],  # Floats added dynamically for palette
        )

        return Layout(
            container=self.root_container,
            focused_element=self.input_area.buffer,
        )
