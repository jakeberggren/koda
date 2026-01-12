"""Layout composition for Koda TUI."""

from prompt_toolkit.layout import (
    FormattedTextControl,
    HSplit,
    Layout,
    VSplit,
    Window,
)

from koda_tui.app.state import AppState
from koda_tui.components import ChatAreaControl, ChatScrollbarMargin, InputArea, StatusBarControl
from koda_tui.rendering import RichToPromptToolkit


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
        # Chat area
        chat_window = Window(
            content=self.chat_area,
            wrap_lines=True,
            style="class:chat-area",
            right_margins=[ChatScrollbarMargin(self.chat_area)],
        )

        # Separator line
        separator = Window(
            height=1,
            char="\u2500",  # Horizontal line character
            style="class:separator",
        )

        # Input prompt label
        input_prompt = Window(
            content=FormattedTextControl(text=[("class:prompt", "❯")]),  # noqa: RUF001 - allow confusable
            width=2,
            dont_extend_width=True,
        )

        # Input area with prompt
        input_row = VSplit(
            [
                input_prompt,
                self.input_area.create_window(),
            ]
        )

        # Status bar
        status_window = Window(
            content=self.status_bar,
            height=1,
            style="class:status-bar",
        )

        # Main layout
        root = HSplit(
            [
                chat_window,  # Takes remaining space
                separator,
                input_row,  # Dynamic height 1-10 lines
                separator,
                status_window,  # Fixed 1 line
            ]
        )

        return Layout(
            container=root,
            focused_element=self.input_area.buffer,
        )
