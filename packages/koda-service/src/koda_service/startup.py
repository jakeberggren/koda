from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import ValidationError

from koda.llm.exceptions import (
    LLMAuthenticationError,
    LLMConfigurationError,
)
from koda.telemetry import LangfuseTelemetry
from koda_common.settings import (
    JsonFileSettingsStore,
    KeyChainSecretsStore,
    KeyringNotInstalledError,
    SettingsManager,
)
from koda_service.bootstrap import create_in_process_runtime_factory, create_registries
from koda_service.exceptions import (
    StartupConfigurationError,
    StartupEnvironmentError,
)
from koda_service.services.in_process import InProcessKodaService

if TYPE_CHECKING:
    from pathlib import Path

    from koda_service.protocols import KodaService
    from koda_service.types import Message, ModelDefinition, ProviderDefinition, StreamEvent


@dataclass(frozen=True, slots=True)
class StartupContext:
    settings: SettingsManager
    service: KodaService[StreamEvent, ProviderDefinition, ModelDefinition, Message]


def _create_settings(settings_store: JsonFileSettingsStore) -> SettingsManager:
    try:
        return SettingsManager(
            settings_store=settings_store,
            secrets_store=KeyChainSecretsStore(),
        )
    except json.JSONDecodeError as error:
        raise StartupConfigurationError.from_json_decode_error(
            path=str(settings_store.path),
            error=error,
        ) from error
    except ValidationError as error:
        raise StartupConfigurationError.from_validation_error(error) from error
    except KeyringNotInstalledError as error:
        raise StartupEnvironmentError.from_keyring_error(error) from error
    except PermissionError as error:
        raise StartupEnvironmentError.from_permission_error(error) from error


def _create_service(
    settings: SettingsManager,
    cwd: Path,
) -> KodaService[StreamEvent, ProviderDefinition, ModelDefinition, Message]:
    try:
        registries = create_registries()
        runtime_factory = create_in_process_runtime_factory(
            settings=settings,
            sandbox_dir=cwd,
            registries=registries,
        )
        telemetry = LangfuseTelemetry()
        return InProcessKodaService(
            runtime_factory=runtime_factory,
            telemetry=telemetry,
        )
    except (LLMConfigurationError, LLMAuthenticationError) as error:
        raise StartupConfigurationError.from_runtime_error(error) from error
    except PermissionError as error:
        raise StartupEnvironmentError.from_permission_error(error) from error


def create_startup_context(cwd: Path) -> StartupContext:
    settings_store = JsonFileSettingsStore()
    settings = _create_settings(settings_store)
    service = _create_service(settings, cwd)
    return StartupContext(settings=settings, service=service)
