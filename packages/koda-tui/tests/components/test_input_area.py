from koda_tui.components.input_area import _wrap_line_ranges


def _display_lines(text: str, width: int) -> list[str]:
    return [text[display_start:end] for _, end, display_start in _wrap_line_ranges(text, width)]


def test_word_after_full_width_word_does_not_render_with_leading_space() -> None:
    """A word moved after a full-width word should not render with a leading space."""
    assert _display_lines("abcde fgh", 5) == ["abcde", "fgh"]


def test_wrap_boundary_space_is_preserved_in_source_range() -> None:
    """The hidden separator should remain part of the source range for cursor mapping."""
    assert _wrap_line_ranges("abcde fgh", 5) == [(0, 5, 0), (5, 9, 6)]


def test_wrap_line_ranges_keep_trailing_space_on_non_full_line() -> None:
    """Only hide spaces that become leading indentation on continuation lines."""
    assert _display_lines("abcd ef", 5) == ["abcd ", "ef"]
