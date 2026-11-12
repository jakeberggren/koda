from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from koda_tui import strings
from koda_tui.app import KodaTuiApp
from koda_tui.main import main

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _no_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("koda_tui.main.configure_logging", lambda: None)


def test_main_runs_the_app_for_the_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    ran: list[KodaTuiApp] = []

    async def _run(app: KodaTuiApp) -> None:
        ran.append(app)

    monkeypatch.setattr(KodaTuiApp, "run", _run)

    main()

    [app] = ran
    assert app.state.workspace == tmp_path.resolve()


def test_main_says_what_is_wrong_with_the_settings_and_exits(
    home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = home / ".koda" / "settings.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"theme": "neon", "not_a_setting": 1}', encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    assert capsys.readouterr().err.startswith(
        strings.App.failed_to_start(f"Invalid settings in {path}\n")
    )
