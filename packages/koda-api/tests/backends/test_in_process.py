from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest

from koda.messages import AssistantMessage as CoreAssistantMessage
from koda.messages import UserMessage as CoreUserMessage
from koda.providers.events import TextDelta as CoreTextDelta
from koda.providers.exceptions import ProviderAuthenticationError
from koda.providers.registry import ModelDefinition as CoreModelDefinition
from koda.providers.registry import ThinkingLevel
from koda.sessions import Session
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
        raise ProviderAuthenticationError("openai", Exception("bad key"))
        yield  # pragma: no cover


def _settings() -> SettingsManager:
    return cast("SettingsManager", SimpleNamespace(provider="openai", model="gpt-5.2"))


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
async def test_chat_maps_core_events_to_stream_events(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_agent = _FakeAgent(events=[CoreTextDelta(text="hello")])
    monkeypatch.setattr(InProcessBackend, "_create_agent", lambda _self: fake_agent)

    backend = InProcessBackend(settings=_settings(), sandbox_dir=Path.cwd())
    events = [event async for event in backend.chat("hi")]

    assert len(events) == 1
    assert isinstance(events[0], TextDelta)
    assert events[0].text == "hello"


@pytest.mark.asyncio
async def test_chat_maps_auth_error_to_backend_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(InProcessBackend, "_create_agent", lambda _self: _FailingAuthAgent())
    backend = InProcessBackend(settings=_settings(), sandbox_dir=Path.cwd())

    with pytest.raises(BackendAuthenticationError):
        _ = [event async for event in backend.chat("hi")]


def test_switch_session_returns_contract_session_and_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    monkeypatch.setattr(
        InProcessBackend,
        "_create_agent",
        lambda _self: _FakeAgent(session=core_session),
    )
    backend = InProcessBackend(settings=_settings(), sandbox_dir=Path.cwd())

    mapped_session, mapped_messages = backend.switch_session(session_id)

    assert mapped_session.session_id == session_id
    assert mapped_session.name == "Example Session"
    assert len(mapped_messages) == 2  # noqa: PLR2004
    assert isinstance(mapped_messages[0], UserMessage)
    assert mapped_messages[0].content == "hello"


def test_reconfigure_rebuilds_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    created_agents: list[object] = []

    def _fake_create_agent(_self: InProcessBackend) -> object:
        agent = object()
        created_agents.append(agent)
        return agent

    monkeypatch.setattr(InProcessBackend, "_create_agent", _fake_create_agent)
    backend = InProcessBackend(settings=_settings(), sandbox_dir=Path.cwd())

    backend.reconfigure()

    assert len(created_agents) == 2  # noqa: PLR2004


def test_list_providers_delegates_to_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_registry = SimpleNamespace(supported=lambda: ["openai", "anthropic"])
    monkeypatch.setattr("koda_api.backends.in_process.get_provider_registry", lambda: fake_registry)
    monkeypatch.setattr(InProcessBackend, "_create_agent", lambda _self: _FakeAgent())

    backend = InProcessBackend(settings=_settings(), sandbox_dir=Path.cwd())
    assert backend.list_providers() == ["openai", "anthropic"]


def test_list_models_maps_contract_models(monkeypatch: pytest.MonkeyPatch) -> None:
    core_model = CoreModelDefinition(
        id="gpt-5.2",
        name="GPT 5.2",
        provider="openai",
        thinking={ThinkingLevel.HIGH},
    )
    fake_model_registry = SimpleNamespace(supported=lambda _provider=None: [core_model])
    monkeypatch.setattr(
        "koda_api.backends.in_process.get_model_registry", lambda: fake_model_registry
    )
    monkeypatch.setattr(InProcessBackend, "_create_agent", lambda _self: _FakeAgent())

    backend = InProcessBackend(settings=_settings(), sandbox_dir=Path.cwd())
    models = backend.list_models("openai")

    assert len(models) == 1
    assert models[0].id == "gpt-5.2"
    assert models[0].thinking


def test_list_sessions_filters_empty_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    non_empty = _core_session(content="keep me")
    empty = Session()
    fake_agent = _FakeAgent(sessions=[empty, non_empty], session=non_empty)
    monkeypatch.setattr(InProcessBackend, "_create_agent", lambda _self: fake_agent)

    backend = InProcessBackend(settings=_settings(), sandbox_dir=Path.cwd())
    sessions = backend.list_sessions()

    assert len(sessions) == 1
    assert sessions[0].name.startswith("keep me")


def test_new_session_maps_session_info(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _core_session(content="new content")
    fake_agent = _FakeAgent(session=session)
    monkeypatch.setattr(InProcessBackend, "_create_agent", lambda _self: fake_agent)

    backend = InProcessBackend(settings=_settings(), sandbox_dir=Path.cwd())
    mapped = backend.new_session()

    assert mapped.session_id == session.session_id
    assert mapped.message_count == 1


def test_delete_session_returns_none_when_core_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_agent = _FakeAgent(delete_return=None)
    monkeypatch.setattr(InProcessBackend, "_create_agent", lambda _self: fake_agent)
    backend = InProcessBackend(settings=_settings(), sandbox_dir=Path.cwd())

    assert backend.delete_session(uuid4()) is None


def test_delete_session_maps_session_when_core_returns_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    returned = _core_session(content="after delete", name="Recovered")
    fake_agent = _FakeAgent(delete_return=returned)
    monkeypatch.setattr(InProcessBackend, "_create_agent", lambda _self: fake_agent)
    backend = InProcessBackend(settings=_settings(), sandbox_dir=Path.cwd())

    mapped = backend.delete_session(uuid4())

    assert mapped is not None
    assert mapped.name == "Recovered"
