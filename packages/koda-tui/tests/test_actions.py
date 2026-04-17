from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from unittest.mock import Mock
from uuid import uuid4

from koda_service.exceptions import ServiceSessionNotFoundError
from koda_service.types import (
    AssistantMessage,
    ModelDefinition,
    SessionInfo,
    ThinkingOption,
    ThinkingOptionId,
    UserMessage,
)
from koda_service.types.messages import TokenUsage
from koda_tui.actions import (
    cycle_thinking,
    delete_session,
    new_session,
    select_model,
    set_provider_api_key,
    set_thinking,
    switch_session,
    toggle_queue_inputs,
    toggle_scrollbar,
    toggle_theme,
)
from koda_tui.state import AppState, Message, MessageRole


def _session_info() -> SessionInfo:
    return SessionInfo(
        session_id=uuid4(),
        name="Session",
        message_count=0,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _state_with_conversation() -> AppState:
    state = AppState(
        provider_name="openai",
        model_name="gpt-5.2",
        workspace_root=Path("/workspace"),
    )
    state.messages = [Message(role=MessageRole.USER, content="old")]
    state.current_streaming_content = "partial"
    state.is_streaming = True
    return state


def test_new_session_success_resets_state() -> None:
    state = _state_with_conversation()
    service = Mock(spec=["new_session"])
    service.new_session.return_value = _session_info()

    result = new_session(service, state)

    assert result.ok is True
    assert result.error is None
    service.new_session.assert_called_once_with()
    assert state.messages == []
    assert state.current_streaming_content == ""
    assert state.is_streaming is False


def test_switch_session_success_converts_messages() -> None:
    state = _state_with_conversation()
    service = Mock(spec=["switch_session"])
    service.switch_session.return_value = (_session_info(), [UserMessage(content="hello")])
    session_id = uuid4()

    result = switch_session(session_id, service, state)

    assert result.ok is True
    service.switch_session.assert_called_once_with(session_id)
    assert len(state.messages) == 1
    assert state.messages[0].role == MessageRole.USER
    assert state.messages[0].content == "hello"


def test_switch_session_restores_usage_from_last_assistant_message() -> None:
    state = _state_with_conversation()
    service = Mock(spec=["switch_session"])
    service.switch_session.return_value = (
        _session_info(),
        [
            UserMessage(content="hello"),
            AssistantMessage(
                content="done",
                usage=TokenUsage(input_tokens=1_200, output_tokens=300, total_tokens=1_500),
            ),
        ],
    )
    session_id = uuid4()

    result = switch_session(session_id, service, state)

    assert result.ok is True
    assert state.usage is not None
    assert state.total_usage is not None
    assert state.usage.input_tokens == 1_200
    assert state.usage.output_tokens == 300
    assert state.usage.total_tokens == 1_500
    assert state.total_usage.input_tokens == 1_200
    assert state.total_usage.output_tokens == 300
    assert state.total_usage.total_tokens == 1_500


def test_switch_session_not_found_returns_error() -> None:
    state = _state_with_conversation()
    service = Mock(spec=["switch_session"])
    service.switch_session.side_effect = ServiceSessionNotFoundError

    result = switch_session(uuid4(), service, state)

    assert result.ok is False
    assert result.error == "Session not found"
    assert state.messages[0].content == "old"
    assert state.current_streaming_content == "partial"
    assert state.is_streaming is True


def test_delete_session_active_removed_resets_state() -> None:
    state = _state_with_conversation()
    active = _session_info()
    service = Mock(spec=["active_session", "delete_session"])
    service.active_session.return_value = active
    session_id = active.session_id

    result = delete_session(session_id, service, state)

    assert result.ok is True
    assert result.payload is not None
    assert result.payload.removed_active_session is True
    service.active_session.assert_called_once_with()
    service.delete_session.assert_called_once_with(session_id)
    assert state.messages == []


def test_delete_session_non_active_keeps_state() -> None:
    state = _state_with_conversation()
    service = Mock(spec=["active_session", "delete_session"])
    service.active_session.return_value = _session_info()
    session_id = uuid4()

    result = delete_session(session_id, service, state)

    assert result.ok is True
    assert result.payload is not None
    assert result.payload.removed_active_session is False
    assert state.messages[0].content == "old"


def test_delete_session_not_found_returns_error() -> None:
    state = _state_with_conversation()
    service = Mock(spec=["active_session", "delete_session"])
    service.active_session.return_value = _session_info()
    service.delete_session.side_effect = ServiceSessionNotFoundError

    result = delete_session(uuid4(), service, state)

    assert result.ok is False
    assert result.error == "Session not found"
    assert state.messages[0].content == "old"


class _ModelSettings:
    provider: str | None
    model: str | None
    thinking: ThinkingOptionId

    def __init__(
        self,
        provider: str | None,
        model: str | None,
        *,
        thinking: ThinkingOptionId = "none",
        fail_model_id: str | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.thinking = thinking
        self._fail_model_id = fail_model_id
        self.update_calls: list[dict[str, object]] = []

    def update(self, **changes: object) -> None:
        self.update_calls.append(changes)
        model = str(changes["model"])
        if self._fail_model_id is not None and model == self._fail_model_id:
            raise ValueError("invalid model")
        provider = changes["provider"]
        self.provider = None if provider is None else str(provider)
        self.model = model
        if "thinking" in changes:
            self.thinking = cast("ThinkingOptionId", changes["thinking"])


def test_select_model_success_updates_settings() -> None:
    settings = _ModelSettings(provider="openai", model="gpt-5")
    model = ModelDefinition(id="gpt-5.2", name="GPT 5.2", provider="openai")

    result = select_model(None, model, settings)

    assert result.ok is True
    assert settings.update_calls == [{"provider": "openai", "model": "gpt-5.2"}]
    assert settings.provider == "openai"
    assert settings.model == "gpt-5.2"


def test_select_model_clamps_unsupported_thinking_level() -> None:
    settings = _ModelSettings(
        provider="openai",
        model="gpt-5.4",
        thinking="xhigh",
    )
    current_model = ModelDefinition(
        id="gpt-5.4",
        name="GPT 5.4",
        provider="openai",
        thinking_options=[
            ThinkingOption(id="none", label="none"),
            ThinkingOption(id="minimal", label="minimal"),
            ThinkingOption(id="low", label="low"),
            ThinkingOption(id="medium", label="medium"),
            ThinkingOption(id="high", label="high"),
            ThinkingOption(id="xhigh", label="xhigh"),
        ],
    )
    model = ModelDefinition(
        id="gpt-5",
        name="GPT 5",
        provider="openai",
        thinking_options=[
            ThinkingOption(id="none", label="none"),
            ThinkingOption(id="low", label="low"),
            ThinkingOption(id="medium", label="medium"),
            ThinkingOption(id="high", label="high"),
        ],
    )

    result = select_model(current_model, model, settings)

    assert result.ok is True
    assert settings.update_calls == [
        {
            "provider": "openai",
            "model": "gpt-5",
            "thinking": "high",
        }
    ]
    assert settings.thinking == "high"


def test_select_model_resets_thinking_when_model_supports_none_only() -> None:
    settings = _ModelSettings(
        provider="openai",
        model="gpt-5.4",
        thinking="xhigh",
    )
    current_model = ModelDefinition(
        id="gpt-5.4",
        name="GPT 5.4",
        provider="openai",
        thinking_options=[
            ThinkingOption(id="none", label="none"),
            ThinkingOption(id="minimal", label="minimal"),
            ThinkingOption(id="low", label="low"),
            ThinkingOption(id="medium", label="medium"),
            ThinkingOption(id="high", label="high"),
            ThinkingOption(id="xhigh", label="xhigh"),
        ],
    )
    model = ModelDefinition(
        id="zai-org/GLM-4.7",
        name="GLM-4.7",
        provider="bergetai",
        thinking_options=[ThinkingOption(id="none", label="none")],
    )

    result = select_model(current_model, model, settings)

    assert result.ok is True
    assert settings.update_calls == [
        {
            "provider": "bergetai",
            "model": "zai-org/GLM-4.7",
            "thinking": "none",
        }
    ]
    assert settings.thinking == "none"


def test_select_model_invalid_rolls_back_settings() -> None:
    settings = _ModelSettings(
        provider="openai",
        model="gpt-5",
        fail_model_id="invalid-model",
    )
    model = ModelDefinition(id="invalid-model", name="Broken", provider="bergetai")

    result = select_model(None, model, settings)

    assert result.ok is False
    assert result.error == "Invalid model selection"
    assert settings.update_calls == [{"provider": "bergetai", "model": "invalid-model"}]
    assert settings.provider == "openai"
    assert settings.model == "gpt-5"


class _AppearanceSettings:
    def __init__(self, *, theme: str, show_scrollbar: bool, queue_inputs: bool) -> None:
        self.theme = theme
        self.show_scrollbar = show_scrollbar
        self.queue_inputs = queue_inputs
        self.set_calls: list[tuple[str, object]] = []

    def set(self, name: str, value: object) -> None:
        self.set_calls.append((name, value))
        setattr(self, name, value)


class _ThinkingSettings:
    thinking: ThinkingOptionId

    def __init__(self, thinking: ThinkingOptionId) -> None:
        self.thinking = thinking
        self.set_calls: list[tuple[str, object]] = []

    def set(self, name: str, value: object) -> None:
        self.set_calls.append((name, value))
        setattr(self, name, value)


def test_toggle_theme_switches_dark_to_light() -> None:
    settings = _AppearanceSettings(theme="dark", show_scrollbar=True, queue_inputs=True)

    result = toggle_theme(settings)

    assert result.ok is True
    assert settings.set_calls == [("theme", "light")]
    assert settings.theme == "light"


def test_toggle_scrollbar_flips_value() -> None:
    settings = _AppearanceSettings(theme="dark", show_scrollbar=True, queue_inputs=True)

    result = toggle_scrollbar(settings)

    assert result.ok is True
    assert settings.set_calls == [("show_scrollbar", False)]
    assert settings.show_scrollbar is False


def test_toggle_queue_inputs_flips_value() -> None:
    settings = _AppearanceSettings(theme="dark", show_scrollbar=True, queue_inputs=False)

    result = toggle_queue_inputs(settings)

    assert result.ok is True
    assert settings.set_calls == [("queue_inputs", True)]
    assert settings.queue_inputs is True


def test_set_thinking_updates_setting() -> None:
    settings = _ThinkingSettings("none")

    result = set_thinking("high", settings)

    assert result.ok is True
    assert settings.set_calls == [("thinking", "high")]
    assert settings.thinking == "high"


def test_cycle_thinking_advances_to_next_supported_level() -> None:
    settings = _ThinkingSettings("low")

    result = cycle_thinking(
        ["none", "low", "medium"],
        settings,
    )

    assert result.ok is True
    assert result.payload == "medium"
    assert settings.set_calls == [("thinking", "medium")]


class _ProviderSettings:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def set_api_key(self, provider: str, key: str) -> None:
        self.calls.append((provider, key))


def test_set_provider_api_key_delegates_to_settings() -> None:
    settings = _ProviderSettings()

    result = set_provider_api_key("openai", "secret", settings)

    assert result.ok is True
    assert settings.calls == [("openai", "secret")]
