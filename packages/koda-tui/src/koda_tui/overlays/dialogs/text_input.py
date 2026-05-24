"""Generic text input dialog overlay."""

from __future__ import annotations

import shutil
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
from prompt_toolkit.layout.processors import PasswordProcessor, Processor
from prompt_toolkit.widgets import Box, Frame

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.key_binding import KeyPressEvent
    from prompt_toolkit.layout import AnyContainer


def _calculate_dialog_width() -> int:
    """Return text input dialog width based on the current terminal size."""
    term_width = shutil.get_terminal_size(fallback=(80, 24)).columns
    return max(40, min(60, term_width // 2))


class TextInputDialog:
    """Dialog for single-line text input with optional masking."""

    def __init__(
        self,
        title: str,
        on_submit: Callable[[str], None],
        on_cancel: Callable[[], None],
        *,
        mask_input: bool = False,
        width: int | None = None,
    ) -> None:
        self._title = title
        self._on_submit = on_submit
        self._on_cancel = on_cancel
        self._mask_input = mask_input
        self.preferred_width = width if width is not None else _calculate_dialog_width()

        self.input_buffer = Buffer()
        self._kb = self._create_keybindings()
        self._container = self._build_container()

    def __pt_container__(self) -> AnyContainer:
        return self._container

    @property
    def focus_target(self) -> Buffer:
        """Return the prompt_toolkit target to focus when opened."""
        return self.input_buffer

    def _create_keybindings(self) -> KeyBindings:
        kb = KeyBindings()
        kb.add(Keys.Escape, eager=True)(self._on_escape)
        kb.add(Keys.Enter)(self._on_enter)
        return kb

    def _on_escape(self, _event: KeyPressEvent) -> None:
        self._on_cancel()

    def _on_enter(self, _event: KeyPressEvent) -> None:
        text = self.input_buffer.text.strip()
        if text:
            self._on_submit(text)

    def _build_container(self) -> Frame:
        title_text = Window(
            content=FormattedTextControl(
                text=[("class:dialog.title", self._title)],
            ),
            height=1,
            dont_extend_height=True,
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

        processors: list[Processor] = [PasswordProcessor()] if self._mask_input else []
        input_row = Window(
            content=BufferControl(
                buffer=self.input_buffer,
                key_bindings=self._kb,
                input_processors=processors,
            ),
            height=1,
            dont_extend_height=True,
            style="class:dialog.box",
        )

        body = HSplit([title_row, separator, input_row])
        box = Box(
            body,
            padding_left=2,
            padding_right=2,
            padding_top=1,
            padding_bottom=1,
            style="class:dialog.box",
        )
        return Frame(body=box, style="class:dialog.frame")
