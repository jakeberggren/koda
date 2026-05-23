from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import BaseModel

from koda.agent import AgentIterationStarted, AgentTurnCompleted, AgentTurnStarted
from koda.llm.types import LLMEvent, LLMRequest, LLMResponse
from koda.messages import AssistantMessage
from koda.sessions import InMemorySessionStore
from koda_service import ChatRequest, ServiceStatusCode
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
            "get_api_key",
        ]
    )
    settings.provider = "openai"
    settings.model = "gpt-5.2"
    settings.thinking = "none"
    settings.allow_web_search = False
    settings.allow_extended_prompt_retention = False
    settings.langfuse_tracing_enabled = False
    settings.bash_execution_sandbox = "none"
    settings.get_api_key.return_value = "test-key"
    return settings


def _make_service(
    *,
    cwd: Path = Path("/tmp"),
    session_store: InMemorySessionStore | None = None,
    llm: _FakeLLM | None = None,
) -> LocalKodaService:
    return LocalKodaService(
        settings=_make_settings(),
        runtime=LocalRuntimeConfig(
            cwd=cwd,
            sandbox_dir=cwd,
            llm=llm,
        ),
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
