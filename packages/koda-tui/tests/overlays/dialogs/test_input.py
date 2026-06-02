"""Tests for TextInputDialog — generic text input dialog."""

# ruff: noqa: SLF001 - allow private member access for tests

from __future__ import annotations

import pytest

from koda_tui.overlays.dialogs.input import TextInputDialog


@pytest.fixture
def dialog_factory():
    """Factory that returns a TextInputDialog with call tracking."""

    def _make(*, mask_input: bool = False) -> tuple[TextInputDialog, dict]:
        calls = {"submit": [], "cancel": []}
        d = TextInputDialog(
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
        d._on_escape(None)
        assert len(calls["cancel"]) == 1
