"""Sizes shared by every theme, in terminal cells: spacing and preferred widths."""

from __future__ import annotations


class Spacing:
    GAP = 1  # Blank rows between sections.
    INSET = 2  # Columns of padding inside a panel.


class Width:
    """Preferred widths; prompt_toolkit shrinks them to fit smaller terminals."""

    SMALL = 60
    MEDIUM = 72
    LARGE = 80
