"""How the TUI looks: themes, design tokens, and the live stylesheet.

- ``Appearance``: the entry point; owns theme state and exposes the app's style.
- ``Tokens``: design tokens, the class names everything else styles itself with.
- ``Icons``: symbols and marks, the same in every theme.
"""

from koda_tui.appearance.appearance import Appearance
from koda_tui.appearance.icons import Icons
from koda_tui.appearance.sizes import Height, Spacing, Width
from koda_tui.appearance.themes import AUTO, THEMES, AutoTheme, RGBColor, Theme
from koda_tui.appearance.tokens import Tokens, compose

__all__ = [
    "AUTO",
    "THEMES",
    "Appearance",
    "AutoTheme",
    "Height",
    "Icons",
    "RGBColor",
    "Spacing",
    "Theme",
    "Tokens",
    "Width",
    "compose",
]
