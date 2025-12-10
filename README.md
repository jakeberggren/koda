# KODA

## Installation

Install the package in development mode:

```bash
uv pip install -e .
```

## CLI Usage

The framework provides a basic CLI tool for testing and interacting with agents.

### Basic Commands

#### Interactive Chat Session

Start an interactive chat session (default mode):

```bash
koda chat
```

With provider and model options:

```bash
koda chat --provider openai --model gpt-5.1
koda chat -p anthropic -m claude-opus-4-5
```

#### Streaming Responses

Enable streaming mode in the interactive session:

```bash
koda chat --stream
```

Or use the short flag:

```bash
koda chat -s
```

With provider and model options:

```bash
koda chat --stream --provider openai --model gpt-4
koda chat -s -p anthropic -m claude-3-opus
```

Type `exit`, `quit`, or `q` to end the session.

### Help

Get help for any command:

```bash
koda --help
koda chat --help
```

## Development

### Setup

1. Install dependencies:

```bash
uv sync
```

2. Install pre-commit hooks:

```bash
pre-commit install
```

## Project Structure

```
src/koda/
├── cli/              # CLI interface (Typer)
├── config/           # Configuration (BaseSettings)
├── core/             # Core abstractions (Agent, Message, etc.)
├── observability/    # Observability protocols and platform implementations
├── providers/        # Provider implementations
├── tools/            # Built-in tools
└── utils/            # Utilities
```

## Environment Variables

Create a `.env` file with your API keys:

```env
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
```
