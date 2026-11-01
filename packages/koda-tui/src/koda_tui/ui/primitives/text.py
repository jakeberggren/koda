"""Text primitive: styled text on one line, word-wrapped, or cut short to fit."""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, override

from prompt_toolkit.formatted_text import FormattedText, fragment_list_width, to_formatted_text
from prompt_toolkit.layout import (
    Dimension,
    FormattedTextControl,
    UIContent,
    UIControl,
    Window,
    WindowAlign,
)

from koda_tui import strings
from koda_tui.ui.fragments import fit, truncate

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.layout.containers import GetLinePrefixCallable

    from koda_tui.ui.fragments import Ending


class Overflow(Enum):
    """What a Text does when it doesn't fit its width."""

    CLIP = auto()  # Cut off at the edge.
    WRAP = auto()  # Break at newlines, and wrap onto more lines by word.
    ELLIPSIS = auto()  # Cut short, ending in the Text's ellipsis ("..." by default).


class Text:
    """Styled text, as many lines as its content (or its wrapping) needs.

    ``content`` is a string, fragments, or a callable returning fragments for text
    that changes between renders. ``fit=True`` makes it only as wide as its text.
    With ``Overflow.ELLIPSIS``, cut text ends with ``ellipsis``, and text that runs up
    to its edge ends with ``tail``.
    ``weight`` is its share when space is handed out next to siblings: a higher
    weight gets its width first.
    """

    def __init__(  # noqa: PLR0913 - layout options are clearer as keyword arguments.
        self,
        content: str | StyleAndTextTuples | Callable[[], StyleAndTextTuples],
        *,
        style: str = "",
        align: WindowAlign = WindowAlign.LEFT,
        fit: bool = False,
        overflow: Overflow = Overflow.CLIP,
        ellipsis: Ending = strings.Common.ELLIPSIS,
        tail: StyleAndTextTuples | None = None,
        focusable: bool = False,
        weight: int = 1,
    ) -> None:
        self._window = Window(
            _control(content, overflow, ellipsis=ellipsis, tail=tail, focusable=focusable),
            style=style,
            align=align,
            width=Dimension(weight=weight),
            dont_extend_width=fit,
            dont_extend_height=True,
        )

    def __pt_container__(self) -> Window:
        return self._window


def _control(
    content: str | StyleAndTextTuples | Callable[[], StyleAndTextTuples],
    overflow: Overflow,
    *,
    ellipsis: Ending,
    tail: StyleAndTextTuples | None,
    focusable: bool,
) -> UIControl:
    match overflow:
        case Overflow.WRAP:
            return WordWrapControl(content, focusable=focusable)
        case Overflow.ELLIPSIS:
            return TruncateControl(content, ellipsis=ellipsis, tail=tail)
        case Overflow.CLIP:
            return FormattedTextControl(content, focusable=focusable, show_cursor=False)


class WordWrapControl(UIControl):
    """Fits fragments to the width: lines break at newlines, and wrap by word."""

    def __init__(
        self,
        content: str | StyleAndTextTuples | Callable[[], StyleAndTextTuples],
        *,
        focusable: bool = False,
    ) -> None:
        self._content = content
        self._focusable = focusable

    def is_focusable(self) -> bool:
        return self._focusable

    def _fragments(self) -> StyleAndTextTuples:
        return to_formatted_text(self._content)

    def _lines(self, width: int) -> list[StyleAndTextTuples]:
        return fit(self._fragments(), max(1, width))

    @override
    def preferred_height(
        self,
        width: int,
        max_available_height: int,
        wrap_lines: bool,
        get_line_prefix: GetLinePrefixCallable | None,
    ) -> int | None:
        return min(max_available_height, len(self._lines(width)))

    def create_content(self, width: int, height: int) -> UIContent:  # noqa: ARG002
        lines = self._lines(width)

        def get_line(i: int) -> FormattedText:
            return FormattedText(lines[i]) if 0 <= i < len(lines) else FormattedText([])

        return UIContent(get_line=get_line, line_count=len(lines))


class TruncateControl(UIControl):
    """Shows one line of fragments, cut short with an ellipsis when it doesn't fit."""

    def __init__(
        self,
        content: str | StyleAndTextTuples | Callable[[], StyleAndTextTuples],
        *,
        ellipsis: Ending = strings.Common.ELLIPSIS,
        tail: StyleAndTextTuples | None = None,
    ) -> None:
        self._content = content
        self._ellipsis = ellipsis
        self._tail = tail or []

    def preferred_width(self, max_available_width: int) -> int:  # noqa: ARG002
        return fragment_list_width(to_formatted_text(self._content))

    @override
    def preferred_height(
        self,
        width: int,
        max_available_height: int,
        wrap_lines: bool,
        get_line_prefix: GetLinePrefixCallable | None,
    ) -> int:
        return 1

    def create_content(self, width: int, height: int) -> UIContent:  # noqa: ARG002
        fragments = to_formatted_text(self._content)
        line = FormattedText(truncate(fragments, width, self._ellipsis, self._tail))
        return UIContent(get_line=lambda i: line if i == 0 else FormattedText([]), line_count=1)
