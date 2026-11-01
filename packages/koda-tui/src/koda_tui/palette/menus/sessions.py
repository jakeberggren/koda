"""Session palette items and actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.keys import Keys

from koda_common.logging import get_logger
from koda_service.exceptions import ServiceSessionNotFoundError
from koda_tui.ui.widgets import ChoiceDialog, DialogChoice, ListItem, Picker, Shortcut

if TYPE_CHECKING:
    from koda.sessions import Session
    from koda_tui.palette.context import PaletteContext


log = get_logger(__name__)

_TITLE = "List Sessions"
_LIST_HEADING = "Select New Session"


class SessionMenu:
    """Session submenu behavior."""

    def __init__(self, context: PaletteContext) -> None:
        self._overlays = context.overlays
        self._outbox = context.outbox
        self._service = context.service
        self._conversation = context.conversation

    def items(self) -> list[ListItem[Session]]:
        """Build session selection items."""
        active = self._service.active_session()
        active_id = active.session_id if active is not None else None
        return [
            ListItem(
                label=_format_session_label(session),
                data=session,
                current=session.session_id == active_id,
            )
            for session in self._service.list_sessions()
        ]

    def open(self) -> None:
        """Open the session selection submenu."""
        self._overlays.open(
            Picker(
                _TITLE,
                self.items(),
                on_select=lambda item: self.switch(item.data),
                heading=_LIST_HEADING,
                shortcuts=[Shortcut(Keys.ControlD, "ctrl+d", "delete", self.confirm_delete)],
                on_close=self._overlays.close,
            ),
        )

    def new(self) -> None:
        """Create and switch to a new session."""
        self._outbox.stop()
        self._service.create_session()
        self._conversation.clear()
        self._overlays.close_all()

    def switch(self, session: Session) -> None:
        """Switch to an existing session."""
        self._outbox.stop()
        try:
            switched = self._service.switch_session(session.session_id)
        except ServiceSessionNotFoundError:
            log.warning("switch_session_failed", session_id=str(session.session_id))
            return
        self._conversation.load(switched)
        self._overlays.close_all()

    def confirm_delete(self, item: ListItem[Session] | None) -> None:
        """Open the delete confirmation dialog for a session item."""
        if item is None:
            return
        session = item.data
        self._overlays.open(
            ChoiceDialog(
                "Delete session?",
                [
                    DialogChoice("Yes", lambda: self.delete(session), key="y"),
                    DialogChoice("No", self._overlays.close, key="n"),
                ],
                on_cancel=self._overlays.close,
            ),
        )

    def delete(self, session: Session) -> None:
        """Delete a session."""
        active = self._service.active_session()
        removed_active = active is not None and active.session_id == session.session_id
        if removed_active:
            self._outbox.stop()

        try:
            self._service.delete_session(session.session_id)
        except ServiceSessionNotFoundError:
            log.warning("delete_session_failed", session_id=str(session.session_id))
            return

        if removed_active:
            self._conversation.clear()
        self._overlays.close_all()


def _format_session_label(session: Session) -> str:
    timestamp = session.created_at.strftime("%Y-%m-%d")
    return f"{session.display_name}  [{timestamp}] ({session.message_count} messages)"
