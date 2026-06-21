from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from koda.llm import ModelDefinition, ThinkingOption
from koda_common.settings import SettingChange
from koda_service import ServiceDiagnostics, ServiceStatus, ServiceStatusCode
from koda_tui.app.application import KodaTuiApp
from koda_tui.settings import AppSettings


def _make_settings_mock(unsubscribe: Mock) -> Mock:
    settings = Mock(
        spec=[
            "subscribe",
            "provider",
            "model",
            "thinking",
        ]
    )
    settings.provider = "openai"
    settings.model = "gpt-5.2"
    settings.thinking = "none"
    settings.subscribe.return_value = unsubscribe
    return settings


def _make_tui_settings_mock(unsubscribe: Mock) -> Mock:
    settings = Mock(
        spec=[
            "subscribe",
            "show_scrollbar",
            "queue_inputs",
            "theme",
        ]
    )
    settings.show_scrollbar = True
    settings.queue_inputs = True
    settings.theme = "dark"
    settings.subscribe.return_value = unsubscribe
    return settings


def _make_app() -> tuple[KodaTuiApp, Mock, Mock, Mock, Mock, Mock]:
    unsubscribe_settings = Mock()
    unsubscribe_tui_settings = Mock()
    settings = _make_settings_mock(unsubscribe_settings)
    tui_settings = _make_tui_settings_mock(unsubscribe_tui_settings)
    service = Mock(
        spec=[
            "ready",
            "status",
            "update_settings",
            "list_models",
            "list_providers",
            "list_configured_providers",
            "list_configured_models",
            "get_model",
            "diagnostics",
            "chat",
            "create_session",
            "switch_session",
            "delete_session",
            "list_sessions",
            "active_session",
        ]
    )
    service.get_model.return_value = ModelDefinition(
        id="gpt-5.2",
        name="GPT 5.2",
        provider="openai",
        context_window=400_000,
        thinking_options=[ThinkingOption(id="none", label="None")],
    )
    service.status.return_value = ServiceStatus(code=ServiceStatusCode.READY, summary="Ready")
    service.diagnostics.return_value = ServiceDiagnostics(startup_warnings=[])
    app = KodaTuiApp(
        app_settings=AppSettings(core=settings, tui=tui_settings),
        service=service,
        workspace_root=Path("/workspace"),
    )
    return (app, settings, tui_settings, service, unsubscribe_settings, unsubscribe_tui_settings)


def test_close_is_idempotent() -> None:
    app, _settings, _tui_settings, _service, unsubscribe, unsubscribe_tui = _make_app()
    app.close()
    app.close()
    unsubscribe.assert_called_once_with()
    unsubscribe_tui.assert_called_once_with()


def test_batched_provider_and_model_changes_update_app_state() -> None:
    app, settings, _tui_settings, service, _unsubscribe, _unsubscribe_tui = _make_app()
    settings.provider = "bergetai"
    settings.model = "zai-org/GLM-4.7"
    service.get_model.return_value = ModelDefinition(
        id="zai-org/GLM-4.7",
        name="GLM-4.7",
        provider="bergetai",
        context_window=128_000,
        thinking_options=[],
    )
    on_settings_changed = settings.subscribe.call_args.args[0]

    on_settings_changed(
        (
            SettingChange(name="provider", old_value="openai", new_value="bergetai"),
            SettingChange(name="model", old_value="gpt-5.2", new_value="zai-org/GLM-4.7"),
        )
    )

    service.update_settings.assert_called_once_with(settings)
    service.get_model.assert_called_with("bergetai", "zai-org/GLM-4.7")
    assert app.state.provider_id == "bergetai"
    assert app.state.context_window == 128_000


def test_theme_change_to_auto_requeries_terminal_background(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query_osc11 = Mock(side_effect=[(0, 0, 0), (255, 255, 255)])
    monkeypatch.setattr("koda_tui.app.application.query_osc11", query_osc11)
    _app, _settings, tui_settings, _service, _unsubscribe, _unsubscribe_tui = _make_app()
    on_tui_settings_changed = tui_settings.subscribe.call_args.args[0]

    tui_settings.theme = "auto"
    on_tui_settings_changed((SettingChange(name="theme", old_value="dark", new_value="auto"),))

    assert query_osc11.call_count == 2


def test_terminal_focus_in_requeries_terminal_background_in_auto_theme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query_osc11 = Mock(side_effect=[(0, 0, 0), (255, 255, 255)])
    monkeypatch.setattr("koda_tui.app.application.query_osc11", query_osc11)
    app, _settings, tui_settings, _service, _unsubscribe, _unsubscribe_tui = _make_app()

    tui_settings.theme = "auto"
    app.handle_terminal_focus_in()

    assert query_osc11.call_count == 2


def test_terminal_focus_in_ignores_manual_theme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query_osc11 = Mock(side_effect=[(0, 0, 0), (255, 255, 255)])
    monkeypatch.setattr("koda_tui.app.application.query_osc11", query_osc11)
    app, _settings, tui_settings, _service, _unsubscribe, _unsubscribe_tui = _make_app()

    tui_settings.theme = "light"
    app.handle_terminal_focus_in()

    assert query_osc11.call_count == 1


@pytest.mark.asyncio
async def test_run_always_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _settings, _tui_settings, _service, unsubscribe, unsubscribe_tui = _make_app()

    class _FakeApp:
        async def run_async(self) -> None:
            raise RuntimeError("boom")

    def _fake_create_application() -> _FakeApp:
        return _FakeApp()

    monkeypatch.setattr(app, "_create_application", _fake_create_application)

    with pytest.raises(RuntimeError):
        await app.run()

    unsubscribe.assert_called_once_with()
    unsubscribe_tui.assert_called_once_with()
