from __future__ import annotations

from unittest.mock import Mock

import pytest

from koda_tui.app.application import KodaTuiApp
from koda_tui.ui.palette.palette_manager import PaletteManager


def _make_settings_mock(unsubscribe: Mock) -> Mock:
    settings = Mock(
        spec=[
            "subscribe",
            "provider",
            "model",
            "show_scrollbar",
            "queue_inputs",
            "theme",
        ]
    )
    settings.provider = "openai"
    settings.model = "gpt-5.2"
    settings.show_scrollbar = True
    settings.queue_inputs = True
    settings.theme = "dark"
    settings.subscribe.return_value = unsubscribe
    return settings


def _make_app() -> tuple[KodaTuiApp, Mock]:
    unsubscribe = Mock()
    settings = _make_settings_mock(unsubscribe)
    backend = Mock(spec=["reconfigure"])
    return KodaTuiApp(settings=settings, backend=backend), unsubscribe


def test_close_is_idempotent() -> None:
    app, unsubscribe = _make_app()
    app.close()
    app.close()
    unsubscribe.assert_called_once_with()


@pytest.mark.asyncio
async def test_run_always_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    app, unsubscribe = _make_app()

    class _FakeApp:
        async def run_async(self) -> None:
            raise RuntimeError("boom")

    def _fake_create_application() -> _FakeApp:
        return _FakeApp()

    def _ignore_set_app(_self: PaletteManager, _app: object) -> None:
        return None

    monkeypatch.setattr(app, "_create_application", _fake_create_application)
    monkeypatch.setattr(PaletteManager, "set_app", _ignore_set_app)

    with pytest.raises(RuntimeError):
        await app.run()

    unsubscribe.assert_called_once_with()
