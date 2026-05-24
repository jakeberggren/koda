"""Tests for ConfirmDialog — yes/no confirmation dialog."""

# ruff: noqa: SLF001 - allow private member access for tests

from __future__ import annotations

import pytest

from koda_tui.overlays.dialogs.confirm import ConfirmDialog


@pytest.fixture
def dialog_factory():
    """Factory that returns a ConfirmDialog with call tracking."""

    def _make() -> tuple[ConfirmDialog, dict]:
        calls = {"confirm": [], "cancel": []}
        d = ConfirmDialog(
            message="Are you sure?",
            on_confirm=lambda: calls["confirm"].append(None),
            on_cancel=lambda: calls["cancel"].append(None),
        )
        return d, calls

    return _make


class TestCallbacks:
    def test_enter_confirms_when_yes_selected(self, dialog_factory) -> None:
        d, calls = dialog_factory()
        d._on_enter(None)
        assert len(calls["confirm"]) == 1
        assert calls["cancel"] == []

    def test_enter_cancels_when_no_selected(self, dialog_factory) -> None:
        d, calls = dialog_factory()
        d._selected = False
        d._on_enter(None)
        assert len(calls["cancel"]) == 1
        assert calls["confirm"] == []

    def test_escape_cancels(self, dialog_factory) -> None:
        d, calls = dialog_factory()
        d._on_escape(None)
        assert len(calls["cancel"]) == 1

    def test_y_key_confirms(self, dialog_factory) -> None:
        d, calls = dialog_factory()
        d._on_yes(None)
        assert len(calls["confirm"]) == 1

    def test_n_key_cancels(self, dialog_factory) -> None:
        d, calls = dialog_factory()
        d._on_no(None)
        assert len(calls["cancel"]) == 1


class TestToggle:
    def test_toggle_switches(self, dialog_factory) -> None:
        d, _ = dialog_factory()
        assert d._selected is True
        d._on_toggle(None)
        assert d._selected is False
        d._on_toggle(None)
        assert d._selected is True

    def test_button_text_reflects_selection(self, dialog_factory) -> None:
        d, _ = dialog_factory()
        text = d._button_text()
        assert text[0] == ("class:dialog.selected", " Yes ")
        assert text[2] == ("class:dialog.button", " No ")

        d._selected = False
        text = d._button_text()
        assert text[0] == ("class:dialog.button", " Yes ")
        assert text[2] == ("class:dialog.selected", " No ")
