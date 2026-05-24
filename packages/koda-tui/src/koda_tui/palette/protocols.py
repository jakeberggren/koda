"""Protocols used by the palette feature."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from koda_service import KodaService
    from koda_tui.layout import TUILayout
    from koda_tui.settings import AppSettings
    from koda_tui.state import AppState


class PaletteApp(Protocol):
    """Outer application surface needed by the palette feature."""

    @property
    def service(self) -> KodaService: ...

    @property
    def app_settings(self) -> AppSettings: ...

    @property
    def state(self) -> AppState: ...

    @property
    def layout(self) -> TUILayout: ...

    def cancel_streaming(self) -> None: ...

    def invalidate(self) -> None: ...
