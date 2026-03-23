from __future__ import annotations

from typing import TYPE_CHECKING

from koda_service.protocols import KodaService
from koda_service.types import Message, ModelDefinition, ProviderDefinition, StreamEvent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence
    from uuid import UUID

    from koda.telemetry import Telemetry
    from koda_service.services.in_process.runtime import InProcessRuntimeFactory
    from koda_service.types import SessionInfo


class InProcessKodaService(KodaService[StreamEvent, ProviderDefinition, ModelDefinition, Message]):
    """In-process implementation of the Koda service boundary."""

    def __init__(
        self,
        runtime_factory: InProcessRuntimeFactory,
        telemetry: Telemetry | None = None,
    ) -> None:
        self._runtime_factory = runtime_factory
        if telemetry:
            telemetry.initialize(self._runtime_factory.settings)
        self._runtime = self._runtime_factory.create()

    def reconfigure(self) -> None:
        self._runtime = self._runtime_factory.create()

    async def chat(self, message: str) -> AsyncIterator[StreamEvent]:
        async for event in self._runtime.chat.chat(message):
            yield event

    def list_providers(self) -> list[ProviderDefinition]:
        return self._runtime.catalog.list_providers()

    def list_models(self, provider: str | None = None) -> list[ModelDefinition]:
        return self._runtime.catalog.list_models(provider)

    def active_session(self) -> SessionInfo:
        return self._runtime.sessions.active_session()

    def list_sessions(self) -> list[SessionInfo]:
        return self._runtime.sessions.list_sessions()

    def new_session(self) -> SessionInfo:
        return self._runtime.sessions.new_session()

    def switch_session(self, session_id: UUID) -> tuple[SessionInfo, Sequence[Message]]:
        return self._runtime.sessions.switch_session(session_id)

    def delete_session(self, session_id: UUID) -> SessionInfo | None:
        return self._runtime.sessions.delete_session(session_id)
