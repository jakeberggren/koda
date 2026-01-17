from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pathspec

from koda.tools import exceptions


def _load_gitignore(sandbox_dir: Path) -> pathspec.PathSpec | None:
    """Load .gitignore from sandbox directory."""
    gitignore_path = sandbox_dir / ".gitignore"
    if not gitignore_path.is_file():
        return None

    try:
        patterns = gitignore_path.read_text().splitlines()
        patterns = [p for p in patterns if p.strip() and not p.strip().startswith("#")]
        return pathspec.PathSpec.from_lines("gitwildmatch", patterns)
    except OSError:
        return None


@dataclass(frozen=True, slots=True)
class ToolPolicy:
    """Centralized policy enforcement for tool execution.

    Enforces:
    - Sandbox boundaries (paths must be within sandbox_dir)
    - Denied path components (e.g. '.git')
    - Gitignore patterns (respects .gitignore in sandbox root)
    """

    sandbox_dir: Path
    """Root directory for sandbox enforcement."""

    deny_path_parts: frozenset[str] = field(default_factory=frozenset)
    """Set of path components to deny (e.g. {'.git'}). Empty = no extra denies."""

    respect_gitignore: bool = True
    """Whether to deny access to paths matching .gitignore patterns."""

    _gitignore_spec: pathspec.PathSpec | None = field(default=None, repr=False)
    """Pre-loaded gitignore spec. Set via create() factory method."""

    @classmethod
    def create(
        cls,
        sandbox_dir: Path,
        *,
        deny_path_parts: frozenset[str] | None = None,
        respect_gitignore: bool = True,
    ) -> ToolPolicy:
        """Create a ToolPolicy with pre-loaded gitignore."""
        gitignore_spec = _load_gitignore(sandbox_dir) if respect_gitignore else None
        return cls(
            sandbox_dir=sandbox_dir,
            deny_path_parts=deny_path_parts or frozenset(),
            respect_gitignore=respect_gitignore,
            _gitignore_spec=gitignore_spec,
        )

    def resolve_path(self, path: str, *, cwd: Path) -> Path:
        """Resolve a user-provided path safely within the sandbox.

        Raises:
            PathOutsideSandboxError: If path is outside sandbox.
            PathDeniedError: If path matches denied patterns or gitignore.
        """
        raw = Path(path)
        candidate = (cwd / raw) if not raw.is_absolute() else raw
        resolved = candidate.resolve()

        if not resolved.is_relative_to(self.sandbox_dir):
            raise exceptions.PathOutsideSandboxError(resolved, sandbox=self.sandbox_dir)

        if self.deny_path_parts:
            parts = frozenset(resolved.parts)
            denied = parts.intersection(self.deny_path_parts)
            if denied:
                raise exceptions.PathDeniedError(
                    resolved, reason=f"contains denied component: {denied}"
                )

        if self.respect_gitignore and self._is_gitignored(resolved):
            raise exceptions.PathDeniedError(resolved, reason="matches .gitignore pattern")

        return resolved

    def is_gitignored(self, path: Path) -> bool:
        """Check if a path matches .gitignore patterns. Public API for filtering."""
        return self._is_gitignored(path)

    def _is_gitignored(self, path: Path) -> bool:
        """Check if a path matches .gitignore patterns."""
        if self._gitignore_spec is None:
            return False

        try:
            relative = path.relative_to(self.sandbox_dir)
        except ValueError:
            return False

        return self._gitignore_spec.match_file(str(relative))
