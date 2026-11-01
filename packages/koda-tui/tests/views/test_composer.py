"""Tests for the composer's @ mentions and text handling."""

from __future__ import annotations

import asyncio
import inspect
from typing import TYPE_CHECKING

import pytest
from prompt_toolkit.keys import Keys

from koda_tui.state import AppState
from koda_tui.terminal.keys import ALT_ENTER
from koda_tui.views import Composer

if TYPE_CHECKING:
    from pathlib import Path

    from koda_service import ServiceStatus


@pytest.fixture
def composer(tmp_path: Path, ready: ServiceStatus) -> Composer:
    for path in ["README.md", "src/app.py", "src/apply.py", "src/appearance/theme.py"]:
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text("")
    return Composer(
        AppState(workspace=tmp_path, service_status=ready),
        on_submit=_record,
    )


SUBMITTED: list[tuple[str, str]] = []


def _record(text: str, *, alternate: bool) -> None:
    SUBMITTED.append(("alternate" if alternate else "submit", text))


@pytest.fixture(autouse=True)
def _clear_submitted() -> None:
    SUBMITTED.clear()


async def _press(composer: Composer, *keys: str) -> None:
    """Run the composer's binding for ``keys``, as prompt_toolkit would."""
    active = [b for b in composer.key_bindings.get_bindings_for_keys(keys) if b.filter()]
    result = active[-1].handler(None)  # type: ignore
    if inspect.isawaitable(result):
        await result


def _type(composer: Composer, text: str) -> None:
    composer.buffer.text = text
    composer.buffer.cursor_position = len(text)


async def _settle(composer: Composer) -> list[str]:
    """The suggestions once they stop changing, as the completer finds them off-thread."""
    shown: list[str] | None = None
    steady = 0
    for _ in range(200):
        await asyncio.sleep(0.005)
        now = [item.label for item in composer._suggestions.items]  # noqa: SLF001
        steady = steady + 1 if now == shown else 0
        shown = now
        if steady >= 5:
            break
    return shown or []


async def test_typing_a_mention_suggests_files(composer: Composer) -> None:
    _type(composer, "look at @src/ap")
    assert composer.is_mentioning()
    assert await _settle(composer) == ["src/app.py", "src/apply.py", "src/appearance/theme.py"]
    assert composer.has_suggestion()


async def test_accepting_puts_the_path_after_the_at_and_leaves_the_mention(
    composer: Composer,
) -> None:
    _type(composer, "look at @src/ap")
    await _settle(composer)
    composer.move_suggestion(1)
    assert composer.accept_suggestion()
    assert composer.text == "look at @src/apply.py "
    assert not composer.is_mentioning()
    assert await _settle(composer) == []


async def test_selection_follows_the_same_file_while_typing(composer: Composer) -> None:
    _type(composer, "@src/ap")
    await _settle(composer)
    composer.move_suggestion(1)
    _type(composer, "@src/app")
    await _settle(composer)
    composer.accept_suggestion()
    assert composer.text == "@src/apply.py "


async def test_a_backspace_in_a_mention_keeps_suggesting(composer: Composer) -> None:
    _type(composer, "@src/appl")
    await _settle(composer)
    composer.buffer.delete_before_cursor()
    assert await _settle(composer) == ["src/app.py", "src/apply.py", "src/appearance/theme.py"]


async def test_moving_into_a_mention_suggests_again(composer: Composer) -> None:
    _type(composer, "@src/apply and more")
    await _settle(composer)
    assert not composer.has_suggestion()
    composer.buffer.cursor_position = len("@src/apply")
    assert await _settle(composer) == ["src/apply.py"]


async def test_leaving_the_mention_closes_the_suggestions(composer: Composer) -> None:
    _type(composer, "@src/ap")
    await _settle(composer)
    _type(composer, "@src/ap and more")
    assert not composer.is_mentioning()
    assert not composer.accept_suggestion()


async def test_a_mention_without_matches_suggests_nothing(composer: Composer) -> None:
    _type(composer, "@nothing-like-this")
    assert await _settle(composer) == []
    assert composer.is_mentioning()


def test_setting_the_text_puts_the_cursor_at_its_end(composer: Composer) -> None:
    composer.text = "draft"
    assert composer.buffer.cursor_position == len("draft")


async def test_enter_submits_the_trimmed_text_and_clears(composer: Composer) -> None:
    _type(composer, "  hello  ")
    await _press(composer, Keys.Enter)
    assert SUBMITTED == [("submit", "hello")]
    assert composer.text == ""


async def test_alt_enter_submits_the_other_way(composer: Composer) -> None:
    _type(composer, "hello")
    await _press(composer, *ALT_ENTER)
    assert SUBMITTED == [("alternate", "hello")]


async def test_enter_on_a_blank_composer_submits_nothing(composer: Composer) -> None:
    _type(composer, "   ")
    await _press(composer, Keys.Enter)
    assert SUBMITTED == []


async def test_ctrl_j_starts_a_new_line(composer: Composer) -> None:
    _type(composer, "hello")
    await _press(composer, Keys.ControlJ)
    assert composer.text == "hello\n"


async def test_enter_while_suggesting_accepts_the_file_instead(composer: Composer) -> None:
    _type(composer, "look at @src/app")
    await _settle(composer)
    await _press(composer, Keys.Enter)
    assert SUBMITTED == []
    assert composer.text == "look at @src/app.py "
