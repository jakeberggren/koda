"""Main: builds the app from its parts, and runs it."""

import asyncio
import logging
import os
import sys
from functools import partial
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import NoReturn

import structlog

from koda import llm
from koda.paths import koda_home_dir
from koda.sessions import JsonSessionStore
from koda_tui import strings
from koda_tui.app import KodaTuiApp
from koda_tui.settings import Settings, SettingsError


def main() -> None:
    """Start Koda in the current directory."""
    configure_logging()
    workspace = Path.cwd().resolve()
    try:
        settings = Settings.load()
    except SettingsError as error:
        _fail(error)
    catalog, warnings = llm.Catalog.load()
    app = KodaTuiApp(
        settings,
        workspace,
        catalog=catalog,
        credentials=llm.JsonCredentialStore(),
        store=JsonSessionStore(),
        connect=partial(llm.connect, tracing=True),
        warnings=[warning.summary for warning in warnings],
    )
    asyncio.run(app.run())


def configure_logging() -> None:
    """Log JSON lines to ``~/.koda/log/koda-tui.log``, at ``KODA_LOG_LEVEL`` (INFO by
    default). Never to the terminal, which the TUI draws on."""
    path = koda_home_dir() / "log" / "koda-tui.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    shared: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.CallsiteParameterAdder(
            [
                structlog.processors.CallsiteParameter.MODULE,
                structlog.processors.CallsiteParameter.QUAL_NAME,
            ]
        ),
    ]
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    handler = RotatingFileHandler(path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )
    )
    logging.basicConfig(level=os.environ.get("KODA_LOG_LEVEL", "INFO").upper(), handlers=[handler])


def _fail(error: SettingsError) -> NoReturn:
    """Log ``error``, tell the user what to fix, and exit. Expected start-up failures
    are reported briefly, not as tracebacks."""
    structlog.get_logger(__name__).error("startup_failed", error=str(error))
    print(strings.App.failed_to_start(error), file=sys.stderr)
    sys.exit(1)
