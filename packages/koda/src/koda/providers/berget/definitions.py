from koda.providers.registry import ModelDefinition

MODELS: list[ModelDefinition] = [
    ModelDefinition(
        id="meta-llama/Llama-3.1-8B-Instruct",
        name="Llama-3.1-8B-Instruct",
        provider="bergetai",
    ),
    ModelDefinition(
        id="meta-llama/Llama-3.3-70B-Instruct",
        name="Llama-3.3-70B-Instruct",
        provider="bergetai",
    ),
    ModelDefinition(
        id="openai/gpt-oss-120b",
        name="gpt-oss-120b",
        provider="bergetai",
    ),
    ModelDefinition(
        id="zai-org/GLM-4.7",
        name="GLM-4.7",
        provider="bergetai",
    ),
    ModelDefinition(
        id="mistralai/Mistral-Small-3.2-24B-Instruct-2506",
        name="Mistral-Small-3.2-24B-Instruct-2506",
        provider="bergetai",
    ),
]
