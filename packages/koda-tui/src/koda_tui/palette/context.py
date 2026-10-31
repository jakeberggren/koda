"""Palette context: what the palette's menus work with."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_service import KodaService
    from koda_tui.app.conversation import Conversation
    from koda_tui.settings import AppSettings
    from koda_tui.state import AppState
    from koda_tui.ui.overlays import Overlays


@dataclass(frozen=True, slots=True)
class PaletteContext:
    """Where menus open their pickers and dialogs, and the parts of Koda they act on."""

    overlays: Overlays
    service: KodaService
    settings: AppSettings
    state: AppState
    conversation: Conversation
    cancel_streaming: Callable[[], None]
    refresh_theme: Callable[[], None]
