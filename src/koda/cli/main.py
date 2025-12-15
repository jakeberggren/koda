import asyncio
import sys

import typer
from typer.main import Typer

from koda import core, observability
from koda.config import settings
from koda.providers import openai
from koda.utils import exceptions

app: Typer = typer.Typer(
    name="koda",
    help="Koda provider-agnostic agent framework CLI",
    add_completion=True,
)


def _create_provider(
    provider_name: str | None, model: str | None, settings: settings.Settings
) -> openai.OpenAIProvider:
    # Default to OpenAI if no provider specified
    provider_name = (provider_name or "openai").lower()

    if provider_name == "openai":
        api_key = settings.OPENAI_API_KEY.get_secret_value()
        provider_model = model or "gpt-5.1"
        return openai.OpenAIProvider(api_key=api_key, model=provider_model)
    else:
        typer.echo(f"Error: Provider '{provider_name}' is not supported yet.", err=True)
        typer.echo("Supported providers: openai", err=True)
        raise typer.Exit(1)


async def _run_chat_loop(agent: core.agent.Agent, stream: bool) -> None:
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
            except exceptions.ProviderRateLimitError as e:
                typer.echo(f"Error: Rate limit exceeded. {e}", err=True)
            except exceptions.ProviderAuthenticationError as e:
                typer.echo(f"Error: Authentication failed. {e}", err=True)
            except exceptions.ProviderAPIError as e:
                typer.echo(f"Error: API error occurred. {e}", err=True)
            except exceptions.ProviderError as e:
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
    typer.echo("Starting interactive chat session...")
    typer.echo("Type 'exit' or 'quit' to end the session.\n")

    app_settings = settings.get_settings()
    _observer: observability.LangfuseObserver = observability.create_observer(settings=app_settings)
    try:
        provider_instance = _create_provider(provider, model, app_settings)
        provider_name = (provider or "openai").lower()
        typer.echo(f"Using provider: {provider_name}")
        if model:
            typer.echo(f"Using model: {model}")
        if stream:
            typer.echo("Streaming mode enabled")
        typer.echo()

        agent = core.agent.Agent(provider=provider_instance)

        asyncio.run(_run_chat_loop(agent, stream))

    except exceptions.ProviderValidationError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e
    except Exception as e:
        typer.echo(f"Unexpected error: {e}", err=True)
        raise typer.Exit(1) from e


def main() -> None:
    app()


if __name__ == "__main__":
    main()
