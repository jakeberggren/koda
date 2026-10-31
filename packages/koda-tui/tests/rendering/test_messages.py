"""Tests for rendering messages, streaming content and their styles."""

from rich.padding import Padding

from koda.tools import ToolCall
from koda_tui.appearance import Tokens
from koda_tui.appearance import rich as rich_bridge
from koda_tui.appearance.rich import render
from koda_tui.rendering import render_message, render_streaming, render_thinking
from koda_tui.rendering.diff import diff_blocks
from koda_tui.rendering.markdown import Markdown
from koda_tui.state import Message, MessageRole

WIDTH = 80


class TestMessages:
    """Tests for message rendering."""

    def test_render_user_message(self) -> None:
        """render_message() should render user messages as markdown."""
        message = Message(role=MessageRole.USER, content="Hello")
        result = render_message(message, WIDTH)
        content = "".join(t[1] for t in result)
        assert "Hello" in content
        assert any(Tokens.Surface.RAISED in fragment[0] for fragment in result)

    def test_render_assistant_message(self) -> None:
        """render_message() should render assistant messages as markdown."""
        message = Message(role=MessageRole.ASSISTANT, content="I can help")
        result = render_message(message, WIDTH)
        content = "".join(t[1] for t in result)
        assert "I can help" in content

    def test_render_assistant_message_with_thinking(self) -> None:
        """render_message() should keep persisted thinking content visible."""
        message = Message(
            role=MessageRole.ASSISTANT,
            content="I can help",
            thinking_content="Comparing options",
        )
        result = render_message(message, WIDTH)
        content = "".join(t[1] for t in result)
        assert "Comparing options" in content
        assert "I can help" in content
        lines = [line.rstrip() for line in content.splitlines()]
        assert lines[:3] == ["Comparing options", "", "I can help"]

    def test_render_assistant_thinking_renders_markdown(self) -> None:
        """thinking content should be rendered through markdown, not as literal markers."""
        message = Message(
            role=MessageRole.ASSISTANT,
            content="",
            thinking_content="**Exploring the meaning of 42**",
        )
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
        message = Message(
            role=MessageRole.TOOL,
            content="Tool: search",
            tool_call=tool_call,
        )
        result = render_message(message, WIDTH)
        content = "".join(t[1] for t in result)
        assert "search" in content


class TestStreaming:
    """Tests for streaming content rendering."""

    def test_render_streaming_content(self) -> None:
        """render_streaming_content() should show streaming content."""
        result = render_streaming("Hello wor", WIDTH)
        content = "".join(t[1] for t in result)
        assert "Hello wor" in content

    def test_render_thinking_content_renders_markdown(self) -> None:
        """render_thinking_content() should parse markdown markers."""
        result = render_thinking("**Exploring the meaning of 42**", WIDTH)
        content = "".join(t[1] for t in result)
        assert "Exploring the meaning of 42" in content
        assert "**Exploring the meaning of 42**" not in content


class TestStyleClasses:
    """Theme-dependent styling is emitted as style classes, not baked-in colors."""

    def test_code_block_emits_pygments_classes(self) -> None:
        message = Message(role=MessageRole.ASSISTANT, content="```python\nimport os\n```")
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
