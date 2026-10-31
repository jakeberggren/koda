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
from rich.color import Color, ColorType
from rich.console import Console
from rich.segment import Segment
from rich.style import Style
from rich.syntax import SyntaxTheme, TokenType
from rich.theme import Theme

from koda_tui.appearance.tokens import Tokens, compose

if TYPE_CHECKING:
    from rich.console import ConsoleOptions, RenderableType, RenderResult

_CLASS_PREFIX = "class:"

# Rich standard color number → prompt_toolkit color name.
# Note: Rich "white" (7) maps to PT "ansigray", Rich "bright_white" (15) to PT "ansiwhite".
_STANDARD_COLOR_TO_PT = {
    0: "ansiblack",
    1: "ansired",
    2: "ansigreen",
    3: "ansiyellow",
    4: "ansiblue",
    5: "ansimagenta",
    6: "ansicyan",
    7: "ansigray",
    8: "ansibrightblack",
    9: "ansibrightred",
    10: "ansibrightgreen",
    11: "ansibrightyellow",
    12: "ansibrightblue",
    13: "ansibrightmagenta",
    14: "ansibrightcyan",
    15: "ansiwhite",
}

_RICH_ATTR_TO_PT = (
    ("bold", "bold"),
    ("dim", "dim"),
    ("italic", "italic"),
    ("underline", "underline"),
    ("blink", "blink"),
    ("blink2", "blink"),
    ("reverse", "reverse"),
    ("conceal", "hidden"),
    ("strike", "strike"),
)


@cache
def _named(style: str) -> Style:
    """Return a Rich style carrying the tokens in ``style`` as metadata."""
    return Style(meta=dict.fromkeys(style.split(), True))


# Rich's built-in style names, used by Markdown, mapped onto Koda tokens.
_RICH_NAMES = {
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

_THEME = Theme({name: _named(style) for name, style in _RICH_NAMES.items()})


class _Console(Console):
    """Console that resolves token styles (and compositions of them) to metadata."""

    def get_style(self, name: str | Style, *, default: Style | str | None = None) -> Style:
        if isinstance(name, str) and name.startswith(_CLASS_PREFIX):
            return _named(name)
        return super().get_style(name, default=default)


def render(renderable: RenderableType, width: int) -> FormattedText:
    """Render with Rich; tokens come out as prompt_toolkit classes."""
    console = _Console(width=width, theme=_THEME, force_terminal=True, no_color=False)
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


class StyleBlock:
    """Render a renderable with a token applied across full-width lines."""

    def __init__(self, renderable: RenderableType, style: str) -> None:
        self._renderable = renderable
        self._style = style

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        style = console.get_style(self._style)
        new_line = Segment.line()
        for line in console.render_lines(self._renderable, options, style=style, pad=True):
            yield from line
            yield new_line


class _SyntaxTheme(SyntaxTheme):
    """Syntax theme that emits ``pygments.*`` classes instead of colors."""

    def get_style_for_token(self, token_type: TokenType) -> Style:
        return _named(f"{_CLASS_PREFIX}{pygments_token_to_classname(token_type)}")

    def get_background_style(self) -> Style:
        return Style.null()


SYNTAX_THEME = _SyntaxTheme()


def _to_pt_color(color: Color | None) -> str:
    if color is None or color.is_default:
        return ""
    if color.type == ColorType.STANDARD and color.number is not None:
        return _STANDARD_COLOR_TO_PT.get(color.number, "")
    if color.triplet is not None:
        r, g, b = color.triplet
        return f"#{r:02x}{g:02x}{b:02x}"
    if color.type == ColorType.EIGHT_BIT:
        triplet = color.get_truecolor()
        return f"#{triplet.red:02x}{triplet.green:02x}{triplet.blue:02x}"
    return ""


def _to_pt_style(style: Style | None) -> str:
    if style is None:
        return ""
    # Classes first so inline attributes take precedence over the stylesheet.
    parts = [key for key in style.meta if key.startswith(_CLASS_PREFIX)]
    if fg := _to_pt_color(style.color):
        parts.append(fg)
    if bg := _to_pt_color(style.bgcolor):
        parts.append(f"bg:{bg}")
    parts.extend(pt for attr, pt in _RICH_ATTR_TO_PT if getattr(style, attr))
    return " ".join(parts)
