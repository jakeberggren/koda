"""Prompt widget: the mark in front of where you type."""

from __future__ import annotations

from prompt_toolkit.layout import Dimension, HSplit, Window
from prompt_toolkit.utils import get_cwidth

from koda_tui.appearance import Tokens, compose
from koda_tui.ui.primitives import Text

GLYPH = "❯"  # noqa: RUF001 - the prompt glyph, not a typo for ">"
STYLE = compose(Tokens.Text.ACCENT, Tokens.Text.STRONG)


class Prompt:
    """The prompt glyph on the first row, as wide as itself, and blank rows below it.

    The blank rows fill the column beside taller content, such as a multi-line
    editor, so it takes the surrounding style instead of being left undrawn.
    """

    def __init__(self) -> None:
        self._column = HSplit(
            [
                Text(GLYPH, style=STYLE, fit=True),
                Window(width=Dimension(max=get_cwidth(GLYPH))),
            ],
        )

    def __pt_container__(self) -> HSplit:
        return self._column
