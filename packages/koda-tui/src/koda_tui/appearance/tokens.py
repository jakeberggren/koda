"""Design tokens: styles named for their intent, never for a specific component.

Each token is a prompt_toolkit class (``"class:text.muted"``) usable directly in
fragments and ``style=`` arguments, and by Rich renderables through the Rich
bridge. Themes decide how each token looks; components combine tokens with
``compose``.
"""

from __future__ import annotations


class Tokens:
    """Every design token. Themes give each one a rule."""

    class Text:
        DEFAULT = "class:text.default"
        MUTED = "class:text.muted"
        STRONG = "class:text.strong"
        EMPHASIS = "class:text.emphasis"
        STRIKE = "class:text.strike"
        ACCENT = "class:text.accent"
        LINK = "class:text.link"
        SUCCESS = "class:text.success"
        WARNING = "class:text.warning"
        ERROR = "class:text.error"
        INFO = "class:text.info"

    class Surface:
        RAISED = "class:surface.raised"
        SELECTED = "class:surface.selected"

    BORDER = "class:border"
    SCROLLBAR = "class:scrollbar"

    class Heading:
        H1 = "class:heading.h1"
        H2 = "class:heading.h2"
        H3 = "class:heading.h3"
        H4 = "class:heading.h4"
        H5 = "class:heading.h5"
        H6 = "class:heading.h6"

    class Code:
        INLINE = "class:code.inline"

    class Diff:
        ADD = "class:diff.add"
        REMOVE = "class:diff.remove"


def compose(*styles: str) -> str:
    """Combine tokens into one style; later tokens win where they overlap."""
    return " ".join(styles)
