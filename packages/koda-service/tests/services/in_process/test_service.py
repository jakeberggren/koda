from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import BaseModel

from koda.agents.agent import Agent, AgentConfig
from koda.llm.types import LLMEvent, LLMRequest, LLMResponse
from koda.messages import AssistantMessage
from koda.sessions import InMemorySessionStore, SessionManager
from koda_service.services.in_process.service import InProcessKodaService


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
            "get_api_key",
        ]
    )
    settings.provider = "openai"
    settings.model = "gpt-5.2"
    settings.thinking = "none"
    settings.allow_web_search = False
    settings.allow_extended_prompt_retention = False
    settings.get_api_key.return_value = "test-key"
    return settings


def _make_service(
    *,
    session_store: InMemorySessionStore | None = None,
    agent_config: Mock | None = None,
) -> InProcessKodaService:
    return InProcessKodaService(
        settings=_make_settings(),
        sandbox_dir=Path("/tmp"),
        session_store=session_store or InMemorySessionStore(),
        agent_config=agent_config or Mock(spec=["build"]),
    )


def test_service_starts_without_active_session() -> None:
    service = _make_service()

    assert service.list_sessions() == []
    assert service.active_session() is None


@pytest.mark.asyncio
async def test_chat_creates_session_lazily_on_first_message() -> None:
    fake_llm = _FakeLLM()
    agent_config = Mock(spec=["build"])

    def _build_agent(
        _settings: Mock,
        session_manager: SessionManager,
        *,
        sandbox_dir: Path,
    ) -> Agent:
        assert sandbox_dir == Path("/tmp")
        return Agent(
            llm=fake_llm,
            config=AgentConfig(),
            session_manager=session_manager,
            tools=None,
        )

    agent_config.build.side_effect = _build_agent
    service = _make_service(agent_config=agent_config)

    events = [event async for event in service.chat("hello")]

    assert events == []
    sessions = service.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].message_count == 1
    active = service.active_session()
    assert active is not None
    assert active.session_id == sessions[0].session_id
    assert fake_llm.last_request is not None
    assert fake_llm.last_request.messages[0].content == "hello"
