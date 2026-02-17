from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from koda_api.backends import UnsupportedKodaBackendError, create_backend

if TYPE_CHECKING:
    from koda_common.settings import SettingsManager


def test_create_backend_uses_in_process_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = object()
    settings = cast("SettingsManager", SimpleNamespace(koda_backend="in_process"))

    monkeypatch.setattr(
        "koda_api.backends.create_in_process_backend",
        lambda _settings, _sandbox_dir: sentinel,
    )

    backend = create_backend(settings, Path.cwd())

    assert backend is sentinel


def test_create_backend_raises_for_unsupported_backend() -> None:
    settings = cast("SettingsManager", SimpleNamespace(koda_backend="http"))

    with pytest.raises(UnsupportedKodaBackendError):
        create_backend(settings, Path.cwd())
