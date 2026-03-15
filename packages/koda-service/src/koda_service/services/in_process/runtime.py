from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from koda_service.services.in_process.catalog import CatalogService
from koda_service.services.in_process.chat import ChatService
from koda_service.services.in_process.sessions import SessionService

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from koda.agents import Agent
    from koda.sessions import SessionManager
    from koda_common.settings import SettingsManager
    from koda_service.bootstrap import Registries


@dataclass(frozen=True, slots=True)
class InProcessRuntime:
    chat: ChatService
    sessions: SessionService
    catalog: CatalogService


@dataclass(slots=True)
class InProcessRuntimeFactory:
    settings: SettingsManager
    sandbox_dir: Path
    session_manager: SessionManager
    registries: Registries
    create_agent: Callable[..., Agent]

    def create(self) -> InProcessRuntime:
        agent = self.create_agent(
            settings=self.settings,
            sandbox_dir=self.sandbox_dir,
            session_manager=self.session_manager,
            registries=self.registries,
        )
        return InProcessRuntime(
            chat=ChatService(agent),
            sessions=SessionService(agent),
            catalog=CatalogService(self.registries),
        )
