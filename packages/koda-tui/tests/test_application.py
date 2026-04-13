from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from koda_common.settings import SettingChange
from koda_service import ServiceStatus
from koda_service.types import ModelDefinition, ThinkingOption
from koda_tui.app.application import KodaTuiApp
from koda_tui.ui.palette.palette_manager import PaletteManager


def _make_settings_mock(unsubscribe: Mock) -> Mock:
    settings = Mock(
        spec=[
            "subscribe",
            "provider",
            "model",
            "thinking",
            "show_scrollbar",
            "queue_inputs",
            "theme",
        ]
    )
    settings.provider = "openai"
    settings.model = "gpt-5.2"
    settings.thinking = "none"
    settings.show_scrollbar = True
    settings.queue_inputs = True
    settings.theme = "dark"
    settings.subscribe.return_value = unsubscribe
    return settings


def _make_app() -> tuple[KodaTuiApp, Mock, Mock, Mock]:
    unsubscribe = Mock()
    settings = _make_settings_mock(unsubscribe)
    service = Mock(
        spec=[
            "ready",
            "update_settings",
            "list_models",
            "list_providers",
            "list_connected_providers",
            "list_selectable_models",
            "chat",
            "new_session",
            "switch_session",
            "delete_session",
            "list_sessions",
            "active_session",
        ]
    )
    service.list_models.return_value = [
        ModelDefinition(
            id="gpt-5.2",
            name="GPT 5.2",
            provider="openai",
            context_window=400_000,
            thinking_options=[ThinkingOption(id="none", label="None")],
        )
    ]
    service.ready.return_value = ServiceStatus(is_ready=True, summary="Ready")
    app = KodaTuiApp(
        settings=settings,
        service=service,
        workspace_root=Path("/workspace"),
    )
    return (app, settings, service, unsubscribe)


def test_close_is_idempotent() -> None:
    app, _settings, _service, unsubscribe = _make_app()
    app.close()
    app.close()
    unsubscribe.assert_called_once_with()


def test_batched_provider_and_model_changes_update_app_state() -> None:
    app, settings, service, _unsubscribe = _make_app()
    settings.provider = "bergetai"
    settings.model = "zai-org/GLM-4.7"
    service.list_models.return_value = [
        ModelDefinition(
            id="zai-org/GLM-4.7",
            name="GLM-4.7",
            provider="bergetai",
            context_window=128_000,
            thinking_options=[],
        )
    ]
    on_settings_changed = settings.subscribe.call_args.args[0]

    on_settings_changed(
        (
            SettingChange(name="provider", old_value="openai", new_value="bergetai"),
            SettingChange(name="model", old_value="gpt-5.2", new_value="zai-org/GLM-4.7"),
        )
    )

    service.update_settings.assert_called_once_with(settings)
    service.list_models.assert_called_with("bergetai")
    assert app.state.provider_name == "bergetai"
    assert app.state.model_name == "zai-org/GLM-4.7"
    assert app.state.context_window == 128_000


@pytest.mark.asyncio
async def test_run_always_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _settings, _service, unsubscribe = _make_app()

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
