"""Sizes shared by every theme, in terminal cells: spacing, and preferred widths and heights."""

from __future__ import annotations


class Spacing:
    GAP = 1  # Blank rows or columns between sections.
    INSET = 2  # Columns of padding inside a panel.
    EDGE = 1  # Columns kept clear at the screen edges.


class Width:
    """Preferred widths; prompt_toolkit shrinks them to fit smaller terminals."""

    SMALL = 60
    MEDIUM = 72
    LARGE = 80


class Height:
    """Heights in rows, for content that grows; prompt_toolkit shrinks them to fit."""

    SMALL = 5
    LARGE = 20
