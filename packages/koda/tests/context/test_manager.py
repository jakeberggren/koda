"""Tests for koda.context.manager."""

from pathlib import Path
from unittest.mock import MagicMock

from koda.context.manager import ContextManager
from koda.context.sources import FileContextSource, ProjectFileContextSource
from koda.prompts import DEFAULT_SYSTEM_PROMPT, SystemPrompt


class TestContextManager:
    """Unit tests for ContextManager."""

    def test_build_system_prompt_no_sources(self) -> None:
        manager = ContextManager(sources=[])
        base = SystemPrompt()

        result = manager.build_system_prompt(base)

        assert result == base

    def test_build_system_prompt_with_content(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text("Always use type hints.", encoding="utf-8")
        manager = ContextManager.from_workspace(tmp_path)
        base = SystemPrompt()

        result = manager.build_system_prompt(base)

        assert "You are Koda" in result.content
        assert "Always use type hints." in result.content
        assert result.source == base.source

    def test_build_system_prompt_preserves_base_content(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text("Rule.", encoding="utf-8")
        manager = ContextManager.from_workspace(tmp_path)
        base = SystemPrompt()

        result = manager.build_system_prompt(base)

        assert base.content in result.content

    def test_build_system_prompt_no_files_found(self, tmp_path: Path) -> None:
        manager = ContextManager.from_workspace(tmp_path)
        base = SystemPrompt()

        result = manager.build_system_prompt(base)

        assert result == base

    def test_from_workspace_defaults(self, tmp_path: Path) -> None:
        manager = ContextManager.from_workspace(tmp_path)

        assert len(manager.sources) == 1
        assert isinstance(manager.sources[0], ProjectFileContextSource)

    def test_from_workspace_custom_filenames(self, tmp_path: Path) -> None:
        (tmp_path / "RULES.md").write_text("Custom.", encoding="utf-8")
        manager = ContextManager.from_workspace(
            tmp_path,
            filenames=("RULES.md",),
        )

        result = manager.build_system_prompt(SystemPrompt())

        assert "Custom." in result.content

    def test_build_system_prompt_multiple_sources(self) -> None:
        source_a = MagicMock(spec=FileContextSource)
        source_a.read.return_value = "From A"
        source_b = MagicMock(spec=FileContextSource)
        source_b.read.return_value = "From B"

        manager = ContextManager(sources=[source_a, source_b])
        result = manager.build_system_prompt(SystemPrompt())

        assert "From A" in result.content
        assert "From B" in result.content

    def test_build_system_prompt_one_source_empty(self) -> None:
        source_a = MagicMock(spec=FileContextSource)
        source_a.read.return_value = None
        source_b = MagicMock(spec=FileContextSource)
        source_b.read.return_value = "Only B"

        manager = ContextManager(sources=[source_a, source_b])
        result = manager.build_system_prompt(SystemPrompt())

        assert result.content == DEFAULT_SYSTEM_PROMPT + "\n\nOnly B"
