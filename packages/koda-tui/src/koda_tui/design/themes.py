"""Built-in color themes and theme setting resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

from pydantic import AfterValidator
from pydantic_core import PydanticCustomError

from koda_tui.design.terminal import is_light_background

if TYPE_CHECKING:
    from collections.abc import Mapping

    from koda_tui.osc import RGBColor


@dataclass(frozen=True, slots=True)
class Theme:
    """A named color theme.

    Colors use prompt_toolkit syntax: an ANSI name such as ``ansimagenta`` (resolved
    by the user's terminal palette) or a ``#rrggbb`` hex value.
    """

    name: str
    label: str
    dark: bool
    accent: str
    on_accent: str
    warning: str
    error: str
    info: str
    scrollbar: str
    surface: str
    diff_add: str
    diff_remove: str
    # prompt_toolkit styles for ``pygments.*`` token classes.
    syntax: Mapping[str, str]
    # Derive the surface from the terminal background when it matches this theme.
    derive_surface: bool = False


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
    accent="ansimagenta",
    on_accent="ansiwhite",
    warning="ansiyellow",
    error="ansired",
    info="ansicyan",
    scrollbar="ansiwhite",
    surface="#434343",
    diff_add="#005f00",
    diff_remove="#870000",
    syntax=_ANSI_DARK_SYNTAX,
    derive_surface=True,
)

TERMINAL_LIGHT = Theme(
    name="terminal-light",
    label="Terminal Light",
    dark=False,
    accent="ansimagenta",
    on_accent="ansiwhite",
    warning="ansiyellow",
    error="ansired",
    info="ansicyan",
    scrollbar="ansibrightblack",
    surface="#dcdcdc",
    diff_add="#d4edda",
    diff_remove="#f8d7da",
    syntax=_ANSI_LIGHT_SYNTAX,
    derive_surface=True,
)

THEMES: dict[str, Theme] = {theme.name: theme for theme in (TERMINAL_DARK, TERMINAL_LIGHT)}

AUTO_THEME = "auto"
_DEFAULT_DARK_THEME = TERMINAL_DARK
_DEFAULT_LIGHT_THEME = TERMINAL_LIGHT
# Theme setting values from before named themes existed.
_LEGACY_THEME_NAMES = {"dark": TERMINAL_DARK.name, "light": TERMINAL_LIGHT.name}


def _validate_theme_setting(value: str) -> str:
    value = _LEGACY_THEME_NAMES.get(value, value)
    if value != AUTO_THEME and value not in THEMES:
        choices = ", ".join(f"'{name}'" for name in (AUTO_THEME, *THEMES))
        raise PydanticCustomError("theme", "Input should be one of {choices}", {"choices": choices})
    return value


ThemeSetting = Annotated[str, AfterValidator(_validate_theme_setting)]


def select_theme(setting: str, terminal_background: RGBColor | None) -> Theme:
    """Return the theme for a setting, picking a light or dark theme in auto mode."""
    if setting != AUTO_THEME:
        return THEMES[setting]
    if terminal_background is not None and is_light_background(terminal_background):
        return _DEFAULT_LIGHT_THEME
    return _DEFAULT_DARK_THEME
