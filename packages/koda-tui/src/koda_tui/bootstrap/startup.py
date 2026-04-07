from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from koda_common.settings import JsonFileSettingsStore
from koda_service.services.in_process.factories import create_catalog_service
from koda_tui.bootstrap.manager import KodaRuntimeManager
from koda_tui.bootstrap.settings import create_settings_manager

if TYPE_CHECKING:
    from pathlib import Path

    from koda_common.settings import SettingsManager
    from koda_service.protocols import CatalogService
    from koda_service.types import ModelDefinition, ProviderDefinition


@dataclass(frozen=True, slots=True)
class StartupContext:
    settings: SettingsManager
    catalog_service: CatalogService[ProviderDefinition, ModelDefinition]
    runtime_manager: KodaRuntimeManager


def create_startup_context(cwd: Path) -> StartupContext:
    settings_store = JsonFileSettingsStore()
    settings = create_settings_manager(settings_store)
    catalog_service = create_catalog_service(settings)
    runtime_manager = KodaRuntimeManager(settings=settings, cwd=cwd)
    return StartupContext(
        settings=settings,
        catalog_service=catalog_service,
        runtime_manager=runtime_manager,
    )
