"""Tests for koda.agent.agent: what an Agent sets up for its workspace."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from koda.agent import Agent
from koda.sessions import Session


def _agent(workspace: Path) -> Agent:
    return Agent(MagicMock(), session=Session(), workspace=workspace)


def _instructions(agent: Agent) -> str:
    instructions = agent.runner.resolve_instructions()
    assert instructions is not None
    return instructions


def test_appends_the_workspace_agents_md_to_the_system_prompt(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("Always run tests before committing.", encoding="utf-8")

    instructions = _instructions(_agent(tmp_path))

    assert "You are Koda" in instructions
    assert instructions.index("Always run tests") > instructions.index("You are Koda")


def test_reads_agents_md_once_at_construction(tmp_path: Path) -> None:
    path = tmp_path / "AGENTS.md"
    path.write_text("Initial instructions.", encoding="utf-8")
    agent = _agent(tmp_path)

    path.write_text("Changed instructions.", encoding="utf-8")

    assert "Initial instructions." in _instructions(agent)
    assert "Changed instructions." not in _instructions(agent)


def test_workspace_system_md_replaces_the_default_prompt(tmp_path: Path) -> None:
    (tmp_path / "SYSTEM.md").write_text("Workspace system prompt.", encoding="utf-8")

    assert _instructions(_agent(tmp_path)) == "Workspace system prompt."


def test_global_system_md_replaces_the_default_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, home = tmp_path / "workspace", tmp_path / "home"
    workspace.mkdir()
    home.mkdir()
    (home / "SYSTEM.md").write_text("Global system prompt.", encoding="utf-8")
    monkeypatch.setattr("koda.prompts.loader.koda_home_dir", lambda: home)

    assert _instructions(_agent(workspace)) == "Global system prompt."


def test_works_in_the_current_directory_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    agent = Agent(MagicMock(), session=Session())

    assert agent.workspace == tmp_path.resolve()
    assert agent.tools.context.cwd == tmp_path.resolve()
