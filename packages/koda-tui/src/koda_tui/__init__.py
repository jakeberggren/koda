import asyncio
import sys

from koda_common.logging import LoggingConfig, configure_logging, get_logger
from koda_tui.app import KodaTuiApp

__all__ = ["KodaTuiApp", "main"]


def main() -> None:
    config = LoggingConfig(app_name="koda-tui", console=False)
    configure_logging(config)
    logger = get_logger(__name__)

    try:
        app = KodaTuiApp()
        asyncio.run(app.run())
    except Exception:
        logger.exception("unhandled_exception")
        sys.exit(1)
