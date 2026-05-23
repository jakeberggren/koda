"""Tests for context manager integration with the Agent."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from koda.agent import Agent, AgentConfig
from koda.context.manager import ContextManager


class TestAgentContextIntegration:
    """Integration tests for ContextManager wired into Agent."""

    @pytest.fixture
    def mock_llm(self) -> MagicMock:
        llm = MagicMock()
        llm.generate_stream = AsyncMock()
        return llm

    def test_agent_without_context_manager_uses_base_prompt(self, mock_llm: MagicMock) -> None:
        config = AgentConfig()
        agent = Agent(llm=mock_llm, config=config)
        instructions = agent.runner.resolve_instructions()

        assert instructions is not None
        assert "You are Koda" in instructions
        assert "project_context" not in instructions

    def test_agent_with_context_manager_appends_project_context(
        self,
        mock_llm: MagicMock,
        tmp_path: Path,
    ) -> None:
        (tmp_path / "AGENTS.md").write_text("Always run tests before committing.", encoding="utf-8")
        context_manager = ContextManager.from_workspace(tmp_path)
        config = AgentConfig()

        agent = Agent(llm=mock_llm, config=config, context_manager=context_manager)
        instructions = agent.runner.resolve_instructions()

        assert instructions is not None
        assert "You are Koda" in instructions
        assert "Always run tests before committing." in instructions
        # Should appear after the base prompt
        koda_pos = instructions.index("You are Koda")
        context_pos = instructions.index("Always run tests before committing")
        assert context_pos > koda_pos

    def test_agent_with_empty_context_files_uses_base_prompt(
        self,
        mock_llm: MagicMock,
        tmp_path: Path,
    ) -> None:
        context_manager = ContextManager.from_workspace(tmp_path)
        base_agent = Agent(llm=mock_llm, config=AgentConfig())
        base_instructions = base_agent.runner.resolve_instructions()

        agent = Agent(llm=mock_llm, config=AgentConfig(), context_manager=context_manager)
        instructions = agent.runner.resolve_instructions()

        assert instructions == base_instructions
