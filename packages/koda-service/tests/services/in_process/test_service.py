from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

from koda_service.services.in_process.catalog import CatalogService
from koda_service.services.in_process.chat import ChatService
from koda_service.services.in_process.runtime import InProcessRuntime
from koda_service.services.in_process.service import InProcessKodaService
from koda_service.services.in_process.sessions import SessionService

from .test_fakes import FakeAgent, runtime_factory, settings

if TYPE_CHECKING:
    from koda_service.services.in_process.runtime import InProcessRuntimeFactory


EXPECTED_AGENT_REBUILDS = 2


def test_reconfigure_rebuilds_agent() -> None:
    created_agents: list[object] = []

    def fake_create_agent(**_kwargs: object) -> object:
        agent = object()
        created_agents.append(agent)
        return agent

    service = InProcessKodaService(
        runtime_factory=runtime_factory(
            create_agent=cast("Any", fake_create_agent),
        ),
    )

    service.reconfigure()

    assert len(created_agents) == EXPECTED_AGENT_REBUILDS


def test_telemetry_initializes_before_runtime_creation() -> None:
    calls: list[str] = []

    class TelemetryStub:
        def initialize(self, _settings) -> None:
            calls.append("initialize")

    class FakeRuntimeFactory:
        def __init__(self) -> None:
            self.settings = settings()

        def create(self) -> InProcessRuntime:
            calls.append("create")
            return InProcessRuntime(
                chat=ChatService(FakeAgent()),
                sessions=SessionService(FakeAgent()),
                catalog=CatalogService(
                    SimpleNamespace(
                        provider_registry=SimpleNamespace(supported=list),
                        model_registry=SimpleNamespace(supported=lambda _provider=None: []),
                    )
                ),
            )

    _ = InProcessKodaService(
        runtime_factory=cast("InProcessRuntimeFactory", FakeRuntimeFactory()),
        telemetry=cast("Any", TelemetryStub()),
    )

    assert calls == ["initialize", "create"]


def test_reconfigure_swaps_runtime_bundle() -> None:
    def runtime(provider_name: str) -> InProcessRuntime:
        return InProcessRuntime(
            chat=ChatService(FakeAgent()),
            sessions=SessionService(FakeAgent()),
            catalog=CatalogService(
                SimpleNamespace(
                    provider_registry=SimpleNamespace(supported=lambda: [provider_name]),
                    model_registry=SimpleNamespace(supported=lambda _provider=None: []),
                )
            ),
        )

    runtimes = [
        runtime("openai"),
        runtime("bergetai"),
    ]

    class FakeRuntimeFactory:
        def __init__(self) -> None:
            self.settings = settings()
            self.runtimes = runtimes

        def create(self) -> InProcessRuntime:
            return self.runtimes.pop(0)

    service = InProcessKodaService(
        runtime_factory=cast("InProcessRuntimeFactory", FakeRuntimeFactory()),
    )

    assert service.list_providers() == ["openai"]

    service.reconfigure()

    assert service.list_providers() == ["bergetai"]
