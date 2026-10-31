"""Markdown: Rich's markdown, with code highlighted by tokens and headings on the left."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from rich import markdown

from koda_tui.appearance.rich import syntax

if TYPE_CHECKING:
    from rich.console import Console, ConsoleOptions, RenderResult


class CodeBlock(markdown.CodeBlock):
    @override
    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        yield syntax(str(self.text).rstrip(), self.lexer_name)


class Heading(markdown.Heading):
    @override
    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        self.text.justify = "left"
        yield self.text


class Markdown(markdown.Markdown):
    elements: ClassVar = {
        **markdown.Markdown.elements,
        "fence": CodeBlock,
        "code_block": CodeBlock,
        "heading_open": Heading,
    }
