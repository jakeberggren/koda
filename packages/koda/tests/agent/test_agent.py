"""Tests for koda.agent.agent."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from koda.agent import Agent, AgentConfig
from koda.context.manager import ContextManager


class TestAgent:
    @pytest.fixture
    def mock_llm(self) -> MagicMock:
        llm = MagicMock()
        llm.generate_stream = AsyncMock()
        return llm

    def test_appends_context_manager_content_to_system_prompt(
        self,
        mock_llm: MagicMock,
        tmp_path: Path,
    ) -> None:
        (tmp_path / "AGENTS.md").write_text("Always run tests before committing.", encoding="utf-8")
        context_manager = ContextManager.from_workspace(tmp_path)

        agent = Agent(llm=mock_llm, config=AgentConfig(), context_manager=context_manager)
        instructions = agent.runner.resolve_instructions()

        assert instructions is not None
        assert "You are Koda" in instructions
        assert "Always run tests before committing." in instructions
        assert instructions.index("Always run tests before committing") > instructions.index(
            "You are Koda"
        )

    def test_snapshots_context_manager_at_construction(
        self,
        mock_llm: MagicMock,
        tmp_path: Path,
    ) -> None:
        path = tmp_path / "AGENTS.md"
        path.write_text("Initial instructions.", encoding="utf-8")

        agent = Agent(
            llm=mock_llm,
            config=AgentConfig(),
            context_manager=ContextManager.from_workspace(tmp_path),
        )
        path.write_text("Changed instructions.", encoding="utf-8")

        instructions = agent.runner.resolve_instructions()

        assert instructions is not None
        assert "Initial instructions." in instructions
        assert "Changed instructions." not in instructions
