"""Layout composition for Koda TUI."""

from prompt_toolkit.layout import (
    FloatContainer,
    FormattedTextControl,
    HSplit,
    Layout,
    VSplit,
    Window,
)
from prompt_toolkit.widgets import Box

from koda_tui.app.state import AppState
from koda_tui.components import ChatAreaControl, ChatScrollbarMargin, InputArea, StatusBarControl
from koda_tui.rendering import RichToPromptToolkit

SEPARATOR_HEIGHT = 1
STATUS_BAR_HEIGHT = 1


class TUILayout:
    """Manages the TUI layout composition."""

    def __init__(self, state: AppState) -> None:
        self._state = state
        self._renderer = RichToPromptToolkit()

        # Initialize components
        self.chat_area = ChatAreaControl(state, self._renderer)
        self.input_area = InputArea()
        self.status_bar = StatusBarControl(state)

    def create_layout(self) -> Layout:
        """Create the full-screen layout."""
        chat_area = Window(
            content=self.chat_area,
            wrap_lines=True,
            style="class:chat-area",
            right_margins=[ChatScrollbarMargin(self.chat_area)],
        )

        separator = Window(
            height=SEPARATOR_HEIGHT,
            char="\u2500",  # Horizontal line character
            style="class:separator",
        )

        input_prompt = Window(
            content=FormattedTextControl(text=[("class:prompt", "❯")]),  # noqa: RUF001 - allow confusable
            width=2,
            dont_extend_width=True,
        )

        input = VSplit([input_prompt, self.input_area.create_window()])

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
