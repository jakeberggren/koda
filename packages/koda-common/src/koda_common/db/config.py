from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from koda_common.settings import EnvSettings

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic import AnyHttpUrl


@dataclass(frozen=True, slots=True)
class DbSettings:
    url: str
    path: Path | None
    auth_token: str | None = None
    sync_url: AnyHttpUrl | None = None


def _libsql_url(path: Path) -> str:
    return f"sqlite+libsql:///{path}"


def resolve_db_settings(env: EnvSettings | None = None) -> DbSettings:
    env = env or EnvSettings()

    path = env.koda_db_path
    auth_token = env.koda_db_auth_token.get_secret_value() if env.koda_db_auth_token else None
    sync_url = env.koda_db_sync_url

    return DbSettings(
        url=_libsql_url(path),
        path=path,
        auth_token=auth_token,
        sync_url=sync_url,
    )
