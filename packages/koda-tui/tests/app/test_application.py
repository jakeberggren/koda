from __future__ import annotations

import asyncio
from copy import replace
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from prompt_toolkit.keys import Keys

from koda.llm import (
    ApiKeyCredential,
    Catalog,
    CredentialsError,
    LLMConfigurationError,
    Model,
    ProviderCredential,
    ThinkingOption,
)
from koda.sessions import InMemorySessionStore, Session
from koda_tui import strings
from koda_tui.app.application import KodaTuiApp
from koda_tui.app.keybindings import create_keybindings
from koda_tui.appearance import RGBColor
from koda_tui.settings import Settings
from koda_tui.state import PendingInput

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pydantic import BaseModel

    from koda.llm import Credentials
    from koda.llm.types import LLMEvent, LLMRequest, LLMResponse
    from koda.messages import AssistantMessage


class _Credentials(dict[str, ProviderCredential]):
    def get_credential(self, key: str) -> ProviderCredential | None:
        return self.get(key)

    def set_credential(self, key: str, credential: ProviderCredential) -> None:
        self[key] = credential


class _UnreadableCredentials(_Credentials):
    def get_credential(self, key: str) -> ProviderCredential | None:
        raise CredentialsError(Path("credentials.json"), PermissionError("denied"))


def _connected() -> _Credentials:
    """An OpenAI API key."""
    return _Credentials({"openai:api-key": ApiKeyCredential(type="api_key", value="key")})


class _FakeLLM:
    """Ends every response without output, and remembers the last request."""

    def __init__(self) -> None:
        self.last_request: LLMRequest | None = None

    async def generate_stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        self.last_request = request
        return
        yield

    async def generate(self, request: LLMRequest) -> LLMResponse[AssistantMessage]:
        raise NotImplementedError

    async def generate_structured(
        self, request: LLMRequest, schema: type[BaseModel]
    ) -> LLMResponse[BaseModel]:
        raise NotImplementedError


class _Connect:
    """Connects every model to the same fake LLM, counting the connections."""

    def __init__(self) -> None:
        self.llm = _FakeLLM()
        self.calls = 0

    async def __call__(self, model: Model, credentials: Credentials) -> _FakeLLM:
        self.calls += 1
        await asyncio.sleep(0)
        return self.llm


_SETTINGS = Settings(provider="openai", model="gpt-5.2", theme="terminal-dark")


def _make_app(
    workspace: Path = Path("/workspace"),
    settings: Settings = _SETTINGS,
    credentials: _Credentials | None = None,
) -> tuple[KodaTuiApp, _Connect]:
    connect = _Connect()
    catalog, _warnings = Catalog.load()
    app = KodaTuiApp(
        settings,
        workspace,
        catalog=catalog,
        credentials=_connected() if credentials is None else credentials,
        store=InMemorySessionStore(),
        connect=connect,
    )
    return app, connect


def test_new_settings_are_saved_and_shown() -> None:
    credentials = _connected()
    credentials["bergetai:api-key"] = ApiKeyCredential(type="api_key", value="key")
    app, _ = _make_app(credentials=credentials)
    app.update_settings(
        replace(app.state.settings, provider="bergetai", model="zai-org/GLM-4.7-FP8")
    )

    assert app.state.active_model is not None
    assert app.state.active_model.id == "zai-org/GLM-4.7-FP8"
    assert Settings.load() == app.state.settings


def test_a_new_theme_redraws_without_asking_the_terminal_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _ = _make_app()
    ask_background = Mock()
    invalidate = Mock()
    monkeypatch.setattr(app._terminal, "ask_background", ask_background)  # noqa: SLF001
    monkeypatch.setattr(app, "invalidate", invalidate)

    app.update_settings(replace(app.state.settings, theme="auto"))

    assert app.appearance.theme == "auto"
    ask_background.assert_not_called()
    invalidate.assert_called_once_with()


def test_terminal_background_response_is_stored_for_any_theme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _ = _make_app()
    invalidate = Mock()
    monkeypatch.setattr(app, "invalidate", invalidate)

    app.on_terminal_background(RGBColor(0, 0, 128))

    assert app.appearance.terminal_background == (0, 0, 128)
    invalidate.assert_called_once_with()


def _thinking_model() -> Model:
    return Model(
        id="gpt-5.2",
        name="GPT 5.2",
        provider="openai",
        thinking_options=(
            ThinkingOption(id="none", label="None"),
            ThinkingOption(id="low", label="Low"),
            ThinkingOption(id="high", label="High"),
        ),
    )


def test_cycle_thinking_moves_to_the_next_level_and_wraps_around() -> None:
    app, _ = _make_app()
    app.update_settings = Mock()
    model = _thinking_model()
    app.state.active_model = model

    app.state.settings = replace(app.state.settings, thinking="none")
    app.cycle_thinking()
    assert app.update_settings.call_args.args[0].thinking == "low"

    app.state.settings = replace(app.state.settings, thinking="high")
    app.cycle_thinking()
    assert app.update_settings.call_args.args[0].thinking == "none"


def test_cycle_thinking_does_nothing_without_a_model() -> None:
    app, _ = _make_app()
    app.update_settings = Mock()
    app.state.active_model = None
    app.cycle_thinking()
    app.update_settings.assert_not_called()


def _escape(app: KodaTuiApp):
    (binding,) = create_keybindings(app).get_bindings_for_keys((Keys.Escape,))
    return binding


def test_escape_sends_whats_queued_now() -> None:
    app, _ = _make_app()
    app.outbox = Mock()
    app.state.responding = True
    app.state.pending_inputs = [PendingInput("next")]
    escape = _escape(app)
    assert escape.filter()
    escape.handler(Mock())
    app.outbox.send_now.assert_called_once_with()
    app.outbox.cancel.assert_not_called()


def test_escape_with_nothing_queued_interrupts_the_response() -> None:
    app, _ = _make_app()
    app.outbox = Mock()
    app.state.responding = True
    escape = _escape(app)
    assert escape.filter()
    escape.handler(Mock())
    app.outbox.cancel.assert_called_once_with()
    app.outbox.send_now.assert_not_called()


def test_escape_is_free_for_others_while_idle() -> None:
    app, _ = _make_app()
    assert not _escape(app).filter()


async def test_every_settings_change_rebuilds_the_agent() -> None:
    app, connect = _make_app()
    await _respond(app)
    app.invalidate = Mock()

    app.update_settings(replace(app.state.settings, sandbox="seatbelt"))

    app.invalidate.assert_called_once_with()
    await _respond(app)
    assert connect.calls == 2


def test_writing_a_message_takes_back_a_press_of_ctrl_c() -> None:
    app, _ = _make_app()
    app.outbox = Mock()
    app.exit_prompt.confirm()

    app.submit("hello", alternate=False)

    assert not app.state.exit_requested
    app.outbox.submit.assert_called_once_with("hello", steer=False)


def test_first_ctrl_c_asks_and_second_confirms() -> None:
    app, _ = _make_app()
    assert app.exit_prompt.confirm() is False
    assert app.state.exit_requested
    assert app.exit_prompt.confirm() is True
    assert not app.state.exit_requested


async def test_the_exit_prompt_goes_away_after_the_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("koda_tui.app.exit.EXIT_TIMEOUT", 0.01)
    app, _ = _make_app()
    app.exit_prompt.confirm()

    await asyncio.sleep(0.02)

    assert not app.state.exit_requested
    assert app.exit_prompt.confirm() is False


async def test_a_confirmed_exit_cancels_the_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("koda_tui.app.exit.EXIT_TIMEOUT", 0.01)
    app, _ = _make_app()
    app.exit_prompt.confirm()
    assert app.exit_prompt.confirm() is True
    app.state.exit_requested = True  # As if asked again after confirming.
    await asyncio.sleep(0.02)
    assert app.state.exit_requested  # The old timer didn't fire.


async def _respond(app: KodaTuiApp, text: str = "hello") -> list[object]:
    return [event async for event in app.respond(text)]


class TestAgent:
    """The agent the app builds for the current session, from the settings."""

    async def test_responding_saves_the_session(self) -> None:
        app, _ = _make_app()

        await _respond(app)

        [saved] = app._store.list_sessions()  # noqa: SLF001
        assert saved.session_id == app.state.session.session_id

    async def test_the_agent_is_built_once_for_concurrent_messages(self) -> None:
        app, connect = _make_app()

        await asyncio.gather(*(_respond(app) for _ in range(3)))

        assert connect.calls == 1

    async def test_a_new_session_gets_a_new_agent_with_fresh_workspace_context(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "AGENTS.md").write_text("First instructions.", encoding="utf-8")
        app, connect = _make_app(tmp_path)
        await _respond(app)

        (tmp_path / "AGENTS.md").write_text("Second instructions.", encoding="utf-8")
        await _respond(app)
        assert connect.llm.last_request is not None
        assert "First instructions." in (connect.llm.last_request.instructions or "")

        app.state.session = Session()
        await _respond(app)
        assert "Second instructions." in (connect.llm.last_request.instructions or "")

    async def test_thinking_resolves_to_the_models_first_mode(self) -> None:
        app, connect = _make_app(
            settings=replace(_SETTINGS, provider="anthropic", model="claude-fable-5")
        )

        await _respond(app)

        assert connect.llm.last_request is not None
        assert connect.llm.last_request.options.thinking == "low"

    async def test_responding_without_a_selected_model_fails(self) -> None:
        app, _ = _make_app(settings=replace(_SETTINGS, model=None))

        with pytest.raises(LLMConfigurationError, match="No model selected"):
            await _respond(app)


class TestStatus:
    """What stops Koda from responding, and the model it responds with."""

    def test_the_selected_connected_model_is_active(self) -> None:
        app, _ = _make_app()

        assert app.state.issue is None
        assert app.state.active_model is not None
        assert app.state.active_model.id == "gpt-5.2"
        assert [provider.id for provider in app.state.configured_providers] == ["openai"]

    def test_setup_is_required_without_credentials(self) -> None:
        app, _ = _make_app(credentials=_Credentials())
        assert app.state.issue == strings.Screen.Status.SETUP_REQUIRED

    def test_selection_is_required_without_a_model(self) -> None:
        app, _ = _make_app(settings=replace(_SETTINGS, model=None))

        assert app.state.issue == strings.Screen.Status.SELECTION_REQUIRED
        assert app.state.active_model is None

    def test_an_unknown_model_is_not_found(self) -> None:
        app, _ = _make_app(settings=replace(_SETTINGS, model="missing"))
        assert app.state.issue == strings.Screen.Status.MODEL_NOT_FOUND

    def test_a_model_of_an_unconnected_provider_is_not_connected(self) -> None:
        settings = replace(_SETTINGS, provider="bergetai", model="google/gemma-4-31B-it")
        app, _ = _make_app(settings=settings)
        assert app.state.issue == strings.Screen.Status.MODEL_NOT_CONNECTED

    def test_an_unreadable_credentials_file_is_reported(self) -> None:
        app, _ = _make_app(credentials=_UnreadableCredentials())

        assert app.state.issue == strings.Screen.Status.CREDENTIALS_UNREADABLE
        assert app.state.configured_providers == []

    def test_thinking_follows_the_settings_for_the_active_model(self) -> None:
        settings = replace(_SETTINGS, provider="anthropic", model="claude-fable-5")
        key = ApiKeyCredential(type="api_key", value="key")
        app, _ = _make_app(settings=settings, credentials=_Credentials({"anthropic:api-key": key}))
        assert app.state.thinking.id == "low"
