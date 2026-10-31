"""Text primitive: styled text on one line, word-wrapped, or cut short to fit."""

from __future__ import annotations

import re
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
from prompt_toolkit.utils import get_cwidth

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.layout.containers import GetLinePrefixCallable


ELLIPSIS = "..."
WORDS = re.compile(r"\s+|\S+")

# What cut text ends with: a string takes the cut text's style; fragments keep their own.
type Ending = str | StyleAndTextTuples


class Overflow(Enum):
    """What a Text does when it doesn't fit its width."""

    CLIP = auto()  # Cut off at the edge.
    WRAP = auto()  # Wrap onto more lines, by word.
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
        ellipsis: Ending = ELLIPSIS,
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
    """Wraps fragments by word, keeping their styles."""

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
        return wrap(fragments, max(1, width))

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
        ellipsis: Ending = ELLIPSIS,
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


def wrap(fragments: StyleAndTextTuples, width: int) -> list[StyleAndTextTuples]:
    """``fragments`` broken into lines at most ``width`` cells wide, between words.

    Whitespace becomes spaces and is dropped where a line breaks; words wider than
    ``width`` get a line of their own and run past it.
    """
    lines: list[StyleAndTextTuples] = [[]]
    used = 0
    space = ("", "")  # Whitespace waiting to see if the next word fits.
    for style, token in _tokens(fragments):
        if token.isspace():
            # Leading whitespace shows only on the first line.
            space = (style, token) if used or len(lines) == 1 else ("", "")
            continue
        if used and used + len(space[1]) + get_cwidth(token) > width:
            lines.append([])
            used = 0
        else:
            lines[-1].append(space)
            used += len(space[1])
        space = ("", "")
        lines[-1].append((style, token))
        used += get_cwidth(token)
    return [_tidy(line) for line in lines]


def _tokens(fragments: StyleAndTextTuples) -> Iterator[tuple[str, str]]:
    """Each word and run of whitespace in ``fragments``, with its style; whitespace
    becomes spaces."""
    for style, text, *_ in fragments:
        for token in WORDS.findall(text):
            yield style, " " * len(token) if token.isspace() else token


def truncate(
    fragments: StyleAndTextTuples,
    width: int,
    ellipsis: Ending = ELLIPSIS,
    tail: StyleAndTextTuples | None = None,
) -> StyleAndTextTuples:
    """Fit ``fragments`` in ``width``, keeping their styles.

    Text with more room to spare than ``tail`` is wide shows as is. Text that runs
    up to its edge ends with ``tail``; text that doesn't fit is cut short and ends
    with ``ellipsis``, then ``tail``.
    """
    tail = tail or []
    spare = width - fragment_list_width(fragments)
    if not fragments or spare > fragment_list_width(tail):
        return fragments
    if spare == fragment_list_width(tail):
        return [*fragments, *tail]
    ending = fragment_list_width(_styled(ellipsis, fragments[0][0])) + fragment_list_width(tail)
    if width <= ending:
        return _tidy(_cut([*_styled(ellipsis, fragments[0][0]), *tail], width, ""))
    return _tidy([*_cut(fragments, width - ending, ellipsis), *tail])


def _cut(fragments: StyleAndTextTuples, room: int, ellipsis: Ending) -> StyleAndTextTuples:
    """The fragments up to ``room`` cells, then ``ellipsis``.

    A string ellipsis takes the style of the text it cuts into; fragments keep their own.
    """
    kept: StyleAndTextTuples = []
    used = 0
    for style, text, *_ in fragments:
        for index, char in enumerate(text):
            if used + get_cwidth(char) > room:
                return [*kept, (style, text[:index]), *_styled(ellipsis, style)]
            used += get_cwidth(char)
        kept.append((style, text))
    return kept


def _tidy(fragments: StyleAndTextTuples) -> StyleAndTextTuples:
    """``fragments`` without empty ones, neighbours with the same style joined."""
    tidy: StyleAndTextTuples = []
    for style, text, *_ in fragments:
        if not text:
            continue
        if tidy and tidy[-1][0] == style:
            tidy[-1] = (style, tidy[-1][1] + text)
        else:
            tidy.append((style, text))
    return tidy


def _styled(ending: Ending, style: str) -> StyleAndTextTuples:
    """``ending`` as fragments: a string in ``style``, or fragments as they are."""
    return [(style, ending)] if isinstance(ending, str) else list(ending)
