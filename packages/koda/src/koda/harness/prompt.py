"""The system prompt: SYSTEM.md (the folder's, ``~/.koda``'s or the default), with the
folder's AGENTS.md and CLAUDE.md after it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from structlog import get_logger

from koda.paths import koda_home_dir

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)

DEFAULT_PROMPT = (
    "You are Koda, an expert coding assistant built to help the user "
    "navigate, understand, and modify codebases.\n\n"
    "You are running in an execution environment with session state and tool support.\n\n"
    "Be clear, practical, and concise. "
    "Prefer concrete next steps and implementation details when helpful.\n\n"
    "When working with code, preserve the user's intent, avoid unnecessary changes, "
    "and call out important assumptions or risks."
)

PROJECT_FILES = ("AGENTS.md", "CLAUDE.md")


def instructions(path: Path) -> str:
    """The system prompt for working in ``path``."""
    path = path.resolve()
    system = read(path / "SYSTEM.md") or read(koda_home_dir() / "SYSTEM.md") or DEFAULT_PROMPT
    project = [text for name in PROJECT_FILES if (text := read(path / name))]
    return "\n\n".join([system, *project])


def read(path: Path) -> str | None:
    """The file's text, or ``None`` when it is missing, empty or can't be read."""
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8").strip() or None
    except OSError as error:
        logger.warning("prompt_file_unreadable", path=str(path), error=str(error))
        return None
