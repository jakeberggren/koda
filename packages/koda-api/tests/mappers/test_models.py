from koda.providers.registry import ModelCapabilities, ThinkingLevel
from koda.providers.registry import ModelDefinition as CoreModelDefinition
from koda_api.mappers import map_model_definition_to_contract_model_definition


def test_map_model_definition_to_contract_model_definition() -> None:
    core_model = CoreModelDefinition(
        id="gpt-5.2",
        name="GPT 5.2",
        provider="openai",
        thinking={ThinkingLevel.HIGH},
        capabilities={ModelCapabilities.WEB_SEARCH},
    )

    mapped = map_model_definition_to_contract_model_definition(core_model)

    assert mapped.id == "gpt-5.2"
    assert mapped.name == "GPT 5.2"
    assert mapped.provider == "openai"
    assert {level.value for level in mapped.thinking} == {"high"}
    assert {capability.value for capability in mapped.capabilities} == {"web_search"}
