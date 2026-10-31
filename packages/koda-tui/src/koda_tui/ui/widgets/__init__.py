"""Widgets: reusable pieces composed from primitives."""

from koda_tui.ui.widgets.bar import Bar, Segment
from koda_tui.ui.widgets.dialogs import (
    ChoiceDialog,
    DialogChoice,
    InputDialog,
    MessageDialog,
)
from koda_tui.ui.widgets.panel import Panel

__all__ = [
    "Bar",
    "ChoiceDialog",
    "DialogChoice",
    "InputDialog",
    "MessageDialog",
    "Panel",
    "Segment",
]
