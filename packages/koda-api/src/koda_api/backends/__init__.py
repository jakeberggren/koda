from collections.abc import Callable
from pathlib import Path

from koda_api.backends.in_process import InProcessBackend
from koda_common.contracts import KodaBackend, Message, ModelDefinition, StreamEvent
from koda_common.settings import SettingsManager

type Backend = KodaBackend[StreamEvent, ModelDefinition, Message]
type BackendFactory = Callable[[SettingsManager, Path], Backend]


class UnsupportedKodaBackendError(ValueError):
    def __init__(self, koda_backend: str) -> None:
        super().__init__(f"Unsupported backend {koda_backend}")


def create_in_process_backend(settings: SettingsManager, sandbox_dir: Path) -> Backend:
    """Create a new in-process backend instance."""
    return InProcessBackend(settings=settings, sandbox_dir=sandbox_dir)


def create_backend(settings: SettingsManager, sandbox_dir: Path) -> Backend:
    backend_factories: dict[str, BackendFactory] = {
        "in_process": create_in_process_backend,
    }
    koda_backend = settings.koda_backend
    try:
        factory = backend_factories[koda_backend]
    except KeyError as e:  # pragma: no cover - defensive guard
        raise UnsupportedKodaBackendError(koda_backend) from e
    return factory(settings, sandbox_dir)


__all__ = [
    "InProcessBackend",
    "KodaBackend",
    "UnsupportedKodaBackendError",
    "create_backend",
    "create_in_process_backend",
]
