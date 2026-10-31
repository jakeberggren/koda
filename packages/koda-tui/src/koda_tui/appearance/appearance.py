"""The current appearance: theme selection and the stylesheet built from it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.styles import DynamicStyle, Style

from koda_tui.appearance.themes import THEMES
from koda_tui.appearance.tokens import Tokens

if TYPE_CHECKING:
    from koda_tui.appearance.themes import RGBColor


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

    def _build(self) -> Style:
        theme = THEMES[self._theme].resolve(self._terminal_background)
        rules = {
            **theme.rules,
            Tokens.Surface.RAISED: f"bg:{theme.surface_on(self._terminal_background)}",
            # prompt_toolkit's own widget classes.
            "frame.border": theme.rules[Tokens.BORDER],
        }
        return Style.from_dict({name.removeprefix("class:"): rule for name, rule in rules.items()})
