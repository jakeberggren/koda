"""Tests for koda.prompts."""

from pathlib import Path

from koda.prompts import (
    DEFAULT_SYSTEM_PROMPT,
    SystemPrompt,
    SystemPromptLoader,
)


class TestSystemPromptRender:
    """Unit tests for SystemPrompt.render."""

    def test_renders_default_prompt(self) -> None:
        prompt = SystemPrompt()

        result = prompt.render()

        assert result == DEFAULT_SYSTEM_PROMPT

    def test_renders_custom_content(self) -> None:
        prompt = SystemPrompt(content="Custom prompt.")

        result = prompt.render()

        assert result == "Custom prompt."

    def test_returns_none_for_empty_content(self) -> None:
        prompt = SystemPrompt(content="   \n\n  ")

        result = prompt.render()

        assert result is None

    def test_strips_whitespace(self) -> None:
        prompt = SystemPrompt(content="  Content  \n")

        result = prompt.render()

        assert result == "Content"


class TestSystemPromptLoader:
    """Unit tests for SystemPromptLoader."""

    def test_load_finds_file_in_workspace(self, tmp_path: Path) -> None:
        (tmp_path / "SYSTEM.md").write_text("Custom system prompt.", encoding="utf-8")
        loader = SystemPromptLoader.for_workspace(tmp_path)

        prompt = loader.load()

        assert prompt.content == "Custom system prompt."
        assert prompt.source == tmp_path / "SYSTEM.md"

    def test_load_falls_back_to_default(self, tmp_path: Path) -> None:
        loader = SystemPromptLoader.for_workspace(tmp_path)

        prompt = loader.load()

        assert prompt.content == DEFAULT_SYSTEM_PROMPT
        assert prompt.source is None

    def test_load_ignores_empty_file(self, tmp_path: Path) -> None:
        (tmp_path / "SYSTEM.md").write_text("   \n\n  ", encoding="utf-8")
        loader = SystemPromptLoader.for_workspace(tmp_path)

        prompt = loader.load()

        assert prompt.content == DEFAULT_SYSTEM_PROMPT
        assert prompt.source is None

    def test_load_prefers_workspace_over_home(self, tmp_path: Path) -> None:
        (tmp_path / "SYSTEM.md").write_text("Workspace wins.", encoding="utf-8")
        loader = SystemPromptLoader(search_paths=[tmp_path, tmp_path])

        prompt = loader.load()

        assert prompt.content == "Workspace wins."
        assert prompt.source == tmp_path / "SYSTEM.md"

    def test_load_searches_in_order(self, tmp_path: Path) -> None:
        first = tmp_path / "first"
        second = tmp_path / "second"
        first.mkdir()
        second.mkdir()
        (second / "SYSTEM.md").write_text("Second file.", encoding="utf-8")
        loader = SystemPromptLoader(search_paths=[first, second])

        prompt = loader.load()

        assert prompt.content == "Second file."
        assert prompt.source == second / "SYSTEM.md"

    def test_load_custom_filename(self, tmp_path: Path) -> None:
        (tmp_path / "CUSTOM.md").write_text("Custom.", encoding="utf-8")
        loader = SystemPromptLoader(search_paths=[tmp_path], filename="CUSTOM.md")

        prompt = loader.load()

        assert prompt.content == "Custom."
        assert prompt.source == tmp_path / "CUSTOM.md"

    def test_load_for_workspace_rejects_symlink_outside(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        outside = tmp_path / "outside"
        workspace.mkdir()
        outside.mkdir()

        secret = outside / "secret.txt"
        secret.write_text("leaked", encoding="utf-8")

        link = workspace / "SYSTEM.md"
        link.symlink_to(secret)

        loader = SystemPromptLoader.for_workspace(workspace)
        prompt = loader.load()

        assert prompt.content == DEFAULT_SYSTEM_PROMPT
        assert prompt.source is None

    def test_load_for_workspace_allows_symlink_inside(self, tmp_path: Path) -> None:
        real = tmp_path / "real.md"
        real.write_text("ok", encoding="utf-8")

        link = tmp_path / "SYSTEM.md"
        link.symlink_to(real)

        loader = SystemPromptLoader.for_workspace(tmp_path)
        prompt = loader.load()

        assert prompt.content == "ok"
        assert prompt.source == tmp_path / "SYSTEM.md"

    def test_load_sandbox_matches_equivalent_workspace_path(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        outside = tmp_path / "outside"
        workspace.mkdir()
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("leaked", encoding="utf-8")
        (workspace / "SYSTEM.md").symlink_to(secret)

        loader = SystemPromptLoader(
            search_paths=[workspace / "."],
            sandbox_root=workspace,
        )
        prompt = loader.load()

        assert prompt.content == DEFAULT_SYSTEM_PROMPT
        assert prompt.source is None

    def test_load_without_sandbox_follows_symlink(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        outside = tmp_path / "outside"
        workspace.mkdir()
        outside.mkdir()

        secret = outside / "secret.txt"
        secret.write_text("leaked", encoding="utf-8")

        link = workspace / "SYSTEM.md"
        link.symlink_to(secret)

        loader = SystemPromptLoader(search_paths=[workspace])
        prompt = loader.load()

        assert prompt.content == "leaked"
        assert prompt.source == workspace / "SYSTEM.md"
