from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from koda.telemetry.langfuse import LangfuseTelemetry

if TYPE_CHECKING:
    from koda_common.settings import SettingsManager


class Telemetry(Protocol):
    def initialize(self, settings: SettingsManager) -> None: ...


__all__ = ["LangfuseTelemetry", "Telemetry"]
