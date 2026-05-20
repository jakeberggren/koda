from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from koda_service.exceptions import StartupError


@dataclass(frozen=True, slots=True, kw_only=True)
class ChatRequest:
    """Input for starting an agent chat turn."""

    message: str
    session_id: UUID | None = None


class ServiceStatusCode(StrEnum):
    """Machine-readable readiness states for service clients."""

    READY = auto()
    PROVIDER_SETUP_REQUIRED = auto()
    MODEL_SELECTION_REQUIRED = auto()
    PROVIDER_NOT_CONNECTED = auto()
    MODEL_UNAVAILABLE = auto()
    API_KEY_NOT_CONFIGURED = auto()
    API_KEY_EMPTY = auto()
    STARTUP_ERROR = auto()


@dataclass(frozen=True, slots=True, kw_only=True)
class ServiceStatus:
    """Readiness status suitable for both display and branching."""

    code: ServiceStatusCode
    summary: str
    detail: str | None = None

    @property
    def is_ready(self) -> bool:
        """Return whether the service can currently run chat."""
        return self.code is ServiceStatusCode.READY

    @classmethod
    def from_startup_error(cls, error: StartupError) -> ServiceStatus:
        """Convert a startup error into a service status."""
        detail = "\n".join(error.details) if error.details else None
        return cls(
            code=ServiceStatusCode.STARTUP_ERROR,
            summary=error.summary,
            detail=detail,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ServiceDiagnostics:
    """Non-blocking service diagnostics for clients to display or log."""

    startup_warnings: list[str]
