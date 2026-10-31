"""Carry prompt_toolkit style classes through Rich rendering.

Rich resolves styles to concrete colors, which would bake the theme into rendered
output. Theme-dependent styling is instead attached as ``Style.meta`` keys, which
survive rendering and merge when styles combine, and is emitted as ``class:`` names
when converting to prompt_toolkit. The stylesheet resolves them at draw time.
"""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING

from prompt_toolkit.styles.pygments import pygments_token_to_classname
from rich.segment import Segment
from rich.style import Style
from rich.syntax import SyntaxTheme, TokenType

if TYPE_CHECKING:
    from rich.console import Console, ConsoleOptions, RenderableType, RenderResult

_CLASS_PREFIX = "class:"


@cache
def style_class(name: str) -> Style:
    """Return a Rich style that renders as the prompt_toolkit class ``name``."""
    return Style(meta={f"{_CLASS_PREFIX}{name}": True})


def style_classes(style: Style) -> list[str]:
    """Return the prompt_toolkit classes attached to a Rich style, outermost first."""
    return [key for key in style.meta if key.startswith(_CLASS_PREFIX)]


class ClassSyntaxTheme(SyntaxTheme):
    """Syntax theme that emits ``pygments.*`` classes instead of colors."""

    def get_style_for_token(self, token_type: TokenType) -> Style:
        return style_class(pygments_token_to_classname(token_type))

    def get_background_style(self) -> Style:
        return Style.null()


SYNTAX_THEME = ClassSyntaxTheme()


class StyleClassBlock:
    """Render a renderable with a style class applied across full-width lines."""

    def __init__(self, renderable: RenderableType, style_name: str) -> None:
        self._renderable = renderable
        self._style = style_class(style_name)

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        new_line = Segment.line()
        for line in console.render_lines(self._renderable, options, style=self._style, pad=True):
            yield from line
            yield new_line
