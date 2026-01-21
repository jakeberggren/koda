from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING

import structlog

from koda_common.settings import EnvSettings

if TYPE_CHECKING:
    from pathlib import Path

    from koda_common.settings.settings import LogFormat, LogLevel

_MAX_LOG_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 3

_default_app_name: str | None = None


def _build_shared_processors() -> list[structlog.typing.Processor]:
    return [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.CallsiteParameterAdder(
            [
                structlog.processors.CallsiteParameter.MODULE,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ),
    ]


def _build_renderer(log_format: LogFormat) -> structlog.typing.Processor:
    if log_format == "text":
        return structlog.dev.ConsoleRenderer()
    return structlog.processors.JSONRenderer()


def _build_handlers(formatter: logging.Formatter, log_file: Path | None) -> list[logging.Handler]:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    for handler in handlers:
        handler.setFormatter(formatter)

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

    return handlers


def _close_handlers(root: logging.Logger) -> None:
    for handler in root.handlers:
        handler.close()
    root.handlers.clear()


def configure_logging(
    *,
    app_name: str | None = None,
    level: LogLevel | None = None,
    log_format: LogFormat | None = None,
    log_file: Path | None = None,
    force: bool = False,
) -> None:
    """Initialize structured logging with console and optional file output."""
    global _default_app_name  # noqa: PLW0603
    root = logging.getLogger()
    if root.handlers and not force:
        return

    env = EnvSettings()
    resolved_level = level or env.koda_log_level
    resolved_format = log_format or env.koda_log_format
    resolved_file = log_file or env.koda_log_file

    _default_app_name = app_name
    shared_processors = _build_shared_processors()
    renderer = _build_renderer(resolved_format)

    structlog.configure_once(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )

    if force:
        _close_handlers(root)

    logging.basicConfig(
        level=resolved_level,
        handlers=_build_handlers(formatter, resolved_file),
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
