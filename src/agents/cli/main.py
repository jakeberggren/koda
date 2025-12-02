"""CLI interface for the agents framework."""

import asyncio
import sys

import typer

from agents.config.settings import Settings
from agents.core import Agent
from agents.providers.openai import OpenAIProvider
from agents.utils.exceptions import (
    ProviderAPIError,
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderValidationError,
)

app = typer.Typer(
    name="agents",
    help="Provider-agnostic agent framework CLI",
    add_completion=True,
)


def _create_provider(provider_name: str | None, model: str | None) -> OpenAIProvider:  # type: ignore[return-value]
    """Create a provider instance based on the provider name.

    Args:
        provider_name: Name of the provider (e.g., "openai").
        model: Model to use (provider-specific).

    Returns:
        A provider instance.

    Raises:
        typer.Exit: If provider is not supported or configuration is invalid.
    """
    settings = Settings()

    # Default to OpenAI if no provider specified
    provider_name = (provider_name or "openai").lower()

    if provider_name == "openai":
        api_key = settings.OPENAI_API_KEY.get_secret_value()
        provider_model = model or "gpt-5.1"
        return OpenAIProvider(api_key=api_key, model=provider_model)
    else:
        typer.echo(f"Error: Provider '{provider_name}' is not supported yet.", err=True)
        typer.echo("Supported providers: openai", err=True)
        raise typer.Exit(1)


async def _run_chat_loop(agent: Agent, stream: bool) -> None:
    """Run the interactive chat loop.

    Args:
        agent: The agent instance to use.
        stream: Whether to stream responses.
    """
    while True:
        try:
            user_input = typer.prompt("You")
            if user_input.lower() in ("exit", "quit", "q"):
                typer.echo("Goodbye!")
                break

            if not user_input.strip():
                continue

            try:
                typer.echo()  # Newline
                if stream:
                    typer.echo("Assistant: ", nl=False)
                    async for chunk in agent.stream(user_input):
                        typer.echo(chunk, nl=False)
                    typer.echo()  # Newline
                else:
                    response = await agent.chat(user_input)
                    typer.echo(f"Assistant: {response}")
                    typer.echo()  # Newline
            except ProviderRateLimitError as e:
                typer.echo(f"Error: Rate limit exceeded. {e}", err=True)
            except ProviderAuthenticationError as e:
                typer.echo(f"Error: Authentication failed. {e}", err=True)
            except ProviderAPIError as e:
                typer.echo(f"Error: API error occurred. {e}", err=True)
            except ProviderError as e:
                typer.echo(f"Error: {e}", err=True)

        except (EOFError, KeyboardInterrupt):
            typer.echo("\nGoodbye!")
            sys.exit(0)


@app.command()
def chat(
    stream: bool = typer.Option(False, "--stream", "-s", help="Stream the response in real-time"),
    provider: str | None = typer.Option(
        None, "--provider", "-p", help="Provider to use (e.g., openai, anthropic)"
    ),
    model: str | None = typer.Option(
        None, "--model", "-m", help="Model to use (provider-specific)"
    ),
) -> None:
    """Start an interactive chat session with the agent."""
    typer.echo("Starting interactive chat session...")
    typer.echo("Type 'exit' or 'quit' to end the session.\n")

    try:
        # Create provider
        provider_instance = _create_provider(provider, model)

        # Display configuration
        provider_name = (provider or "openai").lower()
        typer.echo(f"Using provider: {provider_name}")
        if model:
            typer.echo(f"Using model: {model}")
        if stream:
            typer.echo("Streaming mode enabled")
        typer.echo()

        # Create agent
        agent = Agent(provider=provider_instance)

        # Run async chat loop
        asyncio.run(_run_chat_loop(agent, stream))

    except ProviderValidationError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e
    except Exception as e:
        typer.echo(f"Unexpected error: {e}", err=True)
        raise typer.Exit(1) from e


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
