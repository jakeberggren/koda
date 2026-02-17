import asyncio
import sys
from pathlib import Path

from koda_api.backends import create_backend
from koda_common.logging import LoggingConfig, configure_logging, get_logger
from koda_common.settings import JsonFileSettingsStore, KeyChainSecretsStore
from koda_common.settings.manager import SettingsManager
from koda_tui.app import KodaTuiApp
from koda_tui.state import AppState

__all__ = ["AppState", "KodaTuiApp", "main"]


def main() -> None:
    config = LoggingConfig(app_name="koda-tui", console=False)
    configure_logging(config)
    logger = get_logger(__name__)

    try:
        settings = SettingsManager(
            settings_store=JsonFileSettingsStore(),
            secrets_store=KeyChainSecretsStore(),
        )
        backend = create_backend(settings, Path.cwd().resolve())
        app = KodaTuiApp(settings=settings, backend=backend)
        asyncio.run(app.run())
    except Exception:
        logger.exception("unhandled_exception")
        sys.exit(1)
