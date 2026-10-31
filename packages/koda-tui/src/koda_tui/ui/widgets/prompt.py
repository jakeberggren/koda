"""Prompt widget: the mark in front of where you type."""

from __future__ import annotations

from koda_tui.appearance import Tokens, compose
from koda_tui.ui.primitives import Text

GLYPH = "❯"  # noqa: RUF001 - the prompt glyph, not a typo for ">"
STYLE = compose(Tokens.Text.ACCENT, Tokens.Text.STRONG)


class Prompt:
    """The prompt glyph, as wide as itself."""

    def __init__(self) -> None:
        self._text = Text(GLYPH, style=STYLE, fit=True)

    def __pt_container__(self) -> Text:
        return self._text
