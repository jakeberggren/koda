"""Theme data: colors, the built-in themes, and the theme setting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, NamedTuple

from pydantic import AfterValidator
from pydantic_core import PydanticCustomError

from koda_tui.appearance.tokens import Tokens

if TYPE_CHECKING:
    from collections.abc import Mapping

# Relative luminance at or above which a background reads as light.
_LIGHT_LUMINANCE = 0.5


class RGBColor(NamedTuple):
    """An 8-bit RGB color, such as a detected terminal background."""

    red: int
    green: int
    blue: int

    @property
    def is_light(self) -> bool:
        """Whether the color reads as a light background."""
        # Relative luminance in sRGB space is enough for light/dark background choice.
        luminance = (0.2126 * self.red + 0.7152 * self.green + 0.0722 * self.blue) / 255
        return luminance >= _LIGHT_LUMINANCE

    @property
    def hex(self) -> str:
        """The color as ``#rrggbb``."""
        return f"#{self.red:02x}{self.green:02x}{self.blue:02x}"

    def blend(self, target: RGBColor, amount: float) -> RGBColor:
        """Move ``amount`` (0 to 1) of the way toward ``target``."""
        red, green, blue = (
            round(channel + (goal - channel) * amount)
            for channel, goal in zip(self, target, strict=True)
        )
        return RGBColor(red, green, blue)


BLACK = RGBColor(0, 0, 0)
WHITE = RGBColor(255, 255, 255)

# How far a derived surface moves from the terminal background toward contrast.
_SURFACE_CONTRAST = 0.125


@dataclass(frozen=True, slots=True)
class Theme:
    """A named theme: the prompt_toolkit style rule for every token.

    Colors use prompt_toolkit syntax: an ANSI name such as ``ansimagenta`` (resolved
    by the user's terminal palette) or a ``#rrggbb`` hex value.
    """

    name: str
    label: str
    description: str
    dark: bool
    surface: str  # Fallback background for ``Tokens.Surface.RAISED``.
    rules: Mapping[str, str]  # Token (or ``pygments.*`` class) to style rule.

    def surface_on(self, background: RGBColor | None) -> str:
        """This theme's surface, derived from a matching terminal background when known."""
        if background is None or background.is_light == self.dark:
            return self.surface
        contrast = BLACK if background.is_light else WHITE
        return background.blend(contrast, _SURFACE_CONTRAST).hex


TERMINAL_DARK = Theme(
    name="terminal-dark",
    label="Terminal Dark",
    description="Terminal colors for dark backgrounds",
    dark=True,
    surface="#434343",
    rules={
        Tokens.Text.DEFAULT: "",
        Tokens.Text.MUTED: "dim",
        Tokens.Text.STRONG: "bold",
        Tokens.Text.EMPHASIS: "italic",
        Tokens.Text.STRIKE: "strike",
        Tokens.Text.ACCENT: "ansimagenta",
        Tokens.Text.LINK: "ansiblue underline",
        Tokens.Text.SUCCESS: "ansigreen",
        Tokens.Text.WARNING: "ansiyellow",
        Tokens.Text.ERROR: "ansired",
        Tokens.Text.INFO: "ansicyan",
        Tokens.Surface.SELECTED: "bg:ansimagenta fg:ansiwhite",
        Tokens.BORDER: "dim",
        Tokens.Heading.H1: "bold underline",
        Tokens.Heading.H2: "ansimagenta underline",
        Tokens.Heading.H3: "ansimagenta bold",
        Tokens.Heading.H4: "ansimagenta italic",
        Tokens.Heading.H5: "italic",
        Tokens.Heading.H6: "dim",
        Tokens.Code.INLINE: "ansicyan bg:ansiblack bold",
        Tokens.Diff.ADD: "bg:#005f00",
        Tokens.Diff.REMOVE: "bg:#870000",
        # Syntax highlighting, matching Rich's ANSI themes. Classes inherit from their
        # dotted parents, so children of dim tokens reset with nodim.
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
    },
)

TERMINAL_LIGHT = Theme(
    name="terminal-light",
    label="Terminal Light",
    description="Terminal colors for light backgrounds",
    dark=False,
    surface="#dcdcdc",
    rules={
        Tokens.Text.DEFAULT: "",
        Tokens.Text.MUTED: "dim",
        Tokens.Text.STRONG: "bold",
        Tokens.Text.EMPHASIS: "italic",
        Tokens.Text.STRIKE: "strike",
        Tokens.Text.ACCENT: "ansimagenta",
        Tokens.Text.LINK: "ansiblue underline",
        Tokens.Text.SUCCESS: "ansigreen",
        Tokens.Text.WARNING: "ansiyellow",
        Tokens.Text.ERROR: "ansired",
        Tokens.Text.INFO: "ansicyan",
        Tokens.Surface.SELECTED: "bg:ansimagenta fg:ansiwhite",
        Tokens.BORDER: "dim",
        Tokens.Heading.H1: "bold underline",
        Tokens.Heading.H2: "ansimagenta underline",
        Tokens.Heading.H3: "ansimagenta bold",
        Tokens.Heading.H4: "ansimagenta italic",
        Tokens.Heading.H5: "italic",
        Tokens.Heading.H6: "dim",
        Tokens.Code.INLINE: "ansicyan bg:ansiblack bold",
        Tokens.Diff.ADD: "bg:#d4edda",
        Tokens.Diff.REMOVE: "bg:#f8d7da",
        # Syntax highlighting, matching Rich's ANSI themes. Classes inherit
        # from their dotted parents, so children of dim tokens reset with nodim.
        "pygments.text.whitespace": "ansigray",
        "pygments.comment": "dim",
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
        "pygments.name.tag": "ansibrightblue",
        "pygments.literal.string": "ansiyellow",
        "pygments.literal.number": "ansiblue",
        "pygments.generic.deleted": "ansibrightred",
        "pygments.generic.inserted": "ansigreen",
        "pygments.generic.heading": "bold",
        "pygments.generic.subheading": "ansimagenta bold",
        "pygments.generic.prompt": "bold",
        "pygments.generic.error": "ansibrightred",
        "pygments.error": "ansired underline",
    },
)

THEMES: dict[str, Theme] = {theme.name: theme for theme in (TERMINAL_DARK, TERMINAL_LIGHT)}

AUTO_THEME = "auto"


def _validate_theme_setting(value: str) -> str:
    if value != AUTO_THEME and value not in THEMES:
        choices = ", ".join(f"'{name}'" for name in (AUTO_THEME, *THEMES))
        raise PydanticCustomError("theme", "Input should be one of {choices}", {"choices": choices})
    return value


ThemeSetting = Annotated[str, AfterValidator(_validate_theme_setting)]
