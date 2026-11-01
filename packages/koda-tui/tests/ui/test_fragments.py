"""Tests for fitting, wrapping and truncating fragments."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from prompt_toolkit.formatted_text import fragment_list_width

from koda_tui.ui.fragments import fit, truncate, truncate_text, wrap

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import StyleAndTextTuples


@pytest.mark.parametrize(
    ("width", "expected"),
    [
        (20, [("a", "hello "), ("b", "world")]),
        (11, [("a", "hello "), ("b", "world")]),
        (8, [("a", "hello...")]),
        (9, [("a", "hello "), ("b", "...")]),
        (3, [("a", "...")]),
        (2, [("a", "..")]),
        (0, []),
    ],
)
def test_truncate_keeps_styles_and_adds_an_ellipsis(width: int, expected: list) -> None:
    assert truncate([("a", "hello "), ("b", "world")], width) == expected


@pytest.mark.parametrize(
    ("text", "width", "expected"),
    [("hello", 5, "hello"), ("hello world", 8, "hello..."), ("日本語テキスト", 7, "日本...")],
)
def test_truncate_text_cuts_plain_text_by_cells(text: str, width: int, expected: str) -> None:
    assert truncate_text(text, width) == expected


def test_truncate_ends_with_a_custom_ellipsis() -> None:
    assert truncate([("a", "hello world")], 9, ellipsis="... ·") == [("a", "hell... ·")]


@pytest.mark.parametrize(
    ("width", "expected"),
    [
        (10, [("a", "hello")]),
        (7, [("a", "hello"), ("m", " ·")]),
        (6, [("a", "h"), ("m", "... ·")]),
        (4, [("m", "... ")]),
    ],
)
def test_truncate_ends_crowded_text_with_its_tail(width: int, expected: list) -> None:
    ellipsis: StyleAndTextTuples = [("m", "...")]
    tail: StyleAndTextTuples = [("m", " ·")]
    assert truncate([("a", "hello")], width, ellipsis=ellipsis, tail=tail) == expected


def test_wrap_breaks_between_words_across_styles() -> None:
    fragments: StyleAndTextTuples = [("a", "steering: "), ("b", "keep the tests green")]
    assert wrap(fragments, 20) == [
        [("a", "steering: "), ("b", "keep the")],
        [("b", "tests green")],
    ]


def test_wrap_measures_cells_not_characters() -> None:
    assert wrap([("", "日本 語")], 4) == [[("", "日本")], [("", "語")]]


def test_wrap_breaks_words_wider_than_the_line() -> None:
    assert wrap([("", "a superlative b")], 6) == [
        [("", "a")],
        [("", "superl")],
        [("", "ative")],
        [("", "b")],
    ]


def test_wrap_keeps_text_that_fits_on_one_line() -> None:
    assert wrap([("", "  indented  text")], 40) == [[("", "  indented  text")]]


def _text(lines: list) -> list[str]:
    return ["".join(text for _, text, *_ in line) for line in lines]


def test_fit_splits_at_newlines_without_a_trailing_empty_line() -> None:
    assert _text(fit([("", "one\ntwo\n")], 10)) == ["one", "two"]
    assert _text(fit([("", "one\n\n")], 10)) == ["one", ""]
    assert _text(fit([], 10)) == [""]


def test_fit_keeps_lines_that_fit_exactly_as_they_are() -> None:
    # A raised block's trailing spaces carry its background, so they stay.
    line: StyleAndTextTuples = [("bg", "hi  "), ("bg", "    ")]
    assert fit(line, 8) == [line]


def test_fit_wraps_lines_that_prompt_toolkit_draws_wider() -> None:
    # Rich measures a skin-toned emoji as 2 columns; prompt_toolkit draws 4.
    lines = fit([("", "ab👍🏽cd")], 4)
    assert all(fragment_list_width(line) <= 4 for line in lines)
    assert "".join(_text(lines)) == "ab👍🏽cd"
