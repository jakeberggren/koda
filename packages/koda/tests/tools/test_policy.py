"""Tests for tools/policy.py - sandbox enforcement."""

from pathlib import Path

import pytest

from koda.tools.exceptions import PathDeniedError, PathOutsideSandboxError
from koda.tools.policy import ToolPolicy


class TestPathResolution:
    """Tests for basic path resolution."""

    def test_relative_path_within_sandbox(self, workspace_dir: Path, policy: ToolPolicy) -> None:
        """Relative paths within the sandbox are allowed."""
        test_file = workspace_dir / "test.txt"
        test_file.touch()

        resolved = policy.resolve_path("test.txt", cwd=workspace_dir)
        assert resolved == test_file

    def test_absolute_path_within_sandbox(self, workspace_dir: Path, policy: ToolPolicy) -> None:
        """Absolute paths within sandbox are allowed."""
        test_file = workspace_dir / "test.txt"
        test_file.touch()

        resolved = policy.resolve_path(str(test_file), cwd=workspace_dir)
        assert resolved == test_file

    def test_nested_path_within_sandbox(self, workspace_dir: Path, policy: ToolPolicy) -> None:
        """Deeply nested paths within sandbox are allowed."""
        nested = workspace_dir / "a" / "b" / "c"
        nested.mkdir(parents=True)
        test_file = nested / "test.txt"
        test_file.touch()

        resolved = policy.resolve_path("a/b/c/test.txt", cwd=workspace_dir)
        assert resolved == test_file

    def test_parent_segments_within_sandbox(self, workspace_dir: Path, policy: ToolPolicy) -> None:
        """Parent segments that stay within sandbox resolve correctly."""
        nested = workspace_dir / "nested"
        nested.mkdir()
        test_file = workspace_dir / "root.txt"
        test_file.touch()

        resolved = policy.resolve_path("nested/../root.txt", cwd=workspace_dir)
        assert resolved == test_file


class TestSandboxEnforcement:
    """Tests for sandbox boundary enforcement."""

    def test_absolute_path_outside_sandbox_rejected(
        self, workspace_dir: Path, policy: ToolPolicy
    ) -> None:
        """Absolute paths outside the sandbox raise PathOutsideSandboxError."""
        with pytest.raises(PathOutsideSandboxError) as exc_info:
            policy.resolve_path("/etc/passwd", cwd=workspace_dir)

        assert exc_info.value.path == "/etc/passwd"

    def test_relative_path_escaping_sandbox_rejected(
        self, workspace_dir: Path, policy: ToolPolicy
    ) -> None:
        """Relative paths that escape sandbox raise PathOutsideSandboxError."""
        with pytest.raises(PathOutsideSandboxError):
            policy.resolve_path("../../../etc/passwd", cwd=workspace_dir)

    def test_symlink_escaping_sandbox_rejected(self, workspace_dir: Path) -> None:
        """Symlinks that point outside sandbox are rejected."""
        policy = ToolPolicy.create(workspace_dir)

        symlink = workspace_dir / "escape_link"
        symlink.symlink_to("/etc")

        with pytest.raises(PathOutsideSandboxError):
            policy.resolve_path("escape_link/passwd", cwd=workspace_dir)

    def test_symlink_with_parent_segments_rejected(self, workspace_dir: Path) -> None:
        """Parent segments after symlink resolution cannot escape sandbox."""
        policy = ToolPolicy.create(workspace_dir)

        symlink = workspace_dir / "escape_link"
        symlink.symlink_to("/etc")

        with pytest.raises(PathOutsideSandboxError):
            policy.resolve_path("escape_link/../passwd", cwd=workspace_dir)


class TestDeniedPathParts:
    """Tests for denied path component enforcement."""

    def test_denied_path_parts_rejected(self, workspace_dir: Path) -> None:
        """Paths containing denied components are rejected."""
        policy = ToolPolicy.create(workspace_dir, deny_path_parts=frozenset({".git", ".env"}))

        git_dir = workspace_dir / ".git"
        git_dir.mkdir()

        with pytest.raises(PathDeniedError) as exc_info:
            policy.resolve_path(".git/config", cwd=workspace_dir)

        assert exc_info.value.path == ".git/config"
        assert ".git" in exc_info.value.reason

    def test_empty_deny_parts_allows_all(self, workspace_dir: Path, policy: ToolPolicy) -> None:
        """Empty deny_path_parts allows all paths."""
        git_dir = workspace_dir / ".git"
        git_dir.mkdir()
        config = git_dir / "config"
        config.touch()

        resolved = policy.resolve_path(".git/config", cwd=workspace_dir)
        assert resolved == config


class TestGitignoreEnforcement:
    """Tests for .gitignore pattern enforcement."""

    def test_gitignored_file_rejected(self, workspace_dir: Path) -> None:
        """Paths matching .gitignore patterns are rejected."""
        gitignore = workspace_dir / ".gitignore"
        gitignore.write_text("*.secret\n.env\n")

        secret_file = workspace_dir / "password.secret"
        secret_file.touch()

        policy = ToolPolicy.create(workspace_dir, respect_gitignore=True)

        with pytest.raises(PathDeniedError) as exc_info:
            policy.resolve_path("password.secret", cwd=workspace_dir)
        assert "gitignore" in exc_info.value.reason.lower()

    def test_gitignore_disabled_allows_all(self, workspace_dir: Path) -> None:
        """Gitignore can be disabled via policy."""
        gitignore = workspace_dir / ".gitignore"
        gitignore.write_text("*.secret\n")

        secret_file = workspace_dir / "password.secret"
        secret_file.touch()

        policy = ToolPolicy.create(workspace_dir, respect_gitignore=False)

        resolved = policy.resolve_path("password.secret", cwd=workspace_dir)
        assert resolved == secret_file

    def test_is_gitignored_public_api(self, workspace_dir: Path) -> None:
        """is_gitignored provides public API for filtering."""
        gitignore = workspace_dir / ".gitignore"
        gitignore.write_text("*.log\n")

        policy = ToolPolicy.create(workspace_dir, respect_gitignore=True)

        log_file = workspace_dir / "debug.log"
        txt_file = workspace_dir / "readme.txt"

        assert policy.is_gitignored(log_file) is True
        assert policy.is_gitignored(txt_file) is False
