from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING

import structlog

from koda_common.logging.settings import LoggingEnvSettings
from koda_common.logging.types import LogLevel
from koda_common.paths import log_file_path

if TYPE_CHECKING:
    from pathlib import Path


class NoHandlersConfiguredError(ValueError):
    """Raised when logging is configured with no handlers (no console and no log file)."""

    def __init__(self) -> None:
        super().__init__(
            "No log handlers configured. Either set console=True in LoggingConfig, "
            "provide a log_file path, or set the KODA_LOG_FILE environment variable."
        )


@dataclass(frozen=True)
class LoggingConfig:
    """Configuration options for structured logging setup."""

    app_name: str
    level: LogLevel | None = LogLevel.INFO
    log_file: Path | None = None
    console: bool = True
    enabled: bool = True
    max_log_bytes: int = 5 * 1024 * 1024
    backup_count: int = 3


def _build_shared_processors() -> list[structlog.typing.Processor]:
    return [
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
    config: LoggingConfig,
    log_file: Path | None,
    *,
    console: bool = True,
) -> list[logging.Handler]:
    handlers: list[logging.Handler] = []
    console_formatter = _build_formatter(
        shared_processors,
        structlog.dev.ConsoleRenderer(colors=True),
    )
    file_formatter = _build_formatter(shared_processors, structlog.processors.JSONRenderer())

    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        handlers.append(console_handler)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=config.max_log_bytes,
            backupCount=config.backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)
    if not handlers:
        raise NoHandlersConfiguredError
    return handlers


def configure_logging(
    config: LoggingConfig,
    *,
    env: LoggingEnvSettings | None = None,
) -> None:
    """Initialize structured logging with console and optional file output."""
    env = env or LoggingEnvSettings()

    if not (config.enabled and env.koda_log_enabled):
        return

    root = logging.getLogger()

    if root.handlers:
        return

    resolved_level = config.level or env.koda_log_level
    resolved_file = config.log_file or env.koda_log_file or log_file_path(config.app_name)

    shared_processors = _build_shared_processors()

    structlog.configure_once(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    handlers = _build_handlers(shared_processors, config, resolved_file, console=config.console)

    logging.basicConfig(
        level=resolved_level,
        handlers=handlers,
    )

    structlog.contextvars.bind_contextvars(app=config.app_name)


def get_logger(
    name: str | None = None,
) -> structlog.stdlib.BoundLogger:
    """Return a bound logger for the given name, typically __name__."""
    return structlog.get_logger(name)
