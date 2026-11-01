"""Renderer: what each chat message and tool call looks like, and the conversation
rendered as fragments."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from rich.console import Group
from rich.padding import Padding
from rich.text import Text

from koda_tui import strings
from koda_tui.appearance import Icons, Spacing, Tokens, compose
from koda_tui.rendering import rich
from koda_tui.rendering.diff import diff_blocks, diff_summary
from koda_tui.rendering.markdown import Markdown
from koda_tui.state import AssistantMessage, ErrorMessage, Message, ToolMessage, UserMessage

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from rich.console import RenderableType

    from koda.tools import ToolCall, ToolOutput

type Arguments = dict[str, object]

USER_PADDING = (Spacing.GAP, 0, Spacing.GAP, Spacing.INSET)  # Top, right, bottom, left.
THINKING_STYLE = compose(Tokens.Text.MUTED, Tokens.Text.EMPHASIS)
INLINE_CHARS = 120  # Longest tool argument shown inline before it is summarised.
PREVIEW_LINES = 6  # Most output lines previewed from a command.
PREVIEW_CHARS = 600  # Most output characters previewed from a command.
RUNNING = (Icons.RUNNING, Tokens.Text.WARNING)
FAILED = (Icons.FAILED, Tokens.Text.ERROR)
DONE = (Icons.DONE, Tokens.Text.SUCCESS)


class MessageRenderer[M: Message](ABC):
    """Renders one kind of message as fragments. Each renderer writes ``renderable``;
    ``render`` turns that into fragments."""

    def render(self, message: M, width: int) -> StyleAndTextTuples:
        """``message`` as fragments ``width`` cells wide."""
        return rich.render(self.renderable(message), width)

    @abstractmethod
    def renderable(self, message: M) -> RenderableType:
        """``message`` as a Rich renderable."""


class Renderer(MessageRenderer[Message]):
    """Renders any message, by the renderer for its kind."""

    def renderable(self, message: Message) -> RenderableType:
        match message:
            case UserMessage():
                return UserRenderer().renderable(message)
            case AssistantMessage():
                return AssistantRenderer().renderable(message)
            case ToolMessage():
                return ToolRenderer.for_tool(message.call.tool_name).renderable(message)
            case ErrorMessage():
                return ErrorRenderer().renderable(message)


class UserRenderer(MessageRenderer[UserMessage]):
    def renderable(self, message: UserMessage) -> RenderableType:
        """The user's message on a raised block."""
        return Padding(Markdown(message.text), USER_PADDING, style=Tokens.Surface.RAISED)


class AssistantRenderer(MessageRenderer[AssistantMessage]):
    def renderable(self, message: AssistantMessage) -> RenderableType:
        """The thinking, muted, then the reply, a gap apart; either may be empty."""
        parts: list[RenderableType] = []
        if message.thinking:
            parts.append(Markdown(message.thinking, style=THINKING_STYLE))
        if message.text:
            if parts:
                parts.extend(Text() for _ in range(Spacing.GAP))
            parts.append(Markdown(message.text))
        return Group(*parts)


class ErrorRenderer(MessageRenderer[ErrorMessage]):
    def renderable(self, message: ErrorMessage) -> RenderableType:
        """The error's summary in bold, above its detail or what to do about it."""
        detail = message.detail or strings.Screen.Chat.ERROR_FALLBACK
        return Markdown(f"**{message.summary}**\n\n{detail}")


class ToolRenderer(MessageRenderer[ToolMessage]):
    """How a tool's call is shown: its status, name and arguments, then its result.
    The defaults suit any tool; a tool's own renderer overrides what it shows differently,
    and names its tool where it subclasses this: ``class BashRenderer(ToolRenderer,
    tool="bash")``."""

    _by_tool: ClassVar[dict[str, ToolRenderer]] = {}

    def __init_subclass__(cls, *, tool: str, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        ToolRenderer._by_tool[tool] = cls()

    @classmethod
    def for_tool(cls, name: str) -> ToolRenderer:
        """The renderer for the tool named ``name``, or this default if it has none."""
        return cls._by_tool.get(name) or ToolRenderer()

    def renderable(self, message: ToolMessage) -> RenderableType:
        """The call's line, then its result once it has one; none means it is still
        running."""
        output = message.result
        line = self._line(message.call, output)
        if output is None:
            return line
        return Group(line, *self.result(output))

    def arguments(self, arguments: Arguments) -> str:
        return " ".join(f"{key}={_value(value)}" for key, value in arguments.items())

    def result(self, output: ToolOutput) -> list[RenderableType]:
        """What is shown below the call: by default its display, or its error message if
        it failed without one, under a result mark."""
        text = output.display or (output.error_message if output.is_error else None)
        return [_result(text)] if text else []

    def _line(self, call: ToolCall, output: ToolOutput | None) -> Text:
        symbol, style = RUNNING if output is None else FAILED if output.is_error else DONE
        line = Text()
        line.append(f"{symbol} ", style=style)
        line.append(call.tool_name, style=Tokens.Text.EMPHASIS)
        if call.arguments and (arguments := self.arguments(call.arguments)):
            line.append(f" {arguments}", style=Tokens.Text.MUTED)
        return line


class BashRenderer(ToolRenderer, tool="bash"):
    def arguments(self, arguments: Arguments) -> str:
        """The arguments it was given, with the command on one line."""
        command = _inline(_text(arguments.get("command", "")))
        return super().arguments({**arguments, "command": command})

    def result(self, output: ToolOutput) -> list[RenderableType]:
        """How the command went, then a preview of the output that matters most: stderr
        when it failed, else stdout's end."""
        content = output.content
        if not content:  # It never ran, such as on a timeout.
            return super().result(output)
        stdout = _text(content.get("stdout", ""))
        stderr = _text(content.get("stderr", ""))
        failed = output.is_error
        exit_code = content.get("exit_code") if failed else None
        summary = strings.Screen.Chat.Tools.bash_summary(
            exit_code, len(stdout.splitlines()), len(stderr.splitlines())
        )
        blocks: list[RenderableType] = [_result(summary)]
        show_stderr = bool(stderr) and (failed or not stdout)
        if stream := stderr if show_stderr else stdout:
            label = (
                strings.Screen.Chat.Tools.STDERR
                if show_stderr
                else strings.Screen.Chat.Tools.STDOUT
            )
            preview = _preview(stream, tail=not (failed or show_stderr))
            blocks.append(_result(f"{label}\n{preview}"))
        return blocks


class EditFileRenderer(ToolRenderer, tool="edit_file"):
    def arguments(self, arguments: Arguments) -> str:
        return str(arguments.get("path", ""))

    def result(self, output: ToolOutput) -> list[RenderableType]:
        """The diff's summary, then the diff itself."""
        if not output.display or not output.display.startswith("---"):  # Not a diff.
            return super().result(output)
        return [_result(diff_summary(output.display)), diff_blocks(output.display)]


class WriteFileRenderer(ToolRenderer, tool="write_file"):
    def arguments(self, arguments: Arguments) -> str:
        path = arguments.get("path", "")
        return f"path={path} content={_value(arguments.get('content', ''))}"


def _result(text: str) -> Padding:
    """``text`` under a result mark, indented below the call."""
    marked = Text(f"{Icons.RESULT} {text}", style=Tokens.Text.MUTED)
    return Padding(marked, (0, 0, 0, Spacing.INDENT), expand=False)


def _value(value: object) -> str:
    """An argument value as text, summarised if it is long or spans lines."""
    text = _text(value)
    if "\n" in text or len(text) > INLINE_CHARS:
        return strings.Screen.Chat.Tools.long_value(len(text), len(text.splitlines()))
    return text


def _text(value: object) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _inline(value: str) -> str:
    """``value`` on one line, cut to ``INLINE_CHARS``."""
    normalized = " ".join(value.split())
    if len(normalized) <= INLINE_CHARS:
        return normalized
    ellipsis = strings.Common.ELLIPSIS
    return f"{normalized[: INLINE_CHARS - len(ellipsis)].rstrip()}{ellipsis}"


def _preview(value: str, *, tail: bool = False) -> str:
    """The first (or last) lines of ``value``, marked if anything was cut."""
    lines = value.splitlines()
    cut_lines = len(lines) > PREVIEW_LINES
    preview = "\n".join(lines[-PREVIEW_LINES:] if tail else lines[:PREVIEW_LINES])
    cut_chars = len(preview) > PREVIEW_CHARS
    if cut_chars:
        preview = preview[-PREVIEW_CHARS:].lstrip() if tail else preview[:PREVIEW_CHARS].rstrip()
    if not (cut_lines or cut_chars):
        return preview
    marker = strings.Screen.Chat.Tools.truncated(len(lines))
    ellipsis = strings.Common.ELLIPSIS
    return f"{ellipsis}\n{marker}\n{preview}" if tail else f"{preview}\n{ellipsis}\n{marker}"
