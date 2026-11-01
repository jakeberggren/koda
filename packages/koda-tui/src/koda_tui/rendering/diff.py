"""Diffs: unified diffs as highlighted blocks on added and removed backgrounds."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from rich.console import Group
from rich.padding import Padding
from rich.syntax import Syntax

from koda_tui import strings
from koda_tui.appearance import Tokens
from koda_tui.rendering.rich import syntax

if TYPE_CHECKING:
    from rich.console import RenderableType

type LineKind = Literal["add", "del", "context"]

FILENAME = re.compile(r"^---\s+\S+?([^/\s]+)$", re.MULTILINE)
HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
ADDITION = re.compile(r"^\+(?!\+\+)", re.MULTILINE)
DELETION = re.compile(r"^-(?!--)", re.MULTILINE)
STYLES: dict[LineKind | None, str] = {"add": Tokens.Diff.ADD, "del": Tokens.Diff.REMOVE}


def is_diff(text: str) -> bool:
    return text.startswith("---")


def diff_blocks(diff: str) -> Group:  # noqa: C901 - one branch per kind of diff line
    """``diff`` highlighted for its file's language, one block per run of same-kind lines."""
    blocks = _Blocks(lexer=_lexer(diff))
    old: int | None = None
    new: int | None = None

    for line in diff.splitlines():
        if line.startswith("@@"):
            blocks.flush()
            if match := HUNK.match(line):
                old, new = int(match.group(1)), int(match.group(2))
        elif line.startswith(("+++", "---")):
            continue
        elif line.startswith("+"):
            blocks.add(line, "add", new)
            new = new + 1 if new else None
        elif line.startswith("-"):
            blocks.add(line, "del", old)
            old = old + 1 if old else None
        else:
            blocks.add(line, "context", new)
            new = new + 1 if new else None
            old = old + 1 if old else None

    blocks.flush()
    return Group(*blocks.renderables)


def diff_summary(diff: str) -> str:
    """How many lines ``diff`` adds and removes, e.g. "2 additions, 1 deletion"."""
    additions = len(ADDITION.findall(diff))
    deletions = len(DELETION.findall(diff))
    return strings.Screen.Chat.Tools.diff_summary(additions, deletions)


def _lexer(diff: str) -> str:
    """The lexer for the diffed file's name, or plain text."""
    match = FILENAME.search(diff)
    return Syntax.guess_lexer(match.group(1)) if match else "text"


@dataclass
class _Blocks:
    """Collects diff lines into blocks, starting a new one when the kind changes."""

    lexer: str
    renderables: list[RenderableType] = field(default_factory=list)
    kind: LineKind | None = None
    lines: list[str] = field(default_factory=list)
    start: int | None = None

    def add(self, line: str, kind: LineKind, start: int | None) -> None:
        if self.kind != kind:
            self.flush()
            self.kind = kind
            self.start = start
        self.lines.append(line)

    def flush(self) -> None:
        if not self.lines:
            return
        block = syntax(
            "\n".join(self.lines),
            self.lexer,
            line_numbers=True,
            start_line=self.start or 1,
        )
        style = STYLES.get(self.kind)
        self.renderables.append(block if style is None else Padding(block, 0, style=style))
        self.lines = []
        self.kind = None
        self.start = None
