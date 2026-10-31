"""How the TUI looks: themes, design tokens, and the live stylesheet.

- ``Appearance``: the entry point; owns theme state and exposes the app's style.
- ``Tokens``: design tokens for prompt_toolkit fragments and Rich renderables.
- ``appearance.rich``: renders Rich output as fragments styled by those tokens.
"""

from koda_tui.appearance.appearance import Appearance
from koda_tui.appearance.themes import AUTO_THEME, THEMES, Theme, ThemeSetting
from koda_tui.appearance.tokens import Tokens, compose

__all__ = ["AUTO_THEME", "THEMES", "Appearance", "Theme", "ThemeSetting", "Tokens", "compose"]
