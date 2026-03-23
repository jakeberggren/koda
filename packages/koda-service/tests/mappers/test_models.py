from koda.llm.models import ModelDefinition as CoreModelDefinition
from koda.llm.models import ThinkingOption as CoreThinkingOption
from koda_service.mappers import map_model_definition_to_contract_model_definition


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
            context_window=200_000,
            max_output_tokens=8_000,
            model_features={
                "web_search": True,
                "extended_prompt_retention": True,
            },
        )
    )

    assert contract_model.id == "openai/gpt-5"
    assert contract_model.name == "GPT-5"
    assert contract_model.provider == "openai"
    assert contract_model.context_window == 200_000  # noqa: PLR2004
    assert contract_model.max_output_tokens == 8_000  # noqa: PLR2004
    assert contract_model.thinking_options[0].id == "high"
    assert contract_model.thinking_options[0].label == "High"
    assert contract_model.thinking_options[0].description == "Longer reasoning"
    assert contract_model.model_features == {
        "web_search": True,
        "extended_prompt_retention": True,
    }
