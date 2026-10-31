"""Tests for the composer's @ mentions and text handling."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from koda_service import ServiceStatus, ServiceStatusCode
from koda_tui.state import AppState
from koda_tui.views import Composer

if TYPE_CHECKING:
    from pathlib import Path

READY = ServiceStatus(code=ServiceStatusCode.READY, summary="Ready")


@pytest.fixture
def composer(tmp_path: Path) -> Composer:
    for path in ["README.md", "src/app.py", "src/apply.py", "src/appearance/theme.py"]:
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text("")
    return Composer(AppState(workspace=tmp_path, service_status=READY))


def _type(composer: Composer, text: str) -> None:
    composer.buffer.text = text
    composer.buffer.cursor_position = len(text)


def test_typing_a_mention_suggests_files(composer: Composer) -> None:
    _type(composer, "look at @src/ap")
    assert composer.is_mentioning
    assert composer.has_suggestion


def test_accepting_replaces_the_mention_with_the_path(composer: Composer) -> None:
    _type(composer, "look at @src/ap please")
    composer.buffer.cursor_position = len("look at @src/ap")
    composer.move_suggestion(1)
    assert composer.accept_suggestion()
    assert composer.text == "look at src/apply.py please"
    assert not composer.is_mentioning


def test_selection_follows_the_same_file_while_typing(composer: Composer) -> None:
    _type(composer, "@src/ap")
    composer.move_suggestion(1)
    selected = composer.text
    _type(composer, "@src/app")
    composer.accept_suggestion()
    assert composer.text != selected
    assert composer.text.startswith("src/apply.py")


def test_leaving_the_mention_closes_the_suggestions(composer: Composer) -> None:
    _type(composer, "@src/ap")
    _type(composer, "@src/ap and more")
    assert not composer.is_mentioning
    assert not composer.accept_suggestion()


def test_text_can_be_set_and_cleared(composer: Composer) -> None:
    composer.text = "draft"
    assert composer.buffer.cursor_position == len("draft")
    composer.clear()
    assert composer.text == ""
