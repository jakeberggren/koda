"""Tests for fitting rendered chat lines to the width."""

from prompt_toolkit.formatted_text import fragment_list_width

from koda_tui.views.chat import _fit


def _text(lines: list) -> list[str]:
    return ["".join(text for _, text, *_ in line) for line in lines]


def test_splits_at_newlines_without_a_trailing_empty_line() -> None:
    assert _text(_fit([("", "one\ntwo\n")], 10)) == ["one", "two"]
    assert _text(_fit([("", "one\n\n")], 10)) == ["one", ""]
    assert _text(_fit([], 10)) == [""]


def test_wraps_lines_that_prompt_toolkit_draws_wider() -> None:
    # Rich measures a skin-toned emoji as 2 columns; prompt_toolkit draws 4.
    lines = _fit([("", "ab👍🏽cd")], 4)
    assert all(fragment_list_width(line) <= 4 for line in lines)
    assert "".join(_text(lines)) == "ab👍🏽cd"


def test_keeps_each_character_style() -> None:
    lines = _fit([("bold", "ab"), ("italic", "cd")], 3)
    assert lines == [[("bold", "a"), ("bold", "b"), ("italic", "c")], [("italic", "d")]]
