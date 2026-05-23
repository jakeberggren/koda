"""Tests for koda.context.manager."""

from pathlib import Path
from unittest.mock import MagicMock

from koda.context.manager import ContextManager
from koda.context.sources import ContextSource
from koda.prompts import SystemPrompt


class TestContextManager:
    """Unit tests for ContextManager."""

    def test_build_system_prompt_no_sources(self) -> None:
        manager = ContextManager(sources=[])
        base = SystemPrompt()

        result = manager.build_system_prompt(base)

        assert result == base

    def test_build_system_prompt_appends_context_and_preserves_source(self) -> None:
        source_a = MagicMock(spec=ContextSource)
        source_a.read.return_value = "From A"
        source_b = MagicMock(spec=ContextSource)
        source_b.read.return_value = None
        source_c = MagicMock(spec=ContextSource)
        source_c.read.return_value = "From C"
        manager = ContextManager(sources=[source_a, source_b, source_c])
        base = SystemPrompt(content="Base prompt.", source=Path("/tmp/SYSTEM.md"))

        result = manager.build_system_prompt(base)

        assert result.content == "Base prompt.\n\nFrom A\n\nFrom C"
        assert result.source == base.source

    def test_build_system_prompt_no_files_found(self, tmp_path: Path) -> None:
        manager = ContextManager.from_workspace(tmp_path)
        base = SystemPrompt()

        result = manager.build_system_prompt(base)

        assert result == base

    def test_from_workspace_custom_filenames(self, tmp_path: Path) -> None:
        (tmp_path / "RULES.md").write_text("Custom.", encoding="utf-8")
        manager = ContextManager.from_workspace(
            tmp_path,
            filenames=("RULES.md",),
        )

        result = manager.build_system_prompt(SystemPrompt())

        assert "Custom." in result.content
