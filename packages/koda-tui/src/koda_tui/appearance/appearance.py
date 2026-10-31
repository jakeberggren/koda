"""The current appearance: theme selection and the stylesheet built from it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.styles import DynamicStyle, Style

from koda_tui.appearance.themes import AUTO_THEME, TERMINAL_DARK, TERMINAL_LIGHT, THEMES
from koda_tui.appearance.tokens import Tokens

if TYPE_CHECKING:
    from koda_tui.appearance.themes import RGBColor, Theme


class Appearance:
    """The current theme and terminal environment as a live prompt_toolkit style.

    Set ``theme`` or ``terminal_background`` and redraw; ``style`` follows.
    """

    def __init__(self, theme: str) -> None:
        self._theme = theme
        self._terminal_background: RGBColor | None = None
        self._stylesheet = self._build()
        self.style = DynamicStyle(lambda: self._stylesheet)

    @property
    def theme(self) -> str:
        """The theme setting: ``"auto"`` or a theme name."""
        return self._theme

    @theme.setter
    def theme(self, theme: str) -> None:
        self._theme = theme
        self._stylesheet = self._build()

    @property
    def terminal_background(self) -> RGBColor | None:
        """The detected terminal background, if the terminal reported one."""
        return self._terminal_background

    @terminal_background.setter
    def terminal_background(self, background: RGBColor | None) -> None:
        self._terminal_background = background
        self._stylesheet = self._build()

    def _current_theme(self) -> Theme:
        if self._theme != AUTO_THEME:
            return THEMES[self._theme]
        background = self._terminal_background
        return TERMINAL_LIGHT if background is not None and background.is_light else TERMINAL_DARK

    def _build(self) -> Style:
        theme = self._current_theme()
        return _stylesheet(theme, theme.surface_on(self._terminal_background))


def _stylesheet(theme: Theme, surface: str) -> Style:
    """Give every token its rule from the theme."""
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
