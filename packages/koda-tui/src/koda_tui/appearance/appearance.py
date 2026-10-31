"""The current appearance: theme selection and the stylesheet built from it."""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING

from prompt_toolkit.styles import DynamicStyle, Style

from koda_tui.appearance.themes import AUTO_THEME, TERMINAL_DARK, TERMINAL_LIGHT, THEMES
from koda_tui.appearance.tokens import Tokens

if TYPE_CHECKING:
    from koda_tui.appearance.themes import Theme
    from koda_tui.osc import RGBColor

_LUMINANCE_LIGHT_THRESHOLD = 0.5
_SURFACE_BLEND_AMOUNT = 0.125


class Appearance:
    """The current theme and terminal environment as a live prompt_toolkit style.

    Set ``theme`` or ``terminal_background`` and redraw; ``style`` follows.
    """

    def __init__(self, theme: str) -> None:
        self.theme = theme
        self.terminal_background: RGBColor | None = None
        self.style = DynamicStyle(lambda: _stylesheet(self.theme, self.terminal_background))


def _is_light(color: RGBColor) -> bool:
    red, green, blue = color
    # Relative luminance in sRGB space is enough for light/dark background choice.
    luminance = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255
    return luminance >= _LUMINANCE_LIGHT_THRESHOLD


def _select_theme(setting: str, terminal_background: RGBColor | None) -> Theme:
    if setting != AUTO_THEME:
        return THEMES[setting]
    if terminal_background is not None and _is_light(terminal_background):
        return TERMINAL_LIGHT
    return TERMINAL_DARK


def _surface(theme: Theme, terminal_background: RGBColor | None) -> str:
    """Nudge a matching terminal background toward contrast, else use the theme's surface."""
    if (
        not theme.derive_surface
        or terminal_background is None
        or _is_light(terminal_background) == theme.dark
    ):
        return theme.surface
    target = 0 if _is_light(terminal_background) else 255
    red, green, blue = (
        round(channel + (target - channel) * _SURFACE_BLEND_AMOUNT)
        for channel in terminal_background
    )
    return f"#{red:02x}{green:02x}{blue:02x}"


@cache
def _stylesheet(setting: str, terminal_background: RGBColor | None) -> Style:
    theme = _select_theme(setting, terminal_background)
    surface = _surface(theme, terminal_background)
    rules = {
        Tokens.Text.DEFAULT: "",
        Tokens.Text.MUTED: theme.muted,
        Tokens.Text.STRONG: "bold",
        Tokens.Text.EMPHASIS: "italic",
        Tokens.Text.STRIKE: "strike",
        Tokens.Text.ACCENT: theme.accent,
        Tokens.Text.LINK: theme.link,
        Tokens.Text.SUCCESS: theme.success,
        Tokens.Text.WARNING: theme.warning,
        Tokens.Text.ERROR: theme.error,
        Tokens.Text.INFO: theme.info,
        Tokens.Surface.RAISED: f"bg:{surface}",
        Tokens.Surface.SELECTED: f"bg:{theme.accent} fg:{theme.on_accent}",
        Tokens.BORDER: theme.border,
        Tokens.SCROLLBAR: theme.scrollbar,
        Tokens.Heading.H1: "bold underline",
        Tokens.Heading.H2: f"{theme.accent} underline",
        Tokens.Heading.H3: f"{theme.accent} bold",
        Tokens.Heading.H4: f"{theme.accent} italic",
        Tokens.Heading.H5: "italic",
        Tokens.Heading.H6: theme.muted,
        Tokens.Code.INLINE: theme.code,
        Tokens.Diff.ADD: f"bg:{theme.diff_add}",
        Tokens.Diff.REMOVE: f"bg:{theme.diff_remove}",
    }
    # prompt_toolkit's own widget classes.
    widgets = {"frame.border": theme.border}
    return Style.from_dict(
        {name.removeprefix("class:"): rule for name, rule in rules.items()}
        | widgets
        | dict(theme.syntax)
    )
