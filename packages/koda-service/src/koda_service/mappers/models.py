from koda.llm.models import ModelDefinition as CoreModelDefinition
from koda_service.types.models import ModelDefinition, ThinkingOption


def map_model_definition_to_contract_model_definition(
    core_model: CoreModelDefinition,
) -> ModelDefinition:
    """Map core model definition to contract model definition."""
    return ModelDefinition(
        id=core_model.id,
        name=core_model.name,
        provider=core_model.provider,
        context_window=core_model.context_window,
        max_output_tokens=core_model.max_output_tokens,
        thinking_options=[
            ThinkingOption(
                id=option.id,
                label=option.label,
                description=option.description,
            )
            for option in core_model.thinking_options
        ],
        model_features=core_model.model_features,
    )
