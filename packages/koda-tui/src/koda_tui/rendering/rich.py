"""Render Rich renderables as prompt_toolkit fragments styled by design tokens.

Rich resolves styles to concrete colors, which would bake the theme into rendered
output. Instead, tokens (and Rich's built-in Markdown names, mapped onto tokens)
resolve to Rich styles carrying the token names as ``Style.meta``. Meta survives
rendering and merges when styles combine, and is emitted as ``class:`` names, so
the stylesheet resolves them at draw time and rendered output stays theme-free.
"""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING

from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.styles.pygments import pygments_token_to_classname
from rich.console import Console
from rich.segment import Segment
from rich.style import Style
from rich.syntax import Syntax, SyntaxTheme, TokenType

from koda_tui.appearance.tokens import Tokens, compose

if TYPE_CHECKING:
    from rich.console import RenderableType

CLASS_PREFIX = "class:"


def render(renderable: RenderableType, width: int) -> FormattedText:
    """Render with Rich; tokens come out as prompt_toolkit classes."""
    console = _Console(width=width, force_terminal=True, no_color=False)
    segments = console.render(renderable)
    fragments: list[tuple[str, str]] = [
        (_to_pt_style(segment.style), segment.text)
        for line in Segment.split_and_crop_lines(segments, width, pad=False)
        for segment in line
        if not segment.control and segment.text
    ]
    # Strip incidental line breaks emitted by Rich renderables.
    while fragments and fragments[0][1] == "\n":
        fragments.pop(0)
    while fragments and fragments[-1][1] == "\n":
        fragments.pop()
    return FormattedText(fragments)


def syntax(code: str, lexer: str, *, line_numbers: bool = False, start_line: int = 1) -> Syntax:
    """A Syntax renderable highlighted by tokens, over whatever background surrounds it."""
    return Syntax(
        code,
        lexer,
        theme=_SyntaxTheme(),
        background_color="default",
        line_numbers=line_numbers,
        start_line=start_line,
    )


# Rich's built-in style names, used by Markdown, mapped onto Koda tokens.
RICH_NAMES = {
    "markdown.em": Tokens.Text.EMPHASIS,
    "markdown.emph": Tokens.Text.EMPHASIS,
    "markdown.strong": Tokens.Text.STRONG,
    "markdown.s": Tokens.Text.STRIKE,
    "markdown.code": Tokens.Code.INLINE,
    "markdown.code_block": Tokens.Code.INLINE,
    "markdown.kbd": Tokens.Code.INLINE,
    "markdown.block_quote": Tokens.Text.ACCENT,
    "markdown.list": Tokens.Text.INFO,
    "markdown.item.number": Tokens.Text.INFO,
    "markdown.item.bullet": Tokens.Text.STRONG,
    "markdown.hr": Tokens.BORDER,
    "markdown.h1": Tokens.Heading.H1,
    "markdown.h2": Tokens.Heading.H2,
    "markdown.h3": Tokens.Heading.H3,
    "markdown.h4": Tokens.Heading.H4,
    "markdown.h5": Tokens.Heading.H5,
    "markdown.h6": Tokens.Heading.H6,
    "markdown.h7": compose(Tokens.Text.MUTED, Tokens.Text.EMPHASIS),
    "markdown.link": Tokens.Text.LINK,
    "markdown.link_url": Tokens.Text.LINK,
    "markdown.table.border": Tokens.Text.INFO,
    "markdown.table.header": Tokens.Text.INFO,
    # Rich bolds table headers by default; Markdown styles its own headers.
    "table.header": Tokens.Text.DEFAULT,
}


class _Console(Console):
    """Console that resolves tokens, compositions of them, and Rich's names to metadata."""

    def get_style(self, name: str | Style, *, default: Style | str | None = None) -> Style:
        if isinstance(name, str):
            name = RICH_NAMES.get(name, name)  # Rich's own names become tokens.
            if name.startswith(CLASS_PREFIX):
                return _carrying(name)
        return super().get_style(name, default=default)


class _SyntaxTheme(SyntaxTheme):
    """Syntax theme that emits ``pygments.*`` classes instead of colors."""

    def get_style_for_token(self, token_type: TokenType) -> Style:
        return _carrying(f"{CLASS_PREFIX}{pygments_token_to_classname(token_type)}")

    def get_background_style(self) -> Style:
        return Style.null()


@cache
def _carrying(style: str) -> Style:
    """A Rich style that carries the tokens in ``style`` as metadata."""
    return Style(meta=dict.fromkeys(style.split(), True))


def _to_pt_style(style: Style | None) -> str:
    """The tokens a rendered style carries; all styling comes from tokens, not Rich."""
    if style is None:
        return ""
    return " ".join(key for key in style.meta if key.startswith(CLASS_PREFIX))
