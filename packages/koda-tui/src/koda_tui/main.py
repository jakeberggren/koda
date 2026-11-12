"""Main: builds the app from its parts, and runs it."""

import asyncio
import sys
from functools import partial
from pathlib import Path
from typing import NoReturn

from structlog import get_logger

from koda import llm
from koda.sessions import JsonSessionStore
from koda_tui import strings
from koda_tui.app import KodaTuiApp
from koda_tui.logs import LoggingConfig, configure_logging
from koda_tui.settings import (
    AppSettings,
    JsonFileSecretsStore,
    JsonFileSettingsStore,
    SecretsStore,
    SettingsError,
    SettingsManager,
    SettingsStore,
    TuiSettingsManager,
)


def load_settings(settings_store: SettingsStore, secrets_store: SecretsStore) -> AppSettings:
    """The core and TUI settings, from ``settings_store`` and ``secrets_store``."""
    return AppSettings(
        core=SettingsManager(settings_store=settings_store, secrets_store=secrets_store),
        tui=TuiSettingsManager(settings_store=settings_store),
    )


def main() -> None:
    """Start Koda in the current directory."""
    configure_logging(LoggingConfig(app_name="koda-tui", console=False))
    workspace = Path.cwd().resolve()
    try:
        settings = load_settings(JsonFileSettingsStore(), JsonFileSecretsStore())
    except SettingsError as error:
        _fail(error)
    catalog, warnings = llm.Catalog.load()
    app = KodaTuiApp(
        settings,
        workspace,
        catalog=catalog,
        store=JsonSessionStore(),
        connect=partial(llm.connect, tracing=True),
        warnings=[warning.summary for warning in warnings],
    )
    asyncio.run(app.run())


def _fail(error: SettingsError) -> NoReturn:
    """Log ``error``, tell the user what to fix, and exit. Expected start-up failures
    are reported briefly, not as tracebacks."""
    get_logger(__name__).error("startup_failed", summary=error.summary, details=error.details)
    print(strings.App.failed_to_start(error), file=sys.stderr)
    sys.exit(1)
