import asyncio
import sys
from pathlib import Path

from structlog.stdlib import BoundLogger

from koda_common.logging import LoggingConfig, configure_logging, get_logger
from koda_tui.app import KodaTuiApp
from koda_tui.bootstrap import StartupError, create_startup_context
from koda_tui.state import AppState

__all__ = ["AppState", "KodaTuiApp", "main"]


def _report_startup_error(error: StartupError, logger: BoundLogger) -> None:
    # Expected startup failures should be concise and user-fixable, not tracebacks.
    logger.error("startup_failed", summary=error.summary, details=error.details)
    print(f"Application failed to start ({type(error).__name__}): {error}", file=sys.stderr)


def main() -> None:
    config = LoggingConfig(app_name="koda-tui", console=False)
    configure_logging(config)
    logger = get_logger(__name__)

    try:
        workspace_root = Path.cwd().resolve()
        context = create_startup_context(workspace_root)
        app = KodaTuiApp(
            settings=context.settings,
            catalog_service=context.catalog_service,
            runtime_manager=context.runtime_manager,
            workspace_root=workspace_root,
        )
        asyncio.run(app.run())
    except StartupError as error:
        _report_startup_error(error, logger)
        sys.exit(1)
