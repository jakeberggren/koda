"""Tests for koda.context.sources."""

from pathlib import Path

from koda.context.sources import FileContextSource, ProjectFileDiscoverySource


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


class TestProjectFileDiscoverySource:
    """Unit tests for ProjectFileDiscoverySource."""

    def test_read_no_files(self, tmp_path: Path) -> None:
        source = ProjectFileDiscoverySource(root=tmp_path)

        result = source.read()

        assert result is None

    def test_read_single_file(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text("Rule 1", encoding="utf-8")
        source = ProjectFileDiscoverySource(root=tmp_path)

        result = source.read()

        assert result == "Rule 1"

    def test_read_multiple_files(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text("Rule 1", encoding="utf-8")
        (tmp_path / "CLAUDE.md").write_text("Rule 2", encoding="utf-8")
        source = ProjectFileDiscoverySource(root=tmp_path)

        result = source.read()

        assert result == "Rule 1\n\nRule 2"

    def test_read_skips_missing_files(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("Only Claude", encoding="utf-8")
        source = ProjectFileDiscoverySource(root=tmp_path)

        result = source.read()

        assert result == "Only Claude"

    def test_read_custom_filenames(self, tmp_path: Path) -> None:
        (tmp_path / "CUSTOM.md").write_text("Custom rule", encoding="utf-8")
        source = ProjectFileDiscoverySource(
            root=tmp_path,
            filenames=("CUSTOM.md",),
        )

        result = source.read()

        assert result == "Custom rule"
