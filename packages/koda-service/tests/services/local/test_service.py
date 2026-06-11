import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import BaseModel

from koda.agent import AgentIterationStarted, AgentTurnCompleted, AgentTurnStarted
from koda.llm.exceptions import LLMAuthenticationError
from koda.llm.types import LLMEvent, LLMRequest, LLMResponse
from koda.messages import AssistantMessage
from koda.prompts import SystemPrompt
from koda.sessions import InMemorySessionStore
from koda_common.settings.credentials import ApiKeyCredential
from koda_service import ChatRequest, ServiceStatusCode
from koda_service.exceptions import ServiceAuthenticationError
from koda_service.services.local import LocalKodaService, LocalRuntimeConfig


class _FakeStructuredResponse(BaseModel):
    value: str = "ok"


class _FakeLLM:
    def __init__(self) -> None:
        self.last_request: LLMRequest | None = None

    def generate_stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        self.last_request = request

        async def _stream() -> AsyncIterator[LLMEvent]:
            if False:
                yield

        return _stream()

    async def generate(self, request: LLMRequest) -> LLMResponse[AssistantMessage]:
        self.last_request = request
        return LLMResponse(output=AssistantMessage(content=""))

    async def generate_structured(
        self,
        request: LLMRequest,
        schema: type[_FakeStructuredResponse],
    ) -> LLMResponse[_FakeStructuredResponse]:
        self.last_request = request
        return LLMResponse(output=schema())


def _make_settings() -> Mock:
    settings = Mock(
        spec=[
            "provider",
            "model",
            "thinking",
            "allow_web_search",
            "allow_extended_prompt_retention",
            "langfuse_tracing_enabled",
            "bash_execution_sandbox",
            "credentials",
            "get_credential",
        ]
    )
    settings.provider = "openai"
    settings.model = "gpt-5.2"
    settings.thinking = "none"
    settings.allow_web_search = False
    settings.allow_extended_prompt_retention = False
    settings.langfuse_tracing_enabled = False
    settings.bash_execution_sandbox = "none"
    credential = ApiKeyCredential(type="api_key", value="test-key")
    settings.credentials = {"openai:api-key": credential}
    settings.get_credential.side_effect = settings.credentials.get
    return settings


def _make_service(
    *,
    cwd: Path = Path("/tmp"),
    system_prompt: SystemPrompt | None = None,
    session_store: InMemorySessionStore | None = None,
    llm: _FakeLLM | None = None,
    settings: Mock | None = None,
) -> LocalKodaService:
    runtime_config = (
        LocalRuntimeConfig(
            cwd=cwd,
            sandbox_dir=cwd,
            llm=llm,
            system_prompt=system_prompt,
        )
        if system_prompt is not None
        else LocalRuntimeConfig(
            cwd=cwd,
            sandbox_dir=cwd,
            llm=llm,
        )
    )
    return LocalKodaService(
        settings=settings or _make_settings(),
        runtime=runtime_config,
        session_store=session_store or InMemorySessionStore(),
    )


def test_service_starts_without_active_session() -> None:
    service = _make_service()

    assert service.list_sessions() == []
    assert service.active_session() is None
    assert service.status().code is ServiceStatusCode.READY
    assert service.diagnostics().startup_warnings == []


@pytest.mark.asyncio
async def test_chat_creates_session_lazily_on_first_message() -> None:
    fake_llm = _FakeLLM()
    service = _make_service(llm=fake_llm)

    events = [event async for event in service.chat(ChatRequest(message="hello"))]

    assert len(events) == 3
    assert isinstance(events[0], AgentTurnStarted)
    assert isinstance(events[1], AgentIterationStarted)
    assert isinstance(events[2], AgentTurnCompleted)
    sessions = service.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].message_count == 1
    active = service.active_session()
    assert active is not None
    assert active.session_id == sessions[0].session_id
    assert fake_llm.last_request is not None
    assert fake_llm.last_request.messages[0].content == "hello"


@pytest.mark.asyncio
async def test_chat_resolves_thinking_to_first_supported_model_mode() -> None:
    fake_llm = _FakeLLM()
    settings = _make_settings()
    settings.provider = "anthropic"
    settings.model = "claude-fable-5"
    settings.thinking = "none"
    settings.credentials = {"anthropic:api-key": ApiKeyCredential(type="api_key", value="test-key")}
    settings.get_credential.side_effect = settings.credentials.get
    service = _make_service(llm=fake_llm, settings=settings)

    _events = [event async for event in service.chat(ChatRequest(message="hello"))]

    assert fake_llm.last_request is not None
    assert fake_llm.last_request.options.thinking == "low"
    assert settings.thinking == "none"


async def test_chat_translates_llm_creation_authentication_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _make_service(llm=_FakeLLM())

    async def fail_to_create_agent() -> None:
        raise LLMAuthenticationError("openai", RuntimeError("refresh failed"))

    monkeypatch.setattr(service.runtime, "get_agent", fail_to_create_agent)

    with pytest.raises(ServiceAuthenticationError, match="Authentication failed"):
        _ = [event async for event in service.chat(ChatRequest(message="hello"))]


async def test_runtime_creates_agent_once_for_concurrent_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_llm = _FakeLLM()
    service = _make_service(llm=fake_llm)
    create_calls = 0

    async def create_llm() -> _FakeLLM:
        nonlocal create_calls
        create_calls += 1
        await asyncio.sleep(0)
        return fake_llm

    monkeypatch.setattr(service.runtime, "create_llm", create_llm)

    agents = await asyncio.gather(*(service.runtime.get_agent() for _ in range(3)))

    assert create_calls == 1
    assert agents == [agents[0]] * 3


@pytest.mark.asyncio
async def test_chat_can_target_existing_session() -> None:
    fake_llm = _FakeLLM()
    service = _make_service(llm=fake_llm)
    session = service.create_session()

    events = [
        event
        async for event in service.chat(ChatRequest(message="hello", session_id=session.session_id))
    ]

    assert len(events) == 3
    assert service.active_session() == session


@pytest.mark.asyncio
async def test_workspace_context_is_snapshotted_for_active_session(tmp_path: Path) -> None:
    fake_llm = _FakeLLM()
    (tmp_path / "AGENTS.md").write_text("First instructions.", encoding="utf-8")
    service = _make_service(cwd=tmp_path, llm=fake_llm)

    _ = [event async for event in service.chat(ChatRequest(message="hello"))]
    assert fake_llm.last_request is not None
    assert fake_llm.last_request.instructions is not None
    assert "First instructions." in fake_llm.last_request.instructions

    (tmp_path / "AGENTS.md").write_text("Second instructions.", encoding="utf-8")

    _ = [event async for event in service.chat(ChatRequest(message="again"))]
    assert fake_llm.last_request is not None
    assert fake_llm.last_request.instructions is not None
    assert "First instructions." in fake_llm.last_request.instructions
    assert "Second instructions." not in fake_llm.last_request.instructions


@pytest.mark.asyncio
async def test_workspace_context_is_preserved_when_reusing_active_session_id(
    tmp_path: Path,
) -> None:
    fake_llm = _FakeLLM()
    (tmp_path / "AGENTS.md").write_text("First instructions.", encoding="utf-8")
    service = _make_service(cwd=tmp_path, llm=fake_llm)

    _ = [event async for event in service.chat(ChatRequest(message="hello"))]
    active = service.active_session()
    assert active is not None

    (tmp_path / "AGENTS.md").write_text("Second instructions.", encoding="utf-8")

    _ = [
        event
        async for event in service.chat(ChatRequest(message="again", session_id=active.session_id))
    ]
    assert fake_llm.last_request is not None
    assert fake_llm.last_request.instructions is not None
    assert "First instructions." in fake_llm.last_request.instructions
    assert "Second instructions." not in fake_llm.last_request.instructions


@pytest.mark.asyncio
async def test_workspace_context_reloads_for_new_session(tmp_path: Path) -> None:
    fake_llm = _FakeLLM()
    (tmp_path / "AGENTS.md").write_text("First instructions.", encoding="utf-8")
    service = _make_service(cwd=tmp_path, llm=fake_llm)

    _ = [event async for event in service.chat(ChatRequest(message="hello"))]

    (tmp_path / "AGENTS.md").write_text("Second instructions.", encoding="utf-8")
    service.create_session()

    _ = [event async for event in service.chat(ChatRequest(message="new session"))]
    assert fake_llm.last_request is not None
    assert fake_llm.last_request.instructions is not None
    assert "Second instructions." in fake_llm.last_request.instructions
    assert "First instructions." not in fake_llm.last_request.instructions


@pytest.mark.asyncio
async def test_workspace_context_reloads_after_switching_sessions(tmp_path: Path) -> None:
    fake_llm = _FakeLLM()
    (tmp_path / "AGENTS.md").write_text("First instructions.", encoding="utf-8")
    service = _make_service(cwd=tmp_path, llm=fake_llm)

    first_session = service.create_session()
    _ = [
        event
        async for event in service.chat(
            ChatRequest(message="first", session_id=first_session.session_id)
        )
    ]
    second_session = service.create_session()
    (tmp_path / "AGENTS.md").write_text("Second instructions.", encoding="utf-8")

    _ = [
        event
        async for event in service.chat(
            ChatRequest(message="second", session_id=second_session.session_id)
        )
    ]
    assert fake_llm.last_request is not None
    assert fake_llm.last_request.instructions is not None
    assert "Second instructions." in fake_llm.last_request.instructions
    assert "First instructions." not in fake_llm.last_request.instructions


@pytest.mark.asyncio
async def test_workspace_context_reloads_after_deleting_active_session(tmp_path: Path) -> None:
    fake_llm = _FakeLLM()
    (tmp_path / "AGENTS.md").write_text("First instructions.", encoding="utf-8")
    service = _make_service(cwd=tmp_path, llm=fake_llm)

    _ = [event async for event in service.chat(ChatRequest(message="hello"))]
    active = service.active_session()
    assert active is not None
    (tmp_path / "AGENTS.md").write_text("Second instructions.", encoding="utf-8")

    service.delete_session(active.session_id)
    _ = [event async for event in service.chat(ChatRequest(message="new active"))]

    assert fake_llm.last_request is not None
    assert fake_llm.last_request.instructions is not None
    assert "Second instructions." in fake_llm.last_request.instructions
    assert "First instructions." not in fake_llm.last_request.instructions


@pytest.mark.asyncio
async def test_workspace_context_preserved_after_deleting_inactive_session(tmp_path: Path) -> None:
    fake_llm = _FakeLLM()
    (tmp_path / "AGENTS.md").write_text("First instructions.", encoding="utf-8")
    service = _make_service(cwd=tmp_path, llm=fake_llm)

    inactive = service.create_session()
    _ = [
        event
        async for event in service.chat(
            ChatRequest(message="inactive", session_id=inactive.session_id)
        )
    ]
    active = service.create_session()
    _ = [
        event
        async for event in service.chat(ChatRequest(message="active", session_id=active.session_id))
    ]
    (tmp_path / "AGENTS.md").write_text("Second instructions.", encoding="utf-8")

    service.delete_session(inactive.session_id)
    _ = [
        event
        async for event in service.chat(
            ChatRequest(message="still active", session_id=active.session_id)
        )
    ]

    assert fake_llm.last_request is not None
    assert fake_llm.last_request.instructions is not None
    assert "First instructions." in fake_llm.last_request.instructions
    assert "Second instructions." not in fake_llm.last_request.instructions


@pytest.mark.asyncio
async def test_workspace_system_prompt_overrides_config_prompt(tmp_path: Path) -> None:
    fake_llm = _FakeLLM()
    (tmp_path / "SYSTEM.md").write_text("Workspace system prompt.", encoding="utf-8")
    service = _make_service(
        cwd=tmp_path,
        llm=fake_llm,
        system_prompt=SystemPrompt(content="Configured system prompt."),
    )

    _ = [event async for event in service.chat(ChatRequest(message="hello"))]

    assert fake_llm.last_request is not None
    assert fake_llm.last_request.instructions == "Workspace system prompt."


@pytest.mark.asyncio
async def test_global_system_prompt_overrides_config_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_llm = _FakeLLM()
    workspace = tmp_path / "workspace"
    home = tmp_path / "home"
    workspace.mkdir()
    home.mkdir()
    (home / "SYSTEM.md").write_text("Global system prompt.", encoding="utf-8")
    monkeypatch.setattr("koda.prompts.loader.koda_home_dir", lambda: home)
    service = _make_service(
        cwd=workspace,
        llm=fake_llm,
        system_prompt=SystemPrompt(content="Configured system prompt."),
    )

    _ = [event async for event in service.chat(ChatRequest(message="hello"))]

    assert fake_llm.last_request is not None
    assert fake_llm.last_request.instructions == "Global system prompt."


@pytest.mark.asyncio
async def test_config_prompt_used_when_system_prompt_files_absent(tmp_path: Path) -> None:
    fake_llm = _FakeLLM()
    service = _make_service(
        cwd=tmp_path,
        llm=fake_llm,
        system_prompt=SystemPrompt(content="Configured system prompt."),
    )

    _ = [event async for event in service.chat(ChatRequest(message="hello"))]

    assert fake_llm.last_request is not None
    assert fake_llm.last_request.instructions == "Configured system prompt."
