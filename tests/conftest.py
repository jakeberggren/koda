"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from koda.providers import adapter as provider_adapter
from koda.providers.openai import adapter as openai_adapter
from koda.tools import base as tools_base


class MockToolParams(BaseModel):
    """Simple parameters model for testing."""

    query: str
    limit: int = 10


@pytest.fixture
def sample_tool_definition() -> tools_base.ToolDefinition:
    """A minimal tool definition for contract tests."""
    return tools_base.ToolDefinition(
        name="search",
        description="Search for information",
        parameters_model=MockToolParams,
    )


@pytest.fixture(params=["openai"])  # Add "anthropic" when implemented
def adapter(request: pytest.FixtureRequest) -> provider_adapter.ProviderAdapter:
    """Parametrized fixture providing all adapter implementations."""
    adapters: dict[str, provider_adapter.ProviderAdapter] = {
        "openai": openai_adapter.OpenAIAdapter(),
        # "anthropic": AnthropicAdapter(),
    }
    return adapters[request.param]
