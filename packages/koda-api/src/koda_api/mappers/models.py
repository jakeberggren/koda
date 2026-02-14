from koda.providers.registry import ModelDefinition as CoreModelDefinition
from koda_common.contracts import ModelCapability, ModelDefinition, ThinkingLevel


def map_model_definition_to_contract_model_definition(
    core_model: CoreModelDefinition,
) -> ModelDefinition:
    """Map core model definition to contract model definition."""
    return ModelDefinition(
        id=core_model.id,
        name=core_model.name,
        provider=core_model.provider,
        thinking={ThinkingLevel(level.value) for level in core_model.thinking},
        capabilities={ModelCapability(capability.value) for capability in core_model.capabilities},
    )
