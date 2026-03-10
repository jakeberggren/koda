from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

import pytest

from koda.llm.exceptions import LLMAuthenticationError
from koda.llm.models import ModelDefinition as CoreModelDefinition
from koda.llm.models import ThinkingLevel
from koda.llm.registry import ModelRegistry, ProviderRegistry
from koda.llm.types import LLMTextDelta as CoreTextDelta
from koda.messages import AssistantMessage as CoreAssistantMessage
from koda.messages import UserMessage as CoreUserMessage
from koda.sessions import Session
from koda_api import bootstrap
from koda_api.backends.in_process import InProcessBackend
from koda_common.contracts import BackendAuthenticationError, TextDelta, UserMessage

if TYPE_CHECKING:
    from koda_common.settings import SettingsManager


class _FakeAgent:
    def __init__(
        self,
        events: list[object] | None = None,
        session: Session | None = None,
        sessions: list[Session] | None = None,
        delete_return: Session | None = None,
    ) -> None:
        self._events = events or []
        self._session = session or Session()
        self._sessions = sessions or [self._session]
        self._delete_return = delete_return
        self.active_session = self._session

    async def run(self, _message: str):
        for event in self._events:
            yield event

    def list_sessions(self) -> list[Session]:
        return self._sessions

    def new_session(self) -> Session:
        return self._session

    def switch_session(self, _session_id: UUID) -> Session:
        return self._session

    def delete_session(self, _session_id: UUID) -> Session | None:
        return self._delete_return


class _FailingAuthAgent:
    async def run(self, _message: str):
        raise LLMAuthenticationError("openai", Exception("bad key"))
        yield  # pragma: no cover


def _settings() -> SettingsManager:
    return cast("SettingsManager", SimpleNamespace(provider="openai", model="gpt-5.2"))


def _registries() -> bootstrap.Registries:
    return bootstrap.Registries(
        model_registry=ModelRegistry(),
        provider_registry=ProviderRegistry(),
    )


def _core_session(
    *,
    content: str = "hello",
    name: str | None = None,
    session_id: UUID | None = None,
) -> Session:
    return Session(
        session_id=session_id or uuid4(),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        messages=[CoreUserMessage(content=content)],
        name=name,
    )


@pytest.mark.asyncio
async def test_chat_maps_core_events_to_stream_events() -> None:
    fake_agent = _FakeAgent(events=[CoreTextDelta(text="hello")])
    backend = InProcessBackend(
        settings=_settings(),
        sandbox_dir=Path.cwd(),
        registries=_registries(),
        agent_factory=lambda **_kwargs: fake_agent,
    )
    events = [event async for event in backend.chat("hi")]

    assert len(events) == 1
    assert isinstance(events[0], TextDelta)
    assert events[0].text == "hello"


@pytest.mark.asyncio
async def test_chat_maps_auth_error_to_backend_auth_error() -> None:
    backend = InProcessBackend(
        settings=_settings(),
        sandbox_dir=Path.cwd(),
        registries=_registries(),
        agent_factory=lambda **_kwargs: _FailingAuthAgent(),
    )

    with pytest.raises(BackendAuthenticationError):
        _ = [event async for event in backend.chat("hi")]


def test_switch_session_returns_contract_session_and_messages() -> None:
    session_id = uuid4()
    core_session = Session(
        session_id=session_id,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        messages=[
            CoreUserMessage(content="hello"),
            CoreAssistantMessage(content="hi there"),
        ],
        name="Example Session",
    )
    backend = InProcessBackend(
        settings=_settings(),
        sandbox_dir=Path.cwd(),
        registries=_registries(),
        agent_factory=lambda **_kwargs: _FakeAgent(session=core_session),
    )

    mapped_session, mapped_messages = backend.switch_session(session_id)

    assert mapped_session.session_id == session_id
    assert mapped_session.name == "Example Session"
    assert len(mapped_messages) == 2  # noqa: PLR2004
    assert isinstance(mapped_messages[0], UserMessage)
    assert mapped_messages[0].content == "hello"


def test_reconfigure_rebuilds_agent() -> None:
    created_agents: list[object] = []

    def _fake_create_agent(**_kwargs: object) -> object:
        agent = object()
        created_agents.append(agent)
        return agent

    backend = InProcessBackend(
        settings=_settings(),
        sandbox_dir=Path.cwd(),
        registries=_registries(),
        agent_factory=cast("Any", _fake_create_agent),
    )

    backend.reconfigure()

    assert len(created_agents) == 2  # noqa: PLR2004


def test_list_providers_delegates_to_registry() -> None:
    fake_provider_registry = ProviderRegistry()
    fake_provider_registry.supported = lambda: ["openai", "anthropic"]  # type: ignore[method-assign]
    model_registry = ModelRegistry()
    backend = InProcessBackend(
        settings=_settings(),
        sandbox_dir=Path.cwd(),
        registries=bootstrap.Registries(
            model_registry=model_registry,
            provider_registry=fake_provider_registry,
        ),
        agent_factory=lambda **_kwargs: _FakeAgent(),
    )
    assert backend.list_providers() == ["openai", "anthropic"]


def test_list_models_maps_contract_models(monkeypatch: pytest.MonkeyPatch) -> None:
    core_model = CoreModelDefinition(
        id="gpt-5.2",
        name="GPT 5.2",
        provider="openai",
        thinking={ThinkingLevel.HIGH},
    )
    fake_model_registry = ModelRegistry()
    monkeypatch.setattr(fake_model_registry, "supported", lambda _provider=None: [core_model])
    provider_registry = ProviderRegistry()
    monkeypatch.setattr(provider_registry, "supported", list)
    backend = InProcessBackend(
        settings=_settings(),
        sandbox_dir=Path.cwd(),
        registries=bootstrap.Registries(
            model_registry=fake_model_registry,
            provider_registry=provider_registry,
        ),
        agent_factory=lambda **_kwargs: _FakeAgent(),
    )
    models = backend.list_models("openai")

    assert len(models) == 1
    assert models[0].id == "gpt-5.2"
    assert models[0].thinking


def test_list_sessions_filters_empty_sessions() -> None:
    non_empty = _core_session(content="keep me")
    empty = Session()
    fake_agent = _FakeAgent(sessions=[empty, non_empty], session=non_empty)
    backend = InProcessBackend(
        settings=_settings(),
        sandbox_dir=Path.cwd(),
        registries=_registries(),
        agent_factory=lambda **_kwargs: fake_agent,
    )
    sessions = backend.list_sessions()

    assert len(sessions) == 1
    assert sessions[0].name.startswith("keep me")


def test_new_session_maps_session_info() -> None:
    session = _core_session(content="new content")
    fake_agent = _FakeAgent(session=session)
    backend = InProcessBackend(
        settings=_settings(),
        sandbox_dir=Path.cwd(),
        registries=_registries(),
        agent_factory=lambda **_kwargs: fake_agent,
    )
    mapped = backend.new_session()

    assert mapped.session_id == session.session_id
    assert mapped.message_count == 1


def test_delete_session_returns_none_when_core_returns_none() -> None:
    fake_agent = _FakeAgent(delete_return=None)
    backend = InProcessBackend(
        settings=_settings(),
        sandbox_dir=Path.cwd(),
        registries=_registries(),
        agent_factory=lambda **_kwargs: fake_agent,
    )

    assert backend.delete_session(uuid4()) is None


def test_delete_session_maps_session_when_core_returns_session() -> None:
    returned = _core_session(content="after delete", name="Recovered")
    fake_agent = _FakeAgent(delete_return=returned)
    backend = InProcessBackend(
        settings=_settings(),
        sandbox_dir=Path.cwd(),
        registries=_registries(),
        agent_factory=lambda **_kwargs: fake_agent,
    )

    mapped = backend.delete_session(uuid4())

    assert mapped is not None
    assert mapped.name == "Recovered"
