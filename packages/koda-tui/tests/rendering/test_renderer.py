"""Tests for the renderer: what messages look like, their styles, and the cache."""

from prompt_toolkit.formatted_text import FormattedText
from rich.padding import Padding

from koda.tools import ToolCall
from koda_tui.appearance import Tokens
from koda_tui.rendering import MessageRenderer
from koda_tui.rendering import rich as rich_bridge
from koda_tui.rendering.diff import diff_blocks
from koda_tui.rendering.markdown import Markdown
from koda_tui.rendering.renderer import message_renderable
from koda_tui.rendering.rich import render
from koda_tui.state import (
    AppState,
    AssistantMessage,
    ErrorMessage,
    Message,
    ToolMessage,
    UserMessage,
)

WIDTH = 80


def render_message(message: Message, width: int) -> FormattedText:
    return render(message_renderable(message), width)


class TestMessages:
    """Tests for message rendering."""

    def test_render_user_message(self) -> None:
        """render_message() should render user messages as markdown."""
        message = UserMessage("Hello")
        result = render_message(message, WIDTH)
        content = "".join(t[1] for t in result)
        assert "Hello" in content
        assert any(Tokens.Surface.RAISED in fragment[0] for fragment in result)

    def test_render_assistant_message(self) -> None:
        """render_message() should render assistant messages as markdown."""
        message = AssistantMessage("I can help")
        result = render_message(message, WIDTH)
        content = "".join(t[1] for t in result)
        assert "I can help" in content

    def test_render_assistant_message_with_thinking(self) -> None:
        """render_message() should keep persisted thinking content visible."""
        message = AssistantMessage("I can help", thinking="Comparing options")
        result = render_message(message, WIDTH)
        content = "".join(t[1] for t in result)
        assert "Comparing options" in content
        assert "I can help" in content
        lines = [line.rstrip() for line in content.splitlines()]
        assert lines[:3] == ["Comparing options", "", "I can help"]

    def test_render_assistant_thinking_renders_markdown(self) -> None:
        """thinking content should be rendered through markdown, not as literal markers."""
        message = AssistantMessage("", thinking="**Exploring the meaning of 42**")
        result = render_message(message, WIDTH)
        content = "".join(t[1] for t in result)
        assert "Exploring the meaning of 42" in content
        assert "**Exploring the meaning of 42**" not in content

    def test_render_tool_message(self) -> None:
        """render_message() should render tool messages."""
        tool_call = ToolCall(
            tool_name="search",
            arguments={"query": "test"},
            call_id="call_123",
        )
        message = ToolMessage(tool_call)
        result = render_message(message, WIDTH)
        content = "".join(t[1] for t in result)
        assert "search" in content

    def test_render_error_message(self) -> None:
        """An error shows its summary in bold above its detail."""
        result = render_message(ErrorMessage("Rate limit exceeded.", "Try again later."), WIDTH)
        lines = [line.rstrip() for line in "".join(t[1] for t in result).splitlines()]
        assert lines == ["Rate limit exceeded.", "", "Try again later."]
        assert any(
            "Rate limit" in text and Tokens.Text.STRONG in style for style, text, *_ in result
        )

    def test_render_error_without_detail_says_what_to_do(self) -> None:
        result = render_message(ErrorMessage("Not set up."), WIDTH)
        assert "Complete the required setup and try again." in "".join(t[1] for t in result)


class TestStyleClasses:
    """Theme-dependent styling is emitted as style classes, not baked-in colors."""

    def test_code_block_emits_pygments_classes(self) -> None:
        message = AssistantMessage("```python\nimport os\n```")
        result = render_message(message, WIDTH)
        assert ("class:pygments.keyword.namespace", "import") in result

    def test_diff_lines_emit_full_width_diff_classes(self) -> None:
        diff = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
        result = render(diff_blocks(diff), WIDTH)
        added = "".join(fragment[1] for fragment in result if Tokens.Diff.ADD in fragment[0])
        assert any(Tokens.Diff.REMOVE in fragment[0] for fragment in result)
        assert added.rstrip("\n").endswith(" ")


def test_rich_emits_no_colors_so_every_color_comes_from_a_token() -> None:
    markdown = (
        "# H1\n## H2 *em* **strong** ~~s~~ `code`\n> [link](https://example.com)\n\n"
        "- item\n1. item\n\n| a | b |\n|---|---|\n| c | d |\n\n---\n"
        "```python\nclass A: pass\n```\n\n    indented = True\n"
    )
    diff = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
    renderables = [
        Padding(Markdown(markdown), 1, style=Tokens.Surface.RAISED),
        diff_blocks(diff),
    ]
    console = rich_bridge._Console(width=60)  # noqa: SLF001

    colored = [
        segment
        for renderable in renderables
        for segment in console.render(renderable)
        if segment.style
        and any(
            color and not color.is_default for color in (segment.style.color, segment.style.bgcolor)
        )
    ]

    assert colored == []


def test_messages_are_rendered_once_per_width(state: AppState) -> None:
    state.messages = [UserMessage("hi"), UserMessage("there")]
    renderer = MessageRenderer(state)
    first = renderer.render(40)
    assert all(a is b for a, b in zip(renderer.render(40), first, strict=True))
    assert renderer.render(30)[0] is not first[0]


def test_a_new_message_is_rendered_alongside_the_cached_ones(state: AppState) -> None:
    state.messages = [UserMessage("hi")]
    renderer = MessageRenderer(state)
    first = renderer.render(40)[0]
    state.messages = [*state.messages, UserMessage("there")]
    blocks = renderer.render(40)
    assert blocks[0] is first
    assert len(blocks) == 2


def test_a_message_that_is_gone_is_rendered_again_if_it_comes_back(state: AppState) -> None:
    message = UserMessage("hi")
    state.messages = [message]
    renderer = MessageRenderer(state)
    first = renderer.render(40)[0]
    state.messages = []
    renderer.render(40)
    state.messages = [message]
    assert renderer.render(40)[0] is not first
