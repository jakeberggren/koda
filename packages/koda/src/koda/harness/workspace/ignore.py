"""Ignore rules: which files a workspace leaves out, by its .gitignore and .ignore files."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pathspec import GitIgnoreSpec

if TYPE_CHECKING:
    from pathlib import Path

IGNORE_FILES = (".gitignore", ".ignore")
# Never a workspace's files: version control's own, and the operating system's clutter.
SKIPPED = frozenset({".git", ".hg", ".svn", ".DS_Store", "Thumbs.db", "desktop.ini"})


@dataclass(frozen=True, slots=True)
class IgnoreRules:
    """The patterns of a folder's .gitignore and .ignore, for paths below ``folder``."""

    folder: Path
    spec: GitIgnoreSpec


def read_rules(folder: Path) -> IgnoreRules | None:
    """The ignore rules in ``folder``, if its ignore files have any; .ignore after
    .gitignore, so it has the last word."""
    lines: list[str] = []
    for name in IGNORE_FILES:
        try:
            lines.extend((folder / name).read_text(encoding="utf-8").splitlines())
        except OSError:
            continue
    spec = GitIgnoreSpec.from_lines(lines)
    return IgnoreRules(folder, spec) if len(spec) else None


def ignored(stack: tuple[IgnoreRules, ...], path: Path, *, folder: bool = False) -> bool:
    """Whether ``path`` is excluded: the deepest rules that match it decide."""
    for rules in reversed(stack):
        relative = path.relative_to(rules.folder).as_posix() + ("/" if folder else "")
        if (include := rules.spec.check_file(relative).include) is not None:
            return include
    return False
