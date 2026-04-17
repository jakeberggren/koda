def provider_api_key_env_var(provider: str) -> str:
    """Return the conventional environment variable name for a provider API key."""

    return f"{provider.strip().upper()}_API_KEY"
