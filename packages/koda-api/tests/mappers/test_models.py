from koda.llm.models import ModelCapabilities, ThinkingOption
from koda.llm.models import ModelDefinition as CoreModelDefinition
from koda_api.mappers import map_model_definition_to_contract_model_definition


def test_map_model_definition_to_contract_model_definition() -> None:
    core_model = CoreModelDefinition(
        id="gpt-5.2",
        name="GPT 5.2",
        provider="openai",
        thinking_options=[
            ThinkingOption(
                id="high",
                label="High",
                description="High effort for complex tasks.",
            )
        ],
        capabilities={ModelCapabilities.WEB_SEARCH},
    )

    mapped = map_model_definition_to_contract_model_definition(core_model)

    assert mapped.id == "gpt-5.2"
    assert mapped.name == "GPT 5.2"
    assert mapped.provider == "openai"
    assert [
        (option.id, option.label, option.description) for option in mapped.thinking_options
    ] == [("high", "High", "High effort for complex tasks.")]
    assert {capability.value for capability in mapped.capabilities} == {"web_search"}
