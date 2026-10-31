"""Main: builds the app from its parts, and runs it."""

import asyncio
import sys
from pathlib import Path

from structlog.stdlib import BoundLogger

from koda.telemetry import LangfuseTelemetry, Telemetry
from koda_common.logging import LoggingConfig, configure_logging, get_logger
from koda_common.settings import (
    JsonFileSecretsStore,
    JsonFileSettingsStore,
    SecretsLoadError,
    SecretsStore,
    SettingsLoadError,
    SettingsManager,
    SettingsStore,
)
from koda_service import LocalRuntimeConfig
from koda_service.exceptions import StartupError
from koda_service.services.local import LocalKodaService
from koda_tui.app import KodaTuiApp
from koda_tui.settings import AppSettings, TuiSettingsManager


def _startup_error(error: SecretsLoadError | SettingsLoadError | StartupError) -> StartupError:
    """``error`` as a start-up error, which says what to fix."""
    match error:
        case SecretsLoadError():
            return StartupError.from_secrets_load_error(error)
        case SettingsLoadError():
            return StartupError.from_settings_load_error(error)
        case StartupError():
            return error


def _report_startup_error(error: StartupError, logger: BoundLogger) -> None:
    # Expected startup failures should be concise and user-fixable, not tracebacks.
    logger.error("startup_failed", summary=error.summary, details=error.details)
    print(f"Application failed to start ({type(error).__name__}): {error}", file=sys.stderr)


def build_app(
    workspace: Path,
    settings_store: SettingsStore,
    secrets_store: SecretsStore,
    telemetry: Telemetry,
    runtime_config: LocalRuntimeConfig,
) -> KodaTuiApp:
    core_settings = SettingsManager(settings_store=settings_store, secrets_store=secrets_store)
    tui_settings = TuiSettingsManager(settings_store=settings_store)
    app_settings = AppSettings(core=core_settings, tui=tui_settings)
    service = LocalKodaService(
        settings=core_settings,
        runtime=runtime_config,
        telemetry=telemetry,
    )
    return KodaTuiApp(
        app_settings=app_settings,
        service=service,
        workspace=workspace,
    )


def main() -> None:
    config = LoggingConfig(app_name="koda-tui", console=False)
    configure_logging(config)
    logger = get_logger(__name__)

    try:
        workspace = Path.cwd().resolve()
        app = build_app(
            workspace=workspace,
            settings_store=JsonFileSettingsStore(),
            secrets_store=JsonFileSecretsStore(),
            telemetry=LangfuseTelemetry(),
            runtime_config=LocalRuntimeConfig(cwd=workspace, sandbox_dir=workspace),
        )
        asyncio.run(app.run())
    except (SecretsLoadError, SettingsLoadError, StartupError) as error:
        _report_startup_error(_startup_error(error), logger)
        sys.exit(1)
