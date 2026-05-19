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
from koda_tui.state import AppState

__all__ = ["AppState", "KodaTuiApp", "main"]


def _report_startup_error(error: StartupError, logger: BoundLogger) -> None:
    # Expected startup failures should be concise and user-fixable, not tracebacks.
    logger.error("startup_failed", summary=error.summary, details=error.details)
    print(f"Application failed to start ({type(error).__name__}): {error}", file=sys.stderr)


def build_app(
    workspace_root: Path,
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
        workspace_root=workspace_root,
    )


def main() -> None:
    config = LoggingConfig(app_name="koda-tui", console=False)
    configure_logging(config)
    logger = get_logger(__name__)

    try:
        workspace_root = Path.cwd().resolve()
        app = build_app(
            workspace_root=workspace_root,
            settings_store=JsonFileSettingsStore(),
            secrets_store=JsonFileSecretsStore(),
            telemetry=LangfuseTelemetry(),
            runtime_config=LocalRuntimeConfig(
                cwd=workspace_root,
                sandbox_dir=workspace_root,
            ),
        )
        asyncio.run(app.run())
    except SecretsLoadError as error:
        _report_startup_error(StartupError.from_secrets_load_error(error), logger)
        sys.exit(1)
    except SettingsLoadError as error:
        _report_startup_error(StartupError.from_settings_load_error(error), logger)
        sys.exit(1)
    except StartupError as error:
        _report_startup_error(error, logger)
        sys.exit(1)
