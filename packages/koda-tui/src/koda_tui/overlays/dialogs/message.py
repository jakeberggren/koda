"""Message dialog overlay."""

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
from prompt_toolkit.widgets import Box, Frame

from koda_tui.overlays.controls.wrapped import WrappedTextControl

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.key_binding import KeyPressEvent
    from prompt_toolkit.layout import AnyContainer


def _calculate_dialog_width() -> int:
    """Return message dialog width based on the current terminal size."""
    term_width = shutil.get_terminal_size(fallback=(80, 24)).columns
    return max(48, min(72, term_width // 2))


class MessageDialog:
    """Dialog for showing a non-input message."""

    def __init__(
        self,
        title: str,
        detail: str,
        on_close: Callable[[], None],
        *,
        width: int | None = None,
    ) -> None:
        self._title = title
        self._detail = detail
        self._on_close = on_close
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
        kb.add(Keys.Escape, eager=True)(self._on_close_key)
        kb.add(Keys.Enter)(self._on_close_key)
        return kb

    def _on_close_key(self, _event: KeyPressEvent) -> None:
        self._on_close()

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

        detail_text: StyleAndTextTuples = [
            ("class:dialog.hint", self._detail),
        ]
        detail_row = Window(
            content=WrappedTextControl(detail_text),
            dont_extend_height=True,
            style="class:dialog.box",
        )

        # Hidden buffer for focus (keybindings need a focused BufferControl).
        focus_buffer = Window(
            content=BufferControl(
                buffer=self.input_buffer,
                key_bindings=self._kb,
            ),
            height=0,
            dont_extend_height=True,
        )

        body = HSplit(
            [
                title_row,
                separator,
                detail_row,
                focus_buffer,
            ]
        )
        box = Box(
            body,
            padding_left=2,
            padding_right=2,
            padding_top=1,
            padding_bottom=1,
            style="class:dialog.box",
        )
        return Frame(body=box, style="class:dialog.frame")
