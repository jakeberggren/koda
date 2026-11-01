"""Primitives: the smallest building blocks, each showing one thing.

Being the smallest, they are the pieces that define prompt_toolkit controls; widgets
and views compose them and never define controls of their own.
"""

from koda_tui.ui.primitives.editor import Editor
from koda_tui.ui.primitives.input import Input
from koda_tui.ui.primitives.rows import Lines, Rows
from koda_tui.ui.primitives.scroll import Scroll, ScrollState
from koda_tui.ui.primitives.spacer import Spacer
from koda_tui.ui.primitives.spinner import Spinner
from koda_tui.ui.primitives.text import Overflow, Text

__all__ = [
    "Editor",
    "Input",
    "Lines",
    "Overflow",
    "Rows",
    "Scroll",
    "ScrollState",
    "Spacer",
    "Spinner",
    "Text",
]
