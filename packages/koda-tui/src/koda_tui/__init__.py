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
from koda_service import AgentBuilder
from koda_service.exceptions import StartupError, startup_error_from_settings_error
from koda_service.services.in_process import InProcessKodaService
from koda_tui.agent import KodaTuiAgent
from koda_tui.app import KodaTuiApp
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
    agent_builder: AgentBuilder,
) -> KodaTuiApp:
    settings = SettingsManager(
        settings_store=settings_store,
        secrets_store=secrets_store,
    )
    service = InProcessKodaService(
        settings=settings,
        sandbox_dir=workspace_root,
        telemetry=telemetry,
        agent_builder=agent_builder,
    )
    return KodaTuiApp(
        settings=settings,
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
            agent_builder=KodaTuiAgent(cwd=workspace_root, sandbox_dir=workspace_root),
        )
        asyncio.run(app.run())
    except (SecretsLoadError, SettingsLoadError) as error:
        _report_startup_error(startup_error_from_settings_error(error), logger)
        sys.exit(1)
    except StartupError as error:
        _report_startup_error(error, logger)
        sys.exit(1)
