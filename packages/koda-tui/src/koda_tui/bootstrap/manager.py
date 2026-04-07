from __future__ import annotations

from typing import TYPE_CHECKING

from koda.agents import AgentConfigError, PromptRenderError
from koda.llm.exceptions import LLMAuthenticationError, LLMConfigurationError
from koda.llm.types import LLMRequestOptionsError
from koda_service.services.in_process.factories import (
    create_registries,
    create_runtime,
    create_session_manager,
)
from koda_service.services.in_process.status import check_in_process_service_status
from koda_tui.bootstrap.errors import StartupConfigurationError, StartupEnvironmentError

if TYPE_CHECKING:
    from pathlib import Path

    from koda.telemetry import Telemetry
    from koda_common.settings import SettingsManager
    from koda_service import ServiceStatus
    from koda_service.protocols import KodaRuntime
    from koda_service.types import Message, StreamEvent


class KodaRuntimeManager:
    def __init__(
        self,
        *,
        settings: SettingsManager,
        cwd: Path,
        telemetry: Telemetry | None = None,
    ) -> None:
        self._settings = settings
        self._cwd = cwd
        self._telemetry = telemetry
        self._runtime: KodaRuntime[StreamEvent, Message] | None = None

    def invalidate(self) -> None:
        self._runtime = None

    def ready(self) -> ServiceStatus:
        return check_in_process_service_status(self._settings)

    def get_runtime(self) -> KodaRuntime[StreamEvent, Message]:
        if self._runtime is None:
            try:
                self._runtime = create_runtime(
                    settings=self._settings,
                    sandbox_dir=self._cwd,
                    session_manager=create_session_manager(),
                    registries=create_registries(),
                )
            except (
                AgentConfigError,
                PromptRenderError,
                LLMConfigurationError,
                LLMAuthenticationError,
                LLMRequestOptionsError,
            ) as error:
                raise StartupConfigurationError.from_runtime_error(error) from error
            except PermissionError as error:
                raise StartupEnvironmentError.from_permission_error(error) from error
        return self._runtime
