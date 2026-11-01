"""Bar widget: one line with segments on the left and on the right."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.layout import VSplit

from koda_tui.appearance import Spacing, Tokens
from koda_tui.ui.primitives import Overflow, Text

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.formatted_text import StyleAndTextTuples

type Segment = StyleAndTextTuples

DIVIDER = " · "
RIGHT_PRIORITY = 100


class Bar:
    """One line: left and right segments, each side joined by a divider.

    The right side gets its full width first; the left side takes what remains and
    is cut short with an ellipsis when it doesn't fit. Both sides are re-read on
    every render.
    """

    def __init__(
        self,
        left: Callable[[], list[Segment]],
        right: Callable[[], list[Segment]],
    ) -> None:
        self._container = VSplit(
            [
                Text(
                    lambda: _join(left()),
                    overflow=Overflow.ELLIPSIS,
                    # Keeps a divider between the sides when they are crowded.
                    tail=[(Tokens.Text.MUTED, DIVIDER.rstrip())],
                ),
                Text(lambda: _join(right()), fit=True, weight=RIGHT_PRIORITY),
            ],
            padding=Spacing.GAP,
            height=1,
        )

    def __pt_container__(self) -> VSplit:
        return self._container


def _join(segments: list[Segment]) -> StyleAndTextTuples:
    """The segments in order, with a divider between each."""
    joined: StyleAndTextTuples = []
    for index, segment in enumerate(segments):
        if index:
            joined.append((Tokens.Text.MUTED, DIVIDER))
        joined.extend(segment)
    return joined
