from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from koda.sessions import InMemorySessionStore, SessionManager
from koda_service.services.in_process.catalog import CatalogService
from koda_service.services.in_process.chat import ChatService
from koda_service.services.in_process.runtime import InProcessRuntimeFactory
from koda_service.services.in_process.sessions import SessionService

from .test_fakes import FakeAgent, registries, settings


def test_runtime_factory_creates_runtime_and_passes_shared_dependencies() -> None:
    captured_kwargs: dict[str, Any] = {}
    session_manager = SessionManager(InMemorySessionStore())
    current_registries = registries()

    def fake_create_agent(**kwargs: object) -> FakeAgent:
        captured_kwargs.update(kwargs)
        return FakeAgent()

    factory = InProcessRuntimeFactory(
        settings=settings(),
        sandbox_dir=Path("/tmp/koda-test"),
        session_manager=session_manager,
        registries=current_registries,
        create_agent=cast("Any", fake_create_agent),
    )

    runtime = factory.create()

    assert isinstance(runtime.chat, ChatService)
    assert isinstance(runtime.sessions, SessionService)
    assert isinstance(runtime.catalog, CatalogService)
    assert captured_kwargs["settings"] is factory.settings
    assert captured_kwargs["sandbox_dir"] == Path("/tmp/koda-test")
    assert captured_kwargs["session_manager"] is session_manager
    assert captured_kwargs["registries"] is current_registries
    assert captured_kwargs["prompt_overrides"] is None
