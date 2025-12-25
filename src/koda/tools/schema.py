from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ParameterProperty(BaseModel):
    """A single parameter property in a tool schema."""

    type: Literal["string", "number", "integer", "boolean", "array", "object"]
    description: str | None = None
    enum: list[Any] | None = None
    default: Any = None
    # For nested objects
    properties: dict[str, ParameterProperty] | None = None
    required: list[str] | None = None
    # For arrays
    items: ParameterProperty | None = None

    @classmethod
    def from_json_schema(cls, schema: dict[str, Any]) -> ParameterProperty:
        """Convert a JSON schema property to ParameterProperty."""
        prop_type = schema.get("type", "string")
        description = schema.get("description")
        enum = schema.get("enum")
        default = schema.get("default")

        # Handle nested objects
        properties = None
        required = None
        if prop_type == "object" and "properties" in schema:
            properties = {
                k: ParameterProperty.from_json_schema(v) for k, v in schema["properties"].items()
            }
            required = schema.get("required", [])

        # Handle arrays
        items = None
        if prop_type == "array" and "items" in schema:
            items = ParameterProperty.from_json_schema(schema["items"])

        return cls(
            type=prop_type,
            description=description,
            enum=enum,
            default=default,
            properties=properties,
            required=required,
            items=items,
        )


class ToolSchema(BaseModel):
    """Provider-agnostic tool schema representation."""

    type: Literal["object"] = "object"
    properties: dict[str, ParameterProperty]
    required: list[str] = Field(default_factory=list)
    additional_properties: bool = False

    @classmethod
    def from_pydantic_schema(cls, schema: dict[str, Any]) -> ToolSchema:
        """Convert Pydantic JSON schema to structured ToolSchema."""
        properties = {}
        required = schema.get("required", [])

        if "properties" in schema:
            for prop_name, prop_schema in schema["properties"].items():
                properties[prop_name] = ParameterProperty.from_json_schema(prop_schema)

        return cls(
            properties=properties,
            required=required,
            additional_properties=False,
        )
