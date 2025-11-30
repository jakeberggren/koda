"""CLI interface for the agents framework."""

import sys

import typer

app = typer.Typer(
    name="agents",
    help="Provider-agnostic agent framework CLI",
    add_completion=True,
)


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

    if provider:
        typer.echo(f"Using provider: {provider}")
    if model:
        typer.echo(f"Using model: {model}")
    if stream:
        typer.echo("Streaming mode enabled")
    typer.echo()

    # TODO: Implement actual interactive agent chat
    # from agents.core.agent import Agent
    # agent = Agent(provider=provider, model=model)

    while True:
        try:
            user_input = typer.prompt("You")
            if user_input.lower() in ("exit", "quit", "q"):
                typer.echo("Goodbye!")
                break

            if not user_input.strip():
                continue

            # TODO: Get response from agent
            # if stream:
            #     typer.echo("Assistant: ", nl=False)
            #     for chunk in agent.stream(user_input):
            #         typer.echo(chunk, nl=False)
            #     typer.echo("\n")
            # else:
            #     response = agent.chat(user_input)
            #     typer.echo(f"Assistant: {response}\n")
            typer.echo(f"Assistant: [Response to: {user_input}]\n")

        except (EOFError, KeyboardInterrupt):
            typer.echo("\nGoodbye!")
            sys.exit(0)


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
