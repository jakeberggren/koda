import asyncio
import random
import sys

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from typer.main import Typer

from koda import core, observability
from koda.config import settings
from koda.providers import TextDelta, openai
from koda.tools import filesystem, registry
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
        provider_model = model or settings.KODA_DEFAULT_MODEL
        return openai.OpenAIProvider(api_key=api_key, model=provider_model)
    else:
        typer.echo(f"Error: Provider '{provider_name}' is not supported yet.", err=True)
        typer.echo("Supported providers: openai", err=True)
        raise typer.Exit(1)


def _get_random_thinking_message() -> str:
    return random.choice(  # noqa: S311
        [
            "Koda is up to something good...",
            "Koda is in the zone...",
            "Koda is getting the job done...",
            "Koda is hard at work...",
            "Koda is on it...",
            "Koda is plotting next move...",
            "Koda is deep in the weeds...",
        ]
    )


async def _run_chat_loop(agent: core.agent.Agent) -> None:
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
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    transient=True,
                ) as progress:
                    progress.add_task(_get_random_thinking_message())
                    stream_iter = agent.run(user_input)
                    first_chunk = await anext(stream_iter)  # Show spinner until first chunk.
                typer.echo("Koda: ", nl=False)
                if isinstance(first_chunk, TextDelta):
                    typer.echo(first_chunk.text, nl=False)
                async for chunk in stream_iter:
                    if isinstance(chunk, TextDelta):
                        typer.echo(chunk.text, nl=False)
                typer.echo("\n")
            except exceptions.ProviderRateLimitError as e:
                typer.echo(f"Error: Rate limit exceeded. {e}", err=True)
            except exceptions.ProviderAuthenticationError as e:
                typer.echo(f"Error: Authentication failed. {e}", err=True)
            except exceptions.ProviderAPIError as e:
                typer.echo(f"Error: API error occurred. {e}", err=True)
            except exceptions.ProviderError as e:
                typer.echo(f"Error: {e}", err=True)
            except exceptions.ToolError as e:
                typer.echo(f"Error: {e}", err=True)

        except (EOFError, KeyboardInterrupt):
            typer.echo("\nGoodbye!")
            sys.exit(0)


@app.command()
def run(
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
        provider = provider or app_settings.KODA_DEFAULT_PROVIDER
        model = model or app_settings.KODA_DEFAULT_MODEL
        provider_instance = _create_provider(provider, model, app_settings)

        typer.echo(f"Using provider: {provider}")
        typer.echo(f"Using model: {model}")
        typer.echo()

        # Create tool registry and register tools
        tool_registry = registry.ToolRegistry()
        tool_registry.register(filesystem.ReadFileTool())
        tool_registry.register(filesystem.WriteFileTool())
        tool_registry.register(filesystem.ListDirectoryTool())
        tool_registry.register(filesystem.FileExistsTool())

        # Create agent with system message explaining available tools
        system_message = (
            "You are Koda, an AI coding assistant. You have access to the following tools:\n\n"
            "1. read_file - Read the contents of a file from the filesystem\n"
            "2. write_file - Write content to a file on the filesystem\n"
            "3. list_directory - List the contents of a directory\n"
            "4. file_exists - Check if a file or directory exists\n\n"
            "Use these tools when the user asks you to read, write, list, or check files. "
            "Always use the appropriate tool to accomplish file-related tasks."
        )

        agent = core.agent.Agent(
            provider=provider_instance,
            tool_registry=tool_registry,
            system_message=system_message,
        )

        asyncio.run(_run_chat_loop(agent))

    except exceptions.ProviderValidationError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e


def main() -> None:
    app()


if __name__ == "__main__":
    main()
