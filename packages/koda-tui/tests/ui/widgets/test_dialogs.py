"""Tests for the dialog widgets."""

# ruff: noqa: SLF001 - allow private member access for tests

from __future__ import annotations

from unittest.mock import Mock

import pytest
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import FormattedTextControl, Layout

from koda_tui.appearance import Tokens, compose
from koda_tui.ui.primitives.text import WordWrapControl
from koda_tui.ui.widgets import ChoiceDialog, DialogChoice, InputDialog, MessageDialog


def _press(dialog: ChoiceDialog | InputDialog, key: str) -> None:
    dialog._panel.key_bindings.get_bindings_for_keys((key,))[-1].handler(Mock())


@pytest.fixture
def dialog_factory():
    """Factory that returns an InputDialog with call tracking."""

    def _make(*, mask_input: bool = False) -> tuple[InputDialog, dict]:
        calls = {"submit": [], "cancel": []}
        d = InputDialog(
            title="Test Title",
            on_submit=calls["submit"].append,
            on_cancel=lambda: calls["cancel"].append(None),
            mask_input=mask_input,
        )
        return d, calls

    return _make


class TestCallbacks:
    def test_submit(self, dialog_factory) -> None:
        d, calls = dialog_factory()
        d.input_buffer.text = "hello"
        d._on_enter(None)
        assert calls["submit"] == ["hello"]

    def test_submit_strips(self, dialog_factory) -> None:
        d, calls = dialog_factory()
        d.input_buffer.text = "  hello  "
        d._on_enter(None)
        assert calls["submit"] == ["hello"]

    def test_submit_empty_noop(self, dialog_factory) -> None:
        d, calls = dialog_factory()
        d.input_buffer.text = "   "
        d._on_enter(None)
        assert calls["submit"] == []

    def test_cancel(self, dialog_factory) -> None:
        d, calls = dialog_factory()
        _press(d, Keys.Escape)
        assert len(calls["cancel"]) == 1

    def test_focuses_the_input(self, dialog_factory) -> None:
        d, _ = dialog_factory()
        layout = Layout(d)
        layout.focus(d)
        assert layout.current_buffer is d.input_buffer


@pytest.fixture
def confirm_factory():
    """A yes/no ChoiceDialog, as the palette opens for confirmations, with call tracking."""

    def _make() -> tuple[ChoiceDialog, dict]:
        calls = {"yes": [], "no": [], "cancel": []}
        d = ChoiceDialog(
            message="Are you sure?",
            choices=[
                DialogChoice("Yes", lambda: calls["yes"].append(None), key="y"),
                DialogChoice("No", lambda: calls["no"].append(None), key="n"),
            ],
            on_cancel=lambda: calls["cancel"].append(None),
        )
        return d, calls

    return _make


class TestChoiceDialog:
    def test_enter_selects_first_choice_by_default(self, confirm_factory) -> None:
        d, calls = confirm_factory()
        d._on_enter(None)
        assert calls == {"yes": [None], "no": [], "cancel": []}

    def test_enter_selects_after_moving(self, confirm_factory) -> None:
        d, calls = confirm_factory()
        d._on_next(None)
        d._on_enter(None)
        assert calls == {"yes": [], "no": [None], "cancel": []}

    def test_selection_wraps(self, confirm_factory) -> None:
        d, _ = confirm_factory()
        d._on_previous(None)
        assert d._selected == 1
        d._on_next(None)
        assert d._selected == 0

    def test_escape_cancels(self, confirm_factory) -> None:
        d, calls = confirm_factory()
        _press(d, Keys.Escape)
        assert calls == {"yes": [], "no": [], "cancel": [None]}

    def test_focuses_the_title_when_there_is_no_input(self, confirm_factory) -> None:
        d, _ = confirm_factory()
        layout = Layout(d)
        layout.focus(d)
        assert isinstance(layout.current_control, FormattedTextControl)
        assert layout.current_buffer is None

    @pytest.mark.parametrize(("key", "chosen"), [("y", "yes"), ("n", "no")])
    def test_choice_key_selects_directly(self, confirm_factory, key: str, chosen: str) -> None:
        d, calls = confirm_factory()
        _press(d, key)
        assert calls[chosen] == [None]

    def test_button_text_reflects_selection(self, confirm_factory) -> None:
        d, _ = confirm_factory()
        selected = compose(Tokens.Surface.SELECTED, Tokens.Text.STRONG)
        assert list(d._choice_text()) == [
            (selected, " Yes "),
            ("", "  "),
            (Tokens.Text.MUTED, " No "),
        ]
        d._on_next(None)
        assert list(d._choice_text())[2] == (selected, " No ")


def test_message_dialog_focuses_its_text_and_closes_on_enter() -> None:
    closed = []
    d = MessageDialog("Title", "Detail", lambda: closed.append(None))
    layout = Layout(d)
    layout.focus(d)
    assert isinstance(layout.current_control, WordWrapControl)
    d._panel.key_bindings.get_bindings_for_keys((Keys.Enter,))[-1].handler(Mock())
    assert closed == [None]
