"""Diffs: unified diffs as highlighted blocks on added and removed backgrounds, beside a
gutter of line numbers and signs."""

from __future__ import annotations

import re
from itertools import groupby
from operator import attrgetter
from typing import TYPE_CHECKING, Literal, NamedTuple

from rich.console import Group
from rich.padding import Padding
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from koda_tui import strings
from koda_tui.appearance import Tokens
from koda_tui.rendering.rich import syntax

if TYPE_CHECKING:
    from collections.abc import Iterator

    from rich.console import RenderableType

type LineKind = Literal["add", "del", "context"]

FILENAME = re.compile(r"^---\s+\S+?([^/\s]+)$", re.MULTILINE)
HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
ADDITION = re.compile(r"^\+(?!\+\+)", re.MULTILINE)
DELETION = re.compile(r"^-(?!--)", re.MULTILINE)
KINDS: dict[str, LineKind] = {"+": "add", "-": "del"}  # By first character.
SIGNS: dict[LineKind, str] = {"add": "+", "del": "-", "context": " "}
STYLES: dict[LineKind, str] = {"add": Tokens.Diff.ADD, "del": Tokens.Diff.REMOVE}
GUTTERS: dict[LineKind, str] = {
    "add": Tokens.Diff.ADD_GUTTER,
    "del": Tokens.Diff.REMOVE_GUTTER,
    "context": Tokens.Text.MUTED,
}


class _Line(NamedTuple):
    """A line of a diff: which hunk it is in, its kind, its number, and its text without
    the sign."""

    hunk: int
    kind: LineKind
    number: int | None
    text: str


def diff_blocks(diff: str) -> Group:
    """``diff`` highlighted for its file's language, one block per run of same-kind
    lines in a hunk."""
    lexer = _lexer(diff)
    lines = list(_lines(diff))
    width = max((len(str(line.number)) for line in lines if line.number), default=1)
    runs = groupby(lines, key=attrgetter("hunk", "kind"))
    return Group(*(_block(list(run), lexer, width) for _, run in runs))


def diff_summary(diff: str) -> str:
    """How many lines ``diff`` adds and removes, e.g. "2 additions, 1 deletion"."""
    additions = len(ADDITION.findall(diff))
    deletions = len(DELETION.findall(diff))
    return strings.Screen.Chat.Tools.diff_summary(additions, deletions)


def _lines(diff: str) -> Iterator[_Line]:
    """Each added, removed and context line, numbered as in the new file, or the old
    one for a removed line."""
    hunk = 0
    old: int | None = None
    new: int | None = None
    for text in diff.splitlines():
        if text.startswith("@@"):
            hunk += 1
            old, new = _hunk_start(text) or (old, new)
        elif not text.startswith(("+++", "---")):
            kind = KINDS.get(text[:1], "context")
            yield _Line(hunk, kind, old if kind == "del" else new, text[1:])
            old = old if kind == "add" else _next(old)
            new = new if kind == "del" else _next(new)


def _hunk_start(header: str) -> tuple[int, int] | None:
    """Where a hunk starts in the old file and the new one, from its ``@@`` header."""
    match = HUNK.match(header)
    return (int(match.group(1)), int(match.group(2))) if match else None


def _block(run: list[_Line], lexer: str, width: int) -> RenderableType:
    """A run of same-kind lines, highlighted on its kind's background, beside a gutter
    numbering them ``width`` digits wide and signing them."""
    kind = run[0].kind
    gutter = "\n".join(_gutter(line, width) for line in run)
    code = "\n".join(line.text for line in run)
    grid = Table.grid(expand=True)
    grid.add_column(no_wrap=True)
    grid.add_column(ratio=1)
    grid.add_row(Text(gutter, style=GUTTERS[kind]), syntax(code, lexer))
    style = STYLES.get(kind)
    return grid if style is None else Padding(grid, 0, style=style)


def _gutter(line: _Line, width: int) -> str:
    """A line's number, right-aligned to ``width`` digits, and its sign."""
    number = str(line.number) if line.number else ""
    return f" {number:>{width}} {SIGNS[line.kind]} "


def _next(number: int | None) -> int | None:
    return number + 1 if number else None


def _lexer(diff: str) -> str:
    """The lexer for the diffed file's name, or plain text."""
    match = FILENAME.search(diff)
    return Syntax.guess_lexer(match.group(1)) if match else "text"
