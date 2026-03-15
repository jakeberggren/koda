from koda.llm.models import ModelCapabilities
from koda.llm.models import ModelDefinition as CoreModelDefinition
from koda.llm.models import ThinkingOption as CoreThinkingOption
from koda_service.mappers import map_model_definition_to_contract_model_definition
from koda_service.types import ModelCapability


def test_map_model_definition_to_contract_model_definition() -> None:
    contract_model = map_model_definition_to_contract_model_definition(
        CoreModelDefinition(
            id="openai/gpt-5",
            name="GPT-5",
            provider="openai",
            thinking_options=[
                CoreThinkingOption(
                    id="high",
                    label="High",
                    description="Longer reasoning",
                )
            ],
            capabilities={
                ModelCapabilities.WEB_SEARCH,
                ModelCapabilities.EXTENDED_PROMPT_RETENTION,
            },
        )
    )

    assert contract_model.id == "openai/gpt-5"
    assert contract_model.name == "GPT-5"
    assert contract_model.provider == "openai"
    assert contract_model.thinking_options[0].id == "high"
    assert contract_model.thinking_options[0].label == "High"
    assert contract_model.thinking_options[0].description == "Longer reasoning"
    assert contract_model.capabilities == {
        ModelCapability.WEB_SEARCH,
        ModelCapability.EXTENDED_PROMPT_RETENTION,
    }
