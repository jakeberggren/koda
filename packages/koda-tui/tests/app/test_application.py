from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import Mock

import pytest
from prompt_toolkit.keys import Keys

from koda.llm import ModelDefinition, ThinkingOption
from koda_common.settings import SettingChange
from koda_service import ServiceDiagnostics, ServiceStatus, ServiceStatusCode
from koda_tui.app import application
from koda_tui.app.application import KodaTuiApp
from koda_tui.app.keybindings import create_keybindings
from koda_tui.appearance import RGBColor
from koda_tui.settings import AppSettings
from koda_tui.state import PendingInput


def _make_settings_mock(unsubscribe: Mock) -> Mock:
    settings = Mock(
        spec=[
            "subscribe",
            "set",
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
    settings.theme = "terminal-dark"
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
        workspace=Path("/workspace"),
    )
    return (app, settings, tui_settings, service, unsubscribe_settings, unsubscribe_tui_settings)


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
    app._on_settings_changed(  # noqa: SLF001
        (
            SettingChange(name="provider", old_value="openai", new_value="bergetai"),
            SettingChange(name="model", old_value="gpt-5.2", new_value="zai-org/GLM-4.7"),
        )
    )

    service.update_settings.assert_called_once_with(settings)
    service.get_model.assert_called_with("bergetai", "zai-org/GLM-4.7")
    assert app.state.context_window == 128_000


def test_theme_change_redraws_without_requerying_terminal_background(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _settings, tui_settings, _service, _unsubscribe, _unsubscribe_tui = _make_app()
    request_refresh = Mock()
    invalidate = Mock()
    monkeypatch.setattr(app._terminal, "ask_background", request_refresh)  # noqa: SLF001
    monkeypatch.setattr(app, "invalidate", invalidate)

    tui_settings.theme = "auto"
    app._on_tui_settings_changed(  # noqa: SLF001
        (SettingChange(name="theme", old_value="terminal-dark", new_value="auto"),)
    )

    request_refresh.assert_not_called()
    invalidate.assert_called_once_with()


def test_terminal_background_response_is_stored_for_any_theme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _settings, tui_settings, _service, _unsubscribe, _unsubscribe_tui = _make_app()
    invalidate = Mock()
    monkeypatch.setattr(app, "invalidate", invalidate)

    tui_settings.theme = "terminal-dark"
    app._on_terminal_background(RGBColor(0, 0, 128))  # noqa: SLF001

    assert app.appearance.terminal_background == (0, 0, 128)
    invalidate.assert_called_once_with()


@pytest.mark.asyncio
async def test_run_follows_settings_only_while_it_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    app, settings, tui_settings, _service, unsubscribe, unsubscribe_tui = _make_app()
    settings.subscribe.assert_not_called()
    tui_settings.subscribe.assert_not_called()

    class _FakeApp:
        async def run_async(self) -> None:
            settings.subscribe.assert_called_once_with(app._on_settings_changed)  # noqa: SLF001
            tui_settings.subscribe.assert_called_once_with(app._on_tui_settings_changed)  # noqa: SLF001
            raise RuntimeError("boom")

    monkeypatch.setattr(application, "_create_application", lambda *_args, **_kwargs: _FakeApp())

    with pytest.raises(RuntimeError, match="boom"):
        await app.run()

    unsubscribe.assert_called_once_with()
    unsubscribe_tui.assert_called_once_with()


def _thinking_model() -> ModelDefinition:
    return ModelDefinition(
        id="gpt-5.2",
        name="GPT 5.2",
        provider="openai",
        thinking_options=[
            ThinkingOption(id="none", label="None"),
            ThinkingOption(id="low", label="Low"),
            ThinkingOption(id="high", label="High"),
        ],
    )


def test_cycle_thinking_moves_to_the_next_level_and_wraps_around() -> None:
    app, settings, *_ = _make_app()
    model = _thinking_model()
    app.state.active_model = model

    app.state.thinking = model.effective_thinking_options[0]
    app.cycle_thinking()
    settings.set.assert_called_with("thinking", model.effective_thinking_options[1].id)

    app.state.thinking = model.effective_thinking_options[-1]
    app.cycle_thinking()
    settings.set.assert_called_with("thinking", model.effective_thinking_options[0].id)


def test_cycle_thinking_does_nothing_without_a_model() -> None:
    app, settings, *_ = _make_app()
    app.state.active_model = None
    app.cycle_thinking()
    settings.set.assert_not_called()


def _escape(app: KodaTuiApp):
    (binding,) = create_keybindings(app).get_bindings_for_keys((Keys.Escape,))
    return binding


def test_escape_sends_whats_queued_now() -> None:
    app, *_ = _make_app()
    app.outbox = Mock()
    app.state.responding = True
    app.state.pending_inputs = [PendingInput("next")]
    escape = _escape(app)
    assert escape.filter()
    escape.handler(Mock())
    app.outbox.send_now.assert_called_once_with()
    app.outbox.cancel.assert_not_called()


def test_escape_with_nothing_queued_interrupts_the_response() -> None:
    app, *_ = _make_app()
    app.outbox = Mock()
    app.state.responding = True
    escape = _escape(app)
    assert escape.filter()
    escape.handler(Mock())
    app.outbox.cancel.assert_called_once_with()
    app.outbox.send_now.assert_not_called()


def test_escape_is_free_for_others_while_idle() -> None:
    app, *_ = _make_app()
    assert not _escape(app).filter()


def test_every_core_setting_change_reaches_the_service() -> None:
    app, settings, _tui_settings, service, *_ = _make_app()
    app.invalidate = Mock()

    change = SettingChange(name="bash_execution_sandbox", old_value="host", new_value="docker")
    app._on_settings_changed((change,))  # noqa: SLF001

    service.update_settings.assert_called_once_with(settings)
    app.invalidate.assert_called_once_with()


def test_any_tui_setting_change_redraws() -> None:
    app, *_ = _make_app()
    app.invalidate = Mock()

    app._on_tui_settings_changed(  # noqa: SLF001
        (SettingChange(name="queue_inputs", old_value=True, new_value=False),)
    )

    app.invalidate.assert_called_once_with()


def test_writing_a_message_takes_back_a_press_of_ctrl_c() -> None:
    app, *_ = _make_app()
    app.outbox = Mock()
    app.exit_prompt.confirm()

    app._submit("hello", alternate=False)  # noqa: SLF001 - the composer's submit callback

    assert not app.state.exit_requested
    app.outbox.submit.assert_called_once_with("hello", steer=False)


def test_first_ctrl_c_asks_and_second_confirms() -> None:
    app, *_ = _make_app()
    assert app.exit_prompt.confirm() is False
    assert app.state.exit_requested
    assert app.exit_prompt.confirm() is True
    assert not app.state.exit_requested


async def test_the_exit_prompt_goes_away_after_the_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(application, "EXIT_TIMEOUT", 0.01)
    app, *_ = _make_app()
    app.exit_prompt.confirm()

    await asyncio.sleep(0.02)

    assert not app.state.exit_requested
    assert app.exit_prompt.confirm() is False


async def test_a_confirmed_exit_cancels_the_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(application, "EXIT_TIMEOUT", 0.01)
    app, *_ = _make_app()
    app.exit_prompt.confirm()
    assert app.exit_prompt.confirm() is True
    app.state.exit_requested = True  # As if asked again after confirming.
    await asyncio.sleep(0.02)
    assert app.state.exit_requested  # The old timer didn't fire.
