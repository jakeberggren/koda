"""Theme data: the built-in themes and the theme setting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

from pydantic import AfterValidator
from pydantic_core import PydanticCustomError

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class Theme:
    """A named color theme.

    Colors use prompt_toolkit syntax: an ANSI name such as ``ansimagenta`` (resolved
    by the user's terminal palette) or a ``#rrggbb`` hex value.
    """

    name: str
    label: str
    dark: bool
    muted: str
    border: str
    accent: str
    on_accent: str
    link: str
    # Full style for inline code, e.g. "ansicyan bg:ansiblack bold".
    code: str
    success: str
    warning: str
    error: str
    info: str
    surface: str
    diff_add: str
    diff_remove: str
    # prompt_toolkit styles for ``pygments.*`` token classes.
    syntax: Mapping[str, str]


# Rich's ANSI syntax themes as stylesheet entries. Classes inherit from their dotted
# parents, so children of dim tokens reset with ``nodim``.
_ANSI_DARK_SYNTAX = {
    "pygments.text.whitespace": "ansibrightblack",
    "pygments.comment": "dim",
    "pygments.comment.preproc": "nodim ansibrightcyan",
    "pygments.keyword": "ansibrightblue",
    "pygments.keyword.type": "ansibrightcyan",
    "pygments.operator.word": "ansibrightmagenta",
    "pygments.name.builtin": "ansibrightcyan",
    "pygments.name.function": "ansibrightgreen",
    "pygments.name.namespace": "ansibrightcyan underline",
    "pygments.name.class": "ansibrightgreen underline",
    "pygments.name.exception": "ansibrightcyan",
    "pygments.name.decorator": "ansibrightmagenta bold",
    "pygments.name.variable": "ansibrightred",
    "pygments.name.constant": "ansibrightred",
    "pygments.name.attribute": "ansibrightcyan",
    "pygments.name.tag": "ansibrightblue",
    "pygments.literal.string": "ansiyellow",
    "pygments.literal.number": "ansibrightblue",
    "pygments.generic.deleted": "ansibrightred",
    "pygments.generic.inserted": "ansibrightgreen",
    "pygments.generic.heading": "bold",
    "pygments.generic.subheading": "ansibrightmagenta bold",
    "pygments.generic.prompt": "bold",
    "pygments.generic.error": "ansibrightred",
    "pygments.error": "ansired underline",
}

_ANSI_LIGHT_SYNTAX = {
    **_ANSI_DARK_SYNTAX,
    "pygments.text.whitespace": "ansigray",
    "pygments.comment.preproc": "nodim ansicyan",
    "pygments.keyword": "ansiblue",
    "pygments.keyword.type": "ansicyan",
    "pygments.operator.word": "ansimagenta",
    "pygments.name.builtin": "ansicyan",
    "pygments.name.function": "ansigreen",
    "pygments.name.namespace": "ansicyan underline",
    "pygments.name.class": "ansigreen underline",
    "pygments.name.exception": "ansicyan",
    "pygments.name.decorator": "ansimagenta bold",
    "pygments.name.variable": "ansired",
    "pygments.name.constant": "ansired",
    "pygments.name.attribute": "ansicyan",
    "pygments.literal.number": "ansiblue",
    "pygments.generic.inserted": "ansigreen",
    "pygments.generic.subheading": "ansimagenta bold",
}

TERMINAL_DARK = Theme(
    name="terminal-dark",
    label="Terminal Dark",
    dark=True,
    muted="dim",
    border="dim",
    accent="ansimagenta",
    on_accent="ansiwhite",
    link="ansiblue underline",
    code="ansicyan bg:ansiblack bold",
    success="ansigreen",
    warning="ansiyellow",
    error="ansired",
    info="ansicyan",
    surface="#434343",
    diff_add="#005f00",
    diff_remove="#870000",
    syntax=_ANSI_DARK_SYNTAX,
)

TERMINAL_LIGHT = Theme(
    name="terminal-light",
    label="Terminal Light",
    dark=False,
    muted="dim",
    border="dim",
    accent="ansimagenta",
    on_accent="ansiwhite",
    link="ansiblue underline",
    code="ansicyan bg:ansiblack bold",
    success="ansigreen",
    warning="ansiyellow",
    error="ansired",
    info="ansicyan",
    surface="#dcdcdc",
    diff_add="#d4edda",
    diff_remove="#f8d7da",
    syntax=_ANSI_LIGHT_SYNTAX,
)

THEMES: dict[str, Theme] = {theme.name: theme for theme in (TERMINAL_DARK, TERMINAL_LIGHT)}

AUTO_THEME = "auto"


def _validate_theme_setting(value: str) -> str:
    if value != AUTO_THEME and value not in THEMES:
        choices = ", ".join(f"'{name}'" for name in (AUTO_THEME, *THEMES))
        raise PydanticCustomError("theme", "Input should be one of {choices}", {"choices": choices})
    return value


ThemeSetting = Annotated[str, AfterValidator(_validate_theme_setting)]
