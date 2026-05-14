from __future__ import annotations

from koda_service.types import ModelDefinition, ProviderDefinition, ThinkingOption
from koda_tui.ui.palette.command_palette import CommandPalette, PaletteOptions
from koda_tui.ui.palette.commands import model_commands, provider_commands, thinking_commands
from koda_tui.ui.palette.commands.command import Command, CommandStatus


def _provider(provider_id: str, name: str) -> ProviderDefinition:
    return ProviderDefinition(id=provider_id, name=name, description="")


def _model(model_id: str, provider: str, name: str) -> ModelDefinition:
    return ModelDefinition(
        id=model_id,
        provider=provider,
        name=name,
        description="",
        context_window=0,
        max_output_tokens=None,
    )


def _thinking(option_id: str, label: str) -> ThinkingOption:
    return ThinkingOption(id=option_id, label=label, description="")


def test_provider_commands_mark_connected_providers_connected() -> None:
    providers = [_provider("openai", "OpenAI"), _provider("anthropic", "Anthropic")]

    commands = provider_commands.get_commands(
        providers=providers,
        connected_provider_ids={"openai"},
        on_select=lambda _provider: None,
    )

    assert [cmd.status for cmd in commands] == [CommandStatus.CONNECTED, None]
    assert [cmd.label for cmd in commands] == ["OpenAI", "Anthropic"]


def test_model_commands_mark_active_model_current() -> None:
    providers = [_provider("openai", "OpenAI")]
    models = [
        _model("gpt-5", "openai", "GPT-5"),
        _model("gpt-4.1", "openai", "GPT-4.1"),
    ]

    commands = model_commands.get_commands(
        models=models,
        providers=providers,
        active_provider_id="openai",
        active_model_id="gpt-5",
        on_select=lambda _model: None,
    )

    assert [cmd.status for cmd in commands] == [CommandStatus.CURRENT, None]
    assert [cmd.label for cmd in commands] == ["GPT-5", "GPT-4.1"]


def test_thinking_commands_mark_active_option_current() -> None:
    options = [_thinking("low", "Low"), _thinking("high", "High")]

    commands = thinking_commands.get_commands(
        options=options,
        active_thinking="high",
        on_select=lambda _option_id: None,
    )

    assert [cmd.status for cmd in commands] == [None, CommandStatus.CURRENT]
    assert [cmd.label for cmd in commands] == ["Low", "High"]


def test_palette_renders_star_prefix_for_current_command() -> None:
    current = Command(label="OpenAI", handler=lambda: None, status=CommandStatus.CURRENT)
    other = Command(label="Anthropic", handler=lambda: None)
    palette = CommandPalette(
        commands=[current, other],
        on_close=lambda: None,
        invalidate=lambda: None,
        options=PaletteOptions(),
    )

    rows, _selected = palette.build_command_rows()
    item_rows = [row for row in rows if row.command is not None]

    current_fragments = item_rows[0].text
    other_fragments = item_rows[1].text

    assert current_fragments[0] == ("class:palette.selected", "* ")
    assert current_fragments[1][0] == "class:palette.selected"
    assert other_fragments[0] == ("class:palette.item", "  ")


def test_palette_renders_star_in_selection_column_for_current_unselected_command() -> None:
    first = Command(label="Anthropic", handler=lambda: None)
    current = Command(label="OpenAI", handler=lambda: None, status=CommandStatus.CURRENT)
    palette = CommandPalette(
        commands=[first, current],
        on_close=lambda: None,
        invalidate=lambda: None,
        options=PaletteOptions(),
    )
    palette.move_selection_clamped(-1)

    rows, _selected = palette.build_command_rows()
    item_rows = [row for row in rows if row.command is not None]
    current_fragments = item_rows[1].text

    assert current_fragments[0] == ("class:palette.marker", "* ")
    assert current_fragments[1][0] == "class:palette.current"
    assert current_fragments[1][1].startswith("OpenAI")


def test_palette_renders_connected_command_marker_without_current_label_style() -> None:
    first = Command(label="Anthropic", handler=lambda: None)
    connected = Command(label="OpenAI", handler=lambda: None, status=CommandStatus.CONNECTED)
    palette = CommandPalette(
        commands=[first, connected],
        on_close=lambda: None,
        invalidate=lambda: None,
        options=PaletteOptions(),
    )
    palette.move_selection_clamped(-1)

    rows, _selected = palette.build_command_rows()
    item_rows = [row for row in rows if row.command is not None]
    connected_fragments = item_rows[1].text

    assert connected_fragments[0] == ("class:palette.marker", "* ")
    assert connected_fragments[1][0] == "class:palette.item"
    assert connected_fragments[1][1].startswith("OpenAI")
