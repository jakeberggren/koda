from __future__ import annotations

from koda_service.types import ModelDefinition, ThinkingOption, ThinkingOptionId

_DEFAULT_THINKING_OPTION = ThinkingOption(id="none", label="none")


def find_model(
    models: list[ModelDefinition],
    *,
    provider: str,
    model_id: str,
) -> ModelDefinition | None:
    return next(
        (model for model in models if model.provider == provider and model.id == model_id),
        None,
    )


def supports_thinking(model: ModelDefinition | None) -> bool:
    if model is None:
        return False
    return any(option.id != "none" for option in model.thinking_options)


def supported_thinking_options(model: ModelDefinition | None) -> list[ThinkingOption]:
    if model is None or not model.thinking_options:
        return [_DEFAULT_THINKING_OPTION]
    return model.thinking_options


def normalize_thinking_option(
    current: ThinkingOptionId,
    *,
    current_options: list[ThinkingOption],
    new_options: list[ThinkingOption],
) -> ThinkingOptionId:
    new_ids = [option.id for option in supported_thinking_options_from_list(new_options)]
    if current in new_ids:
        return current

    current_ids = [option.id for option in supported_thinking_options_from_list(current_options)]
    try:
        current_index = current_ids.index(current)
    except ValueError:
        return new_ids[0]

    return new_ids[min(current_index, len(new_ids) - 1)]


def supported_thinking_options_from_list(
    options: list[ThinkingOption],
) -> list[ThinkingOption]:
    if not options:
        return [_DEFAULT_THINKING_OPTION]
    return options


def resolve_thinking_option(
    model: ModelDefinition | None,
    thinking_id: ThinkingOptionId,
) -> ThinkingOption:
    options = supported_thinking_options(model)
    return next((option for option in options if option.id == thinking_id), options[0])
