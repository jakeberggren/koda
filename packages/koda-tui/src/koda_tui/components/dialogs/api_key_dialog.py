"""API key input dialog component."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    BufferControl,
    FormattedTextControl,
    HSplit,
    VSplit,
    Window,
    WindowAlign,
)
from prompt_toolkit.layout.processors import PasswordProcessor
from prompt_toolkit.widgets import Box

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.key_binding import KeyPressEvent


class ApiKeyDialog:
    """Dialog for entering an API key with masked input."""

    def __init__(
        self,
        provider: str,
        on_submit: Callable[[str], None],
        on_cancel: Callable[[], None],
    ) -> None:
        self.provider = provider
        self.on_submit = on_submit
        self.on_cancel = on_cancel

        # Input buffer for API key
        self.input_buffer = Buffer()

        # Key bindings
        self._kb = self._create_keybindings()

        # Build container
        self._container = self._build_container()

    def _create_keybindings(self) -> KeyBindings:
        """Create key bindings for dialog."""
        kb = KeyBindings()

        @kb.add(Keys.Escape, eager=True)
        def _cancel(_event: KeyPressEvent) -> None:
            self.on_cancel()

        @kb.add(Keys.Enter)
        def _submit(_event: KeyPressEvent) -> None:
            key = self.input_buffer.text.strip()
            if key:
                self.on_submit(key)

        return kb

    def _build_container(self) -> Box:
        """Build the dialog UI container."""
        title_text = Window(
            content=FormattedTextControl(
                text=[("class:dialog.title", f"Enter {self.provider} API Key")]
            ),
            height=1,
            dont_extend_height=True,
            dont_extend_width=False,
            style="class:dialog.box",
        )

        esc_hint = Window(
            content=FormattedTextControl(text=[("class:dialog.hint", "esc")]),
            height=1,
            width=3,
            dont_extend_height=True,
            dont_extend_width=True,
            align=WindowAlign.RIGHT,
            style="class:dialog.box",
        )

        title_row = VSplit([title_text, esc_hint], style="class:dialog.box")

        separator = Window(height=1, style="class:dialog.box")

        # Input with prompt
        input_row = Window(
            content=BufferControl(
                buffer=self.input_buffer,
                key_bindings=self._kb,
                input_processors=[PasswordProcessor()],
            ),
            height=1,
            dont_extend_height=True,
            style="class:dialog.box",
        )

        body = HSplit([title_row, separator, input_row])

        return Box(
            body,
            padding_left=2,
            padding_right=2,
            padding_top=1,
            padding_bottom=2,
            style="class:dialog.box",
        )

    def __pt_container__(self) -> Box:
        """Return the container for prompt_toolkit."""
        return self._container
