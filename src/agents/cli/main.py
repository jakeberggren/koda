import asyncio
import sys

import typer
from typer.main import Typer

from agents.config.settings import Settings
from agents.core import Agent
from agents.observability import Observability
from agents.observability.platforms.braintrust import BraintrustObservability
from agents.observability.platforms.langfuse import LangfuseObservability
from agents.observability.platforms.noop import NoOpObservability
from agents.providers.openai import OpenAIProvider
from agents.utils.exceptions import (
    ProviderAPIError,
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderValidationError,
)

app: Typer = typer.Typer(
    name="agents",
    help="Provider-agnostic agent framework CLI",
    add_completion=True,
)


def _create_provider(
    provider_name: str | None, model: str | None, observer: Observability | None
) -> OpenAIProvider:
    settings = Settings()

    # Default to OpenAI if no provider specified
    provider_name = (provider_name or "openai").lower()

    if provider_name == "openai":
        api_key = settings.OPENAI_API_KEY.get_secret_value()
        provider_model = model or "gpt-5.1"
        return OpenAIProvider(api_key=api_key, model=provider_model, observability=observer)
    else:
        typer.echo(f"Error: Provider '{provider_name}' is not supported yet.", err=True)
        typer.echo("Supported providers: openai", err=True)
        raise typer.Exit(1)


def _create_observer(backend: str | None) -> Observability:
    settings = Settings()

    # If no backend specified, use no-op observer
    if not backend:
        return NoOpObservability()

    backend = backend.lower()

    if backend == "langfuse":
        # Get Langfuse credentials from settings
        public_key = settings.LANGFUSE_PUBLIC_KEY
        secret_key = settings.LANGFUSE_SECRET_KEY
        host = settings.LANGFUSE_BASE_URL

        if not public_key or not secret_key:
            typer.echo(
                "Error: Langfuse requires LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY environment variables.",  # noqa: E501
                err=True,
            )
            raise typer.Exit(1)

        return LangfuseObservability(
            public_key=public_key,
            secret_key=secret_key.get_secret_value(),
            host=str(host),
        )

    elif backend == "braintrust":
        # Get Braintrust credentials from settings
        api_key = getattr(settings, "BRAINTRUST_API_KEY", None)
        project_name = getattr(settings, "BRAINTRUST_PROJECT_NAME", None)

        if not api_key:
            typer.echo(
                "Error: Braintrust requires BRAINTRUST_API_KEY environment variable.",
                err=True,
            )
            raise typer.Exit(1)

        return BraintrustObservability(
            api_key=api_key,
            project_name=project_name,
        )

    else:
        typer.echo(f"Error: Observability backend '{backend}' is not supported.", err=True)
        typer.echo("Supported backends: langfuse, braintrust", err=True)
        raise typer.Exit(1)


async def _run_chat_loop(agent: Agent, stream: bool) -> None:
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
    observability: str | None = typer.Option(
        None, "--observability", "-o", help="Observability backend (e.g., langfuse, braintrust)"
    ),
) -> None:
    typer.echo("Starting interactive chat session...")
    typer.echo("Type 'exit' or 'quit' to end the session.\n")

    try:
        # Create provider
        observer = _create_observer(backend=observability)
        provider_instance = _create_provider(provider, model, observer)

        # Display configuration
        provider_name = (provider or "openai").lower()
        typer.echo(f"Using provider: {provider_name}")
        if model:
            typer.echo(f"Using model: {model}")
        if stream:
            typer.echo("Streaming mode enabled")
        if observability:
            typer.echo(f"Observability: {observability}")
        typer.echo()

        # Create agent
        agent = Agent(provider=provider_instance, observability=observer)

        # Run async chat loop
        asyncio.run(_run_chat_loop(agent, stream))

    except ProviderValidationError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e
    except Exception as e:
        typer.echo(f"Unexpected error: {e}", err=True)
        raise typer.Exit(1) from e


def main() -> None:
    app()


if __name__ == "__main__":
    main()
