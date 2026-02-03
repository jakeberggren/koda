<div align="center">
<pre>
╔═══════════════════════════════════════╗
║   ██╗  ██╗ ██████╗ ██████╗  █████╗    ║
║   ██║ ██╔╝██╔═══██╗██╔══██╗██╔══██╗   ║
║   █████╔╝ ██║   ██║██║  ██║███████║   ║
║   ██╔═██╗ ██║   ██║██║  ██║██╔══██║   ║
║   ██║  ██╗╚██████╔╝██████╔╝██║  ██║   ║
║   ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝   ║
╚═══════════════════════════════════════╝
</pre>
</div>

Lightweight terminal coding assistant that can navigate, understand, and modify codebases.

## Usage

Start an interactive chat session (default mode):

```bash
koda
```

Press Ctrl+C twice to exit the session.

## Project Structure

Koda is a monorepo workspace managed by uv, containing three main packages:

- **koda**: Provider-agnostic core library that handles agent logic, tool execution, and LLM provider integration
- **koda-tui**: Interactive terminal interface
- **koda-common**: Shared utilities including settings, logging, and database configuration

```
packages/
├── koda/                        # Core agent framework
│   ├── src/koda/
│   │   ├── agents/              # Agent orchestration
│   │   ├── messages/            # Message types and handling
│   │   ├── providers/           # LLM provider adapters (OpenAI, Anthropic)
│   │   └── tools/               # Agent tools (filesystem operations, etc.)
│   └── tests/
│
├── koda-tui/                    # Terminal user interface
│   ├── src/koda_tui/
│   │   ├── app/                 # TUI application entry + orchestration
│   │   ├── clients/             # Client implementations (local, mock, etc.)
│   │   ├── components/          # UI components/widgets
│   │   └── rendering/           # Rich Rendering layer
│   └── tests/
│
└── koda-common/                 # Shared utilities
    ├── src/koda_common/
    │   ├── db/                  # Database configuration + engine helpers
    │   ├── logging/             # Logging configuration
    │   └── settings/            # Settings management (store, manager)
    └── tests/
```

## Development Setup

KODA uses [Astral's](https://astral.sh/) Python toolchain:

- **uv** — Package and workspace management
- **ruff** — Linting and formatting
- **ty** — Type checking

### Prerequisites

Install uv: https://docs.astral.sh/uv/getting-started/installation/

### Getting Started

```bash
# Install dependencies and set up the workspace
uv sync

# Install pre-commit hooks
pre-commit install
```

Pre-commit hooks run ruff formatting and linting, and ty type checking automatically on each commit.
Pre-push hooks also runs tests for modified packages and additional security checks.
