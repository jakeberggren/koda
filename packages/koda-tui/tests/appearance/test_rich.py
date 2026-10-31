"""Tests for the Rich bridge: Rich output styled by tokens."""

from rich.markdown import Markdown
from rich.text import Text

from koda_tui.appearance import Tokens, compose, rich


def test_rich_and_prompt_toolkit_share_style_names() -> None:
    fragments = rich.render(Text("x", style=Tokens.Text.MUTED), width=10)

    assert list(fragments) == [(Tokens.Text.MUTED, "x")]


def test_rich_markdown_styles_render_as_style_names() -> None:
    fragments = rich.render(Markdown("`code`"), width=10)

    assert (Tokens.Code.INLINE, "code") in fragments


def test_rich_resolves_composed_tokens() -> None:
    muted_emphasis = compose(Tokens.Text.MUTED, Tokens.Text.EMPHASIS)
    fragments = rich.render(Text("x", style=muted_emphasis), width=10)

    assert list(fragments) == [(muted_emphasis, "x")]
