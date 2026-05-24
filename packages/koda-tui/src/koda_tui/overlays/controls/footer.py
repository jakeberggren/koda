"""Width-aware wrapped footer text for overlays."""

from __future__ import annotations

from textwrap import wrap
from typing import TYPE_CHECKING, override

from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout import UIContent, UIControl

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.layout.containers import GetLinePrefixCallable


class FooterControl(UIControl):
    """Width-aware wrapped footer text for overlays."""

    def __init__(self, text: StyleAndTextTuples) -> None:
        self._text = text

    def _footer_width(self) -> int:
        return sum(len(fragment[1]) for fragment in self._text)

    def _wrapped_lines(self, width: int) -> list[StyleAndTextTuples]:
        if not self._text:
            return [[("", "")]]
        if self._footer_width() <= width:
            return [self._text]
        if len(self._text) > 1:
            return [self._text]

        style, text, *_ = self._text[0]
        lines = wrap(text, width=max(1, width), break_long_words=False) or [""]
        return [[(style, line)] for line in lines]

    @override
    def preferred_height(
        self,
        width: int,
        max_available_height: int,
        wrap_lines: bool,
        get_line_prefix: GetLinePrefixCallable | None,
    ) -> int | None:
        return min(max_available_height, len(self._wrapped_lines(width)))

    def create_content(self, width: int, height: int) -> UIContent:  # noqa: ARG002
        lines = self._wrapped_lines(width)

        def get_line(i: int) -> FormattedText:
            if 0 <= i < len(lines):
                return FormattedText(lines[i])
            return FormattedText([])

        return UIContent(get_line=get_line, line_count=len(lines))
