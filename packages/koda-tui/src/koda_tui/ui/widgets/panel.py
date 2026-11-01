"""Panel widget: a framed box with a title row above its body."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Dimension, HSplit, VSplit
from prompt_toolkit.widgets import Box, Frame

from koda_tui import strings
from koda_tui.appearance import Spacing, Tokens
from koda_tui.ui.primitives import Spacer, Text

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from prompt_toolkit.key_binding import KeyBindingsBase
    from prompt_toolkit.layout import AnyContainer


class Panel:
    """A framed box: a title with a close hint, a gap, then the body.

    Escape calls ``on_close``; ``key_bindings`` apply wherever focus is inside the
    panel. ``width`` is the width it prefers; it shrinks to fit smaller terminals.
    """

    def __init__(
        self,
        title: str,
        body: Sequence[AnyContainer],
        *,
        on_close: Callable[[], None],
        width: int,
        key_bindings: KeyBindingsBase | None = None,
    ) -> None:
        self.key_bindings = _with_escape(on_close, key_bindings)
        content = HSplit([_title_row(title), Spacer(), *body], key_bindings=self.key_bindings)
        self._container = Frame(
            Box(
                content,
                padding=Spacing.GAP,
                padding_left=Spacing.INSET,
                padding_right=Spacing.INSET,
            ),
            width=Dimension(max=width, preferred=width),
        )

    def __pt_container__(self) -> Frame:
        return self._container


def _title_row(title: str) -> VSplit:
    return VSplit(
        [
            Text(title, style=Tokens.Text.STRONG),
            Text(strings.Key.ESC, style=Tokens.Text.MUTED, fit=True),  # Bound in _with_escape.
        ],
    )


def _with_escape(
    on_close: Callable[[], None],
    key_bindings: KeyBindingsBase | None,
) -> KeyBindingsBase:
    escape = KeyBindings()
    escape.add(Keys.Escape, eager=True)(lambda _event: on_close())
    return merge_key_bindings([escape, key_bindings or KeyBindings()])
