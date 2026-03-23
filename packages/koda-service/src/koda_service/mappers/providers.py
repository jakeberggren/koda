from koda.llm.models import ProviderDefinition as CoreProviderDefinition
from koda_service.types.models import ProviderDefinition


def map_provider_definition_to_contract_provider_definition(
    core_provider: CoreProviderDefinition,
) -> ProviderDefinition:
    """Map core provider definition to contract provider definition."""
    return ProviderDefinition(
        id=core_provider.id,
        name=core_provider.name,
        provider_features=core_provider.provider_features,
    )
