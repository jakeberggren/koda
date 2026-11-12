"""Tests for the Runtime: building the agent from the settings, sessions, and readiness."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from koda.agent import AgentIterationStarted, AgentTurnCompleted, AgentTurnStarted
from koda.llm import Catalog
from koda.llm.exceptions import LLMAuthenticationError
from koda.sessions import InMemorySessionStore, Session, SessionNotFoundError
from koda_common.settings import SecretsPermissionError
from koda_common.settings.credentials import ApiKeyCredential
from koda_tui import strings
from koda_tui.runtime import Runtime

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pydantic import BaseModel

    from koda.llm import Credentials, Model
    from koda.llm.types import LLMEvent, LLMRequest, LLMResponse
    from koda.messages import AssistantMessage


class _FakeLLM:
    """Ends every response without output, and remembers the last request."""

    def __init__(self) -> None:
        self.last_request: LLMRequest | None = None

    async def generate_stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        self.last_request = request
        return
        yield

    async def generate(self, request: LLMRequest) -> LLMResponse[AssistantMessage]:
        raise NotImplementedError

    async def generate_structured(
        self, request: LLMRequest, schema: type[BaseModel]
    ) -> LLMResponse[BaseModel]:
        raise NotImplementedError


class _Connect:
    """Connects every model to the same fake LLM, counting the connections."""

    def __init__(self) -> None:
        self.llm = _FakeLLM()
        self.calls = 0

    async def __call__(self, model: Model, credentials: Credentials) -> _FakeLLM:
        self.calls += 1
        await asyncio.sleep(0)
        return self.llm


def _settings(provider: str | None = "openai", model: str | None = "gpt-5.2") -> Mock:
    settings = Mock()
    settings.provider = provider
    settings.model = model
    settings.thinking = "none"
    settings.allow_web_search = False
    settings.allow_extended_prompt_retention = False
    settings.bash_execution_sandbox = "host"
    credentials = {
        "openai:api-key": ApiKeyCredential(type="api_key", value="key"),
        "anthropic:api-key": ApiKeyCredential(type="api_key", value="key"),
    }
    settings.get_credential.side_effect = credentials.get
    return settings


@pytest.fixture
def connect() -> _Connect:
    return _Connect()


def _runtime(
    connect: _Connect, workspace: Path = Path("/tmp"), settings: Mock | None = None
) -> Runtime:
    catalog, _warnings = Catalog.load()
    return Runtime(
        settings or _settings(),
        workspace,
        catalog=catalog,
        store=InMemorySessionStore(),
        connect=connect,
    )


async def _run(runtime: Runtime, text: str = "hello") -> list[object]:
    return [event async for event in runtime.run(text)]


def _instructions(connect: _Connect) -> str:
    assert connect.llm.last_request is not None
    assert connect.llm.last_request.instructions is not None
    return connect.llm.last_request.instructions


class TestRunning:
    async def test_run_streams_the_turn_and_saves_the_session(self, connect: _Connect) -> None:
        runtime = _runtime(connect)
        assert runtime.store.list_sessions() == []

        events = await _run(runtime)

        assert [type(event) for event in events] == [
            AgentTurnStarted,
            AgentIterationStarted,
            AgentTurnCompleted,
        ]
        [saved] = runtime.store.list_sessions()
        assert saved.session_id == runtime.session.session_id
        assert saved.message_count == 1

    async def test_the_agent_is_built_once_for_concurrent_runs(self, connect: _Connect) -> None:
        runtime = _runtime(connect)

        await asyncio.gather(*(_run(runtime) for _ in range(3)))

        assert connect.calls == 1

    async def test_changed_settings_rebuild_the_agent(self, connect: _Connect) -> None:
        runtime = _runtime(connect)
        await _run(runtime)

        runtime.settings_changed()
        await _run(runtime)

        assert connect.calls == 2

    async def test_thinking_resolves_to_the_models_first_mode(self, connect: _Connect) -> None:
        runtime = _runtime(connect, settings=_settings("anthropic", "claude-fable-5"))

        await _run(runtime)

        assert connect.llm.last_request is not None
        assert connect.llm.last_request.options.thinking == "low"

    async def test_connect_errors_reach_the_caller(self) -> None:
        async def fail(_model: Model, _credentials: Credentials) -> _FakeLLM:
            raise LLMAuthenticationError("openai", RuntimeError("refresh failed"))

        catalog, _warnings = Catalog.load()
        runtime = Runtime(
            _settings(), Path("/tmp"), catalog=catalog, store=InMemorySessionStore(), connect=fail
        )

        with pytest.raises(LLMAuthenticationError):
            await _run(runtime)


class TestSessions:
    async def test_workspace_context_is_read_once_per_session(
        self, connect: _Connect, tmp_path: Path
    ) -> None:
        (tmp_path / "AGENTS.md").write_text("First instructions.", encoding="utf-8")
        runtime = _runtime(connect, tmp_path)
        await _run(runtime)

        (tmp_path / "AGENTS.md").write_text("Second instructions.", encoding="utf-8")
        await _run(runtime)
        assert "First instructions." in _instructions(connect)

        runtime.new_session()
        await _run(runtime)
        assert "Second instructions." in _instructions(connect)

    async def test_opening_another_session_reads_the_workspace_context_again(
        self, connect: _Connect, tmp_path: Path
    ) -> None:
        (tmp_path / "AGENTS.md").write_text("First instructions.", encoding="utf-8")
        runtime = _runtime(connect, tmp_path)
        await _run(runtime)
        first = runtime.session
        runtime.new_session()
        await _run(runtime)

        (tmp_path / "AGENTS.md").write_text("Second instructions.", encoding="utf-8")
        runtime.open_session(first.session_id)
        await _run(runtime)

        assert "Second instructions." in _instructions(connect)
        assert runtime.session.message_count == 2

    def test_opening_an_unknown_session_fails(self, connect: _Connect) -> None:
        runtime = _runtime(connect)

        with pytest.raises(SessionNotFoundError):
            runtime.open_session(Session().session_id)

    async def test_deleting_the_current_session_starts_a_new_one(self, connect: _Connect) -> None:
        runtime = _runtime(connect)
        await _run(runtime)
        deleted = runtime.session

        runtime.delete_session(deleted.session_id)

        assert runtime.session.session_id != deleted.session_id
        assert runtime.store.list_sessions() == []

    def test_deleting_the_unsaved_current_session_starts_a_new_one(self, connect: _Connect) -> None:
        runtime = _runtime(connect)
        unsaved = runtime.session

        runtime.delete_session(unsaved.session_id)

        assert runtime.session.session_id != unsaved.session_id

    def test_deleting_an_unknown_session_fails(self, connect: _Connect) -> None:
        runtime = _runtime(connect)

        with pytest.raises(SessionNotFoundError):
            runtime.delete_session(Session().session_id)


class TestSystemPrompt:
    async def test_workspace_system_prompt_replaces_the_default(
        self, connect: _Connect, tmp_path: Path
    ) -> None:
        (tmp_path / "SYSTEM.md").write_text("Workspace system prompt.", encoding="utf-8")
        runtime = _runtime(connect, tmp_path)

        await _run(runtime)

        assert _instructions(connect) == "Workspace system prompt."

    async def test_global_system_prompt_replaces_the_default(
        self, connect: _Connect, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace, home = tmp_path / "workspace", tmp_path / "home"
        workspace.mkdir()
        home.mkdir()
        (home / "SYSTEM.md").write_text("Global system prompt.", encoding="utf-8")
        monkeypatch.setattr("koda.prompts.loader.koda_home_dir", lambda: home)
        runtime = _runtime(connect, workspace)

        await _run(runtime)

        assert _instructions(connect) == "Global system prompt."


class TestIssue:
    def test_no_issue_when_the_selected_model_is_connected(self, connect: _Connect) -> None:
        assert _runtime(connect).issue() is None

    def test_setup_is_required_without_credentials(self, connect: _Connect) -> None:
        settings = _settings()
        settings.get_credential.side_effect = None
        settings.get_credential.return_value = None

        assert _runtime(connect, settings=settings).issue() == strings.Screen.Status.SETUP_REQUIRED

    def test_selection_is_required_without_a_model(self, connect: _Connect) -> None:
        runtime = _runtime(connect, settings=_settings(model=None))

        assert runtime.issue() == strings.Screen.Status.SELECTION_REQUIRED

    def test_an_unknown_model_is_unavailable(self, connect: _Connect) -> None:
        runtime = _runtime(connect, settings=_settings(model="missing"))

        assert runtime.issue() == strings.Screen.Status.MODEL_UNAVAILABLE

    def test_a_model_of_an_unconnected_provider_is_unavailable(self, connect: _Connect) -> None:
        runtime = _runtime(connect, settings=_settings("bergetai", "google/gemma-4-31B-it"))

        assert runtime.issue() == strings.Screen.Status.MODEL_UNAVAILABLE

    def test_an_unreadable_secrets_file_is_reported(self, connect: _Connect) -> None:
        settings = _settings()
        settings.get_credential.side_effect = SecretsPermissionError(
            path=Path("secrets.json"), error=PermissionError("denied")
        )

        assert _runtime(connect, settings=settings).issue() is not None
