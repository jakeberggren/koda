"""Tests for the Text primitive's truncation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from koda_tui.ui.primitives.text import truncate

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
