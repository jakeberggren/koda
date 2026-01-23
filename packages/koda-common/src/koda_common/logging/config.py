from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from pathlib import Path

    from koda_common.settings.settings import LogLevel


class NoHandlersConfiguredError(ValueError):
    """Raised when logging is configured with no handlers (no console and no log file)."""

    def __init__(self) -> None:
        super().__init__(
            "No log handlers configured. Either set console=True in LoggingConfig, "
            "provide a log_file path, or set the KODA_LOG_FILE environment variable."
        )


@dataclass
class LoggingConfig:
    """Configuration options for structured logging setup."""

    app_name: str | None = None
    level: LogLevel | None = None
    log_file: Path | None = None
    console: bool = True
    enabled: bool = True


_MAX_LOG_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 3

_default_app_name: str | None = None


def _build_shared_processors() -> list[structlog.typing.Processor]:
    return [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.CallsiteParameterAdder(
            [structlog.processors.CallsiteParameter.MODULE]
        ),
    ]


def _build_formatter(
    shared_processors: list[structlog.typing.Processor],
    renderer: structlog.typing.Processor,
) -> structlog.stdlib.ProcessorFormatter:
    return structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )


def _build_handlers(
    shared_processors: list[structlog.typing.Processor],
    log_file: Path | None,
    *,
    console: bool = True,
) -> list[logging.Handler]:
    handlers: list[logging.Handler] = []
    formatter = _build_formatter(shared_processors, structlog.dev.ConsoleRenderer(colors=True))

    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=_MAX_LOG_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    if not handlers:
        raise NoHandlersConfiguredError
    return handlers


def _close_handlers(root: logging.Logger) -> None:
    for handler in root.handlers:
        handler.close()
    root.handlers.clear()


def configure_logging(config: LoggingConfig | None = None, *, force: bool = False) -> None:
    """Initialize structured logging with console and optional file output."""
    from koda_common.settings.settings import EnvSettings  # noqa: PLC0415

    global _default_app_name  # noqa: PLW0603

    config = config or LoggingConfig()
    env = EnvSettings()

    if not (config.enabled and env.koda_log_enabled):
        return

    root = logging.getLogger()
    if root.handlers and not force:
        return
    resolved_level = config.level or env.koda_log_level
    resolved_file = config.log_file or env.koda_log_file

    _default_app_name = config.app_name
    shared_processors = _build_shared_processors()

    structlog.configure_once(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    if force:
        _close_handlers(root)

    logging.basicConfig(
        level=resolved_level,
        handlers=_build_handlers(shared_processors, resolved_file, console=config.console),
        force=force,
    )


def get_logger(
    name: str | None = None, *, app_name: str | None = None
) -> structlog.stdlib.BoundLogger:
    """Return a bound logger for the given name, typically __name__."""
    logger = structlog.get_logger(name)
    resolved_app_name = app_name or _default_app_name
    if resolved_app_name:
        return logger.bind(app=resolved_app_name)
    return logger
