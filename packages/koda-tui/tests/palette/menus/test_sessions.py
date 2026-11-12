"""Tests for the sessions menu: starting, opening and deleting sessions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda.messages import UserMessage
from koda.sessions import Session
from koda_tui.palette.menus.sessions import SessionMenu

if TYPE_CHECKING:
    from koda.sessions import SessionStore
    from koda_tui.palette.context import PaletteContext


def _menu(context: PaletteContext) -> tuple[SessionMenu, SessionStore]:
    return SessionMenu(context), context.store


def _saved(store: SessionStore) -> Session:
    session = Session(messages=[UserMessage(content="hello")])
    store.save_session(session)
    return session


def test_new_starts_an_unsaved_session(context: PaletteContext) -> None:
    menu, store = _menu(context)
    before = context.state.session

    menu.new()

    assert context.state.session.session_id != before.session_id
    assert store.list_sessions() == []


def test_switch_opens_a_saved_session(context: PaletteContext) -> None:
    menu, store = _menu(context)
    saved = _saved(store)

    menu.switch(saved)

    assert context.state.session == saved


def test_deleting_the_current_session_starts_a_new_one(context: PaletteContext) -> None:
    menu, store = _menu(context)
    saved = _saved(store)
    menu.switch(saved)

    menu.delete(saved)

    assert context.state.session.session_id != saved.session_id
    assert store.list_sessions() == []


def test_deleting_the_unsaved_current_session_starts_a_new_one(context: PaletteContext) -> None:
    menu, _store = _menu(context)
    unsaved = context.state.session

    menu.delete(unsaved)

    assert context.state.session.session_id != unsaved.session_id


def test_deleting_another_session_keeps_the_current_one(context: PaletteContext) -> None:
    menu, store = _menu(context)
    other = _saved(store)
    current = context.state.session

    menu.delete(other)

    assert context.state.session is current
    assert store.list_sessions() == []
