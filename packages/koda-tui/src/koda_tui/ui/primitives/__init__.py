"""Primitives: building blocks that render one thing directly."""

from koda_tui.ui.primitives.editor import Editor
from koda_tui.ui.primitives.input import Input
from koda_tui.ui.primitives.list import List, ListItem, ListState
from koda_tui.ui.primitives.scroll import Scroll, ScrollState
from koda_tui.ui.primitives.spacer import Spacer
from koda_tui.ui.primitives.spinner import Spinner
from koda_tui.ui.primitives.text import Overflow, Text

__all__ = [
    "Editor",
    "Input",
    "List",
    "ListItem",
    "ListState",
    "Overflow",
    "Scroll",
    "ScrollState",
    "Spacer",
    "Spinner",
    "Text",
]
