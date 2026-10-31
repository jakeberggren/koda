"""Text primitive: styled text on one line, or word-wrapped."""

from __future__ import annotations

from textwrap import wrap
from typing import TYPE_CHECKING, override

from prompt_toolkit.formatted_text import FormattedText, to_formatted_text
from prompt_toolkit.layout import FormattedTextControl, UIContent, UIControl, Window, WindowAlign

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.layout.containers import GetLinePrefixCallable


class Text:
    """Styled text.

    One line by default; ``wrap=True`` wraps a single fragment by word instead.
    ``content`` is a string, fragments, or a callable returning fragments for text
    that changes between renders. ``fit=True`` makes it only as wide as its text.
    """

    def __init__(  # noqa: PLR0913 - layout options are clearer as keyword arguments.
        self,
        content: str | StyleAndTextTuples | Callable[[], StyleAndTextTuples],
        *,
        style: str = "",
        align: WindowAlign = WindowAlign.LEFT,
        fit: bool = False,
        wrap: bool = False,
        focusable: bool = False,
    ) -> None:
        control = (
            WordWrapControl(content, focusable=focusable)
            if wrap
            else FormattedTextControl(content, focusable=focusable, show_cursor=False)
        )
        self._window = Window(
            control,
            style=style,
            align=align,
            height=None if wrap else 1,
            dont_extend_width=fit,
            dont_extend_height=True,
        )

    def __pt_container__(self) -> Window:
        return self._window


class WordWrapControl(UIControl):
    """Wraps a single fragment by word; several fragments are shown as one line."""

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
        fragments = self._fragments()
        if not fragments:
            return [[("", "")]]
        if len(fragments) > 1 or sum(len(fragment[1]) for fragment in fragments) <= width:
            return [fragments]
        style, text, *_ = fragments[0]
        return [
            [(style, line)]
            for line in wrap(text, width=max(1, width), break_long_words=False) or [""]
        ]

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
