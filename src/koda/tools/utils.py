from typing import Any

from pydantic import BaseModel


def pydantic_model_to_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Convert a Pydantic model to JSON Schema format."""
    return model.model_json_schema()
