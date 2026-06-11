"""Concrete palette feature implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_tui.overlays.dialogs import (
    ChoiceDialog,
    ConfirmDialog,
    DialogChoice,
    MessageDialog,
    TextInputDialog,
)
from koda_tui.overlays.manager import OverlayManager
from koda_tui.palette.controller import PaletteController
from koda_tui.palette.overlay import PaletteOverlay

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit import Application
    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.layout import FloatContainer

    from koda_service import KodaService
    from koda_tui.palette.items import ListItem
    from koda_tui.palette.protocols import PaletteApp
    from koda_tui.settings import AppSettings
    from koda_tui.state import AppState


class Palette:
    """Owns palette overlays, submenus, and palette-specific actions."""

    def __init__(self, app: PaletteApp) -> None:
        self._app = app
        self._controller = PaletteController(self)
        self._overlay_manager: OverlayManager | None = None

    @property
    def service(self) -> KodaService:
        """Return the service used by palette actions."""
        return self._app.service

    @property
    def app_settings(self) -> AppSettings:
        """Return mutable application settings used by palette actions."""
        return self._app.app_settings

    @property
    def state(self) -> AppState:
        """Return shared UI state updated by palette actions."""
        return self._app.state

    def attach(self, pt_app: Application[None], root_container: FloatContainer) -> None:
        """Attach prompt_toolkit runtime objects after app creation."""
        self._overlay_manager = OverlayManager(
            root_container,
            pt_app,
            fallback_focus_target=self._app.layout.input_area.buffer,
        )

    def toggle(self) -> None:
        """Toggle root palette visibility."""
        if self.state.palette_open:
            self.close_all_overlays()
            return

        items = self._controller.root_items()
        self.open_palette(items)

    def open_palette(
        self,
        items: list[ListItem],
        *,
        title: str = "Commands",
        list_heading: str | None = None,
        footer: StyleAndTextTuples | None = None,
        shortcuts: dict[str, Callable[[ListItem | None], None]] | None = None,
    ) -> None:
        """Open a searchable palette overlay with ``items``."""
        if self._overlay_manager is None:
            return

        def on_select(item: ListItem) -> None:
            self._controller.execute(item)

        palette = PaletteOverlay(
            items=items,
            on_select=on_select,
            on_close=self.close_top_overlay,
            invalidate=self.invalidate,
            title=title,
            footer=footer,
            list_heading=list_heading,
            shortcuts=shortcuts,
        )
        self._overlay_manager.push(palette, width=palette.preferred_width)
        self.state.palette_open = True
        self.invalidate()

    def open_text_dialog(
        self,
        title: str,
        on_submit: Callable[[str], None],
        *,
        detail: str | None = None,
        mask_input: bool = False,
    ) -> None:
        """Open a palette-owned text input dialog."""
        if self._overlay_manager is None:
            return

        dialog = TextInputDialog(
            title=title,
            on_submit=on_submit,
            on_cancel=self.close_top_overlay,
            detail=detail,
            mask_input=mask_input,
        )
        self._overlay_manager.push(dialog, width=dialog.preferred_width)
        self.state.palette_open = True
        self.invalidate()

    def open_confirm(
        self,
        message: str,
        on_confirm: Callable[[], None],
    ) -> None:
        """Open a palette-owned confirmation dialog."""
        if self._overlay_manager is None:
            return

        dialog = ConfirmDialog(
            message=message,
            on_confirm=on_confirm,
            on_cancel=self.close_top_overlay,
        )
        self._overlay_manager.push(dialog, width=dialog.preferred_width)
        self.state.palette_open = True
        self.invalidate()

    def open_choice(
        self,
        message: str,
        choices: list[DialogChoice],
    ) -> None:
        """Open a palette-owned choice dialog."""
        if self._overlay_manager is None:
            return

        dialog = ChoiceDialog(
            message=message,
            choices=choices,
            on_cancel=self.close_top_overlay,
        )
        self._overlay_manager.push(dialog, width=dialog.preferred_width)
        self.state.palette_open = True
        self.invalidate()

    def open_message(self, title: str, detail: str) -> None:
        """Open a palette-owned non-input message dialog."""
        if self._overlay_manager is None:
            return

        dialog = MessageDialog(
            title=title,
            detail=detail,
            on_close=self.close_top_overlay,
        )
        self._overlay_manager.push(dialog, width=dialog.preferred_width)
        self.state.palette_open = True
        self.invalidate()

    def close_top_overlay(self) -> None:
        """Close the top palette overlay or dialog."""
        if self._overlay_manager is not None:
            self._overlay_manager.pop()
            self.state.palette_open = self._overlay_manager.is_open
            self.invalidate()

    def close_all_overlays(self) -> None:
        """Close every palette-owned overlay or dialog."""
        if self._overlay_manager is not None:
            self._overlay_manager.clear()
        self.state.palette_open = False
        self.invalidate()

    def cancel_streaming(self) -> None:
        """Cancel the active response stream."""
        self._app.cancel_streaming()

    def invalidate(self) -> None:
        """Request a UI redraw."""
        self._app.invalidate()
