"""Tests for koda.context.sources."""

from pathlib import Path

from koda.context.sources import FileContextSource, ProjectFileContextSource


class TestFileContextSource:
    """Unit tests for FileContextSource."""

    def test_read_existing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "AGENTS.md"
        path.write_text("Use Python 3.13.", encoding="utf-8")
        source = FileContextSource(path)

        result = source.read()

        assert result == "Use Python 3.13."

    def test_read_missing_file(self, tmp_path: Path) -> None:
        source = FileContextSource(tmp_path / "MISSING.md")

        result = source.read()

        assert result is None

    def test_read_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "EMPTY.md"
        path.write_text("   \n\n  ", encoding="utf-8")
        source = FileContextSource(path)

        result = source.read()

        assert result is None

    def test_read_strips_whitespace(self, tmp_path: Path) -> None:
        path = tmp_path / "AGENTS.md"
        path.write_text("  Content  \n", encoding="utf-8")
        source = FileContextSource(path)

        result = source.read()

        assert result == "Content"

    def test_read_rejects_symlink_outside_root(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        outside = tmp_path / "outside"
        workspace.mkdir()
        outside.mkdir()

        secret = outside / "secret.txt"
        secret.write_text("leaked", encoding="utf-8")

        link = workspace / "AGENTS.md"
        link.symlink_to(secret)

        source = FileContextSource(link, trusted_root=workspace)
        assert source.read() is None

    def test_read_allows_symlink_inside_root(self, tmp_path: Path) -> None:
        real = tmp_path / "real.md"
        real.write_text("ok", encoding="utf-8")

        link = tmp_path / "AGENTS.md"
        link.symlink_to(real)

        source = FileContextSource(link, trusted_root=tmp_path)
        assert source.read() == "ok"

    def test_read_rejects_traversal_outside_root(self, tmp_path: Path) -> None:
        source = FileContextSource(tmp_path / ".." / "AGENTS.md", trusted_root=tmp_path)
        assert source.read() is None

    def test_read_without_root_follows_symlink(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        outside = tmp_path / "outside"
        workspace.mkdir()
        outside.mkdir()

        secret = outside / "secret.txt"
        secret.write_text("leaked", encoding="utf-8")

        link = workspace / "AGENTS.md"
        link.symlink_to(secret)

        source = FileContextSource(link)
        assert source.read() == "leaked"


class TestProjectFileContextSource:
    """Unit tests for ProjectFileContextSource."""

    def test_read_no_files(self, tmp_path: Path) -> None:
        source = ProjectFileContextSource(root=tmp_path)

        result = source.read()

        assert result is None

    def test_read_single_file(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text("Rule 1", encoding="utf-8")
        source = ProjectFileContextSource(root=tmp_path)

        result = source.read()

        assert result == "Rule 1"

    def test_read_multiple_files(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text("Rule 1", encoding="utf-8")
        (tmp_path / "CLAUDE.md").write_text("Rule 2", encoding="utf-8")
        source = ProjectFileContextSource(root=tmp_path)

        result = source.read()

        assert result == "Rule 1\n\nRule 2"

    def test_read_skips_missing_files(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("Only Claude", encoding="utf-8")
        source = ProjectFileContextSource(root=tmp_path)

        result = source.read()

        assert result == "Only Claude"

    def test_read_custom_filenames(self, tmp_path: Path) -> None:
        (tmp_path / "CUSTOM.md").write_text("Custom rule", encoding="utf-8")
        source = ProjectFileContextSource(
            root=tmp_path,
            filenames=("CUSTOM.md",),
        )

        result = source.read()

        assert result == "Custom rule"

    def test_read_rejects_custom_filename_traversal(self, tmp_path: Path) -> None:
        outside = tmp_path / "outside.md"
        outside.write_text("outside", encoding="utf-8")
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        source = ProjectFileContextSource(root=workspace, filenames=("../outside.md",))

        assert source.read() is None
