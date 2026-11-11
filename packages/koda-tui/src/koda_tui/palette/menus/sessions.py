"""Session palette items and actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.keys import Keys

from koda.sessions import SessionNotFoundError
from koda_common.logging import get_logger
from koda_tui import strings
from koda_tui.ui.widgets import ChoiceDialog, DialogChoice, ListItem, Picker, Shortcut

if TYPE_CHECKING:
    from koda.sessions import Session
    from koda_tui.palette.context import PaletteContext


log = get_logger(__name__)


class SessionMenu:
    """Session submenu behavior."""

    def __init__(self, context: PaletteContext) -> None:
        self._overlays = context.overlays
        self._outbox = context.outbox
        self._runtime = context.runtime
        self._conversation = context.conversation

    def items(self) -> list[ListItem[Session]]:
        """Build session selection items."""
        active_id = self._runtime.session.session_id
        return [
            ListItem(
                label=_format_session_label(session),
                data=session,
                current=session.session_id == active_id,
            )
            for session in self._runtime.store.list_sessions()
        ]

    def open(self) -> None:
        """Open the session selection submenu."""
        self._overlays.open(
            Picker(
                strings.Palette.Sessions.TITLE,
                self.items(),
                on_select=lambda item: self.switch(item.data),
                heading=strings.Palette.Sessions.HEADING,
                shortcuts=[
                    Shortcut(
                        Keys.ControlN,
                        strings.Key.CTRL_N,
                        strings.Palette.Sessions.NEW_HINT,
                        lambda _item: self.new(),
                    ),
                    Shortcut(
                        Keys.ControlD,
                        strings.Key.CTRL_D,
                        strings.Palette.Sessions.DELETE_HINT,
                        self.confirm_delete,
                    ),
                ],
                on_close=self._overlays.close,
            ),
        )

    def new(self) -> None:
        """Create and switch to a new session."""
        self._outbox.stop()
        self._runtime.new_session()
        self._conversation.clear()
        self._overlays.close_all()

    def switch(self, session: Session) -> None:
        """Switch to an existing session."""
        self._outbox.stop()
        try:
            switched = self._runtime.open_session(session.session_id)
        except SessionNotFoundError:
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
                strings.Palette.Sessions.CONFIRM_DELETE,
                [
                    DialogChoice(strings.Common.YES, lambda: self.delete(session), key="y"),
                    DialogChoice(strings.Common.NO, self._overlays.close, key="n"),
                ],
                on_cancel=self._overlays.close,
            ),
        )

    def delete(self, session: Session) -> None:
        """Delete a session."""
        removed_active = self._runtime.session.session_id == session.session_id
        if removed_active:
            self._outbox.stop()

        try:
            self._runtime.delete_session(session.session_id)
        except SessionNotFoundError:
            log.warning("delete_session_failed", session_id=str(session.session_id))
            return

        if removed_active:
            self._conversation.clear()
        self._overlays.close_all()


def _format_session_label(session: Session) -> str:
    date = session.created_at.strftime("%Y-%m-%d")
    return strings.Palette.Sessions.label(session.display_name, date, session.message_count)
