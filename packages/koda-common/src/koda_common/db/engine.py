from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlmodel import create_engine

from koda_common.db.config import DbSettings, resolve_db_settings
from koda_common.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

    from koda_common.settings import EnvSettings

log = get_logger(__name__)

_engine: Engine | None = None


def _prepare_sqlite_path(settings: DbSettings) -> None:
    if settings.path is None:
        return
    settings.path.parent.mkdir(parents=True, exist_ok=True)


def get_engine(*, echo: bool = False, env: EnvSettings | None = None) -> Engine:
    global _engine  # noqa: PLW0603

    if _engine is not None:
        return _engine

    settings = resolve_db_settings(env)

    connect_args: dict[str, Any] = {"check_same_thread": False}
    _prepare_sqlite_path(settings)

    if settings.auth_token:
        connect_args["auth_token"] = settings.auth_token
    if settings.sync_url:
        connect_args["sync_url"] = str(settings.sync_url)

    log.info("db_engine_created")
    _engine = create_engine(settings.url, echo=echo, connect_args=connect_args)
    return _engine


def clear_engine_cache() -> None:
    """Clear the cached engine. Useful for testing."""
    global _engine  # noqa: PLW0603
    _engine = None
