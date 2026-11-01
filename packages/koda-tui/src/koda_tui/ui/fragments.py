"""Fragments: styled text laid out in cells, fitted to a width, wrapped by word, or cut short.

These work on fragments only, never containers, so primitives and rendering share them.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from prompt_toolkit.formatted_text import fragment_list_to_text, fragment_list_width
from prompt_toolkit.formatted_text.utils import split_lines
from prompt_toolkit.utils import get_cwidth

from koda_tui import strings

if TYPE_CHECKING:
    from collections.abc import Iterator

    from prompt_toolkit.formatted_text import StyleAndTextTuples

WORDS = re.compile(r"\s+|\S+")

# What cut text ends with: a string takes the cut text's style; fragments keep their own.
type Ending = str | StyleAndTextTuples


def fit(fragments: StyleAndTextTuples, width: int) -> list[StyleAndTextTuples]:
    """``fragments`` as lines at most ``width`` cells wide: split at newlines, and each
    line that is too wide wrapped by word. Lines that fit are kept exactly as they are,
    trailing spaces and all."""
    lines = [
        fitted
        for line in split_lines(fragments)
        for fitted in ([line] if fragment_list_width(line) <= width else wrap(line, width))
    ]
    if len(lines) > 1 and not fragment_list_to_text(lines[-1]):
        lines.pop()  # The text ended with a newline.
    return lines


def wrap(fragments: StyleAndTextTuples, width: int) -> list[StyleAndTextTuples]:
    """``fragments`` broken into lines at most ``width`` cells wide, between words.

    Whitespace becomes spaces and is dropped where a line breaks; words wider than
    ``width`` are broken between characters.
    """
    lines: list[StyleAndTextTuples] = [[]]
    used = 0
    space = ("", "")  # Whitespace waiting to see if the next word fits.
    for style, token in _tokens(fragments, width):
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


def _tokens(fragments: StyleAndTextTuples, width: int) -> Iterator[tuple[str, str]]:
    """Each word and run of whitespace in ``fragments``, with its style: whitespace as
    spaces, and words wider than ``width`` in pieces that fit."""
    for style, text, *_ in fragments:
        for token in WORDS.findall(text):
            if token.isspace():
                yield style, " " * len(token)
            else:
                yield from ((style, piece) for piece in _pieces(token, width))


def _pieces(word: str, width: int) -> Iterator[str]:
    """``word`` in pieces at most ``width`` cells wide; a character wider than ``width``
    is a piece of its own."""
    piece, used = "", 0
    for char in word:
        if piece and used + get_cwidth(char) > width:
            yield piece
            piece, used = "", 0
        piece += char
        used += get_cwidth(char)
    yield piece


def truncate(
    fragments: StyleAndTextTuples,
    width: int,
    ellipsis: Ending = strings.Common.ELLIPSIS,
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


def truncate_text(text: str, width: int) -> str:
    """``text`` cut short with an ellipsis to fit in ``width`` cells."""
    return fragment_list_to_text(truncate([("", text)], width))


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
