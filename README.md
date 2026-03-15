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

Start an interactive chat session:

```bash
koda
```

Press Ctrl+C twice to exit the session.

## Project Structure

Koda is a uv-managed monorepo with four workspace packages:

- **koda** — Core agent/runtime library: agent loop, LLM abstractions, sessions, telemetry, and tools
- **koda-service** — Service boundary and startup/runtime orchestration used by clients
- **koda-tui** — Interactive terminal UI built on top of the service layer
- **koda-common** — Shared settings, logging, and database utilities

```text
packages/
├── koda/                        # Core agent and runtime primitives
│   ├── src/koda/
│   │   ├── agents/              # Agent loop orchestration
│   │   ├── llm/                 # Provider adapters, registries, request/response types
│   │   ├── messages/            # Internal conversation message models
│   │   ├── sessions/            # Session management and persistence
│   │   ├── telemetry/           # Langfuse integration
│   │   └── tools/               # Tool framework + built-in filesystem tools
│   └── tests/
│
├── koda-service/                # Service boundary used by clients
│   ├── src/koda_service/
│   │   ├── bootstrap.py         # Runtime and registry assembly helpers
│   │   ├── protocols.py         # Public KodaService protocol
│   │   ├── startup.py           # Startup context creation
│   │   ├── mappers/             # Core -> service DTO mapping
│   │   ├── services/            # In-process service implementation
│   │   └── types/               # Service-boundary DTOs
│   └── tests/
│
├── koda-tui/                    # Terminal user interface
│   ├── src/koda_tui/
│   │   ├── app/                 # Application loop, streaming, output coordination
│   │   ├── components/          # UI widgets and panes
│   │   ├── rendering/           # Rich rendering helpers
│   │   ├── ui/                  # Layout, styles, and command palette UI
│   │   ├── actions.py           # TUI actions backed by the service layer
│   │   ├── converters.py        # Service -> TUI message conversion
│   │   └── state.py             # Shared application state
│   └── tests/
│
└── koda-common/                 # Shared utilities
    ├── src/koda_common/
    │   ├── db/                  # Database configuration + engine helpers
    │   ├── logging/             # Logging configuration
    │   └── settings/            # Settings management + secret storage
    └── tests/
```

## Development Setup

KODA uses [Astral's](https://astral.sh/) Python toolchain:

- **uv** — package and workspace management
- **ruff** — linting and formatting
- **ty** — type checking

### Prerequisites

Install uv from the [Astral docs](https://docs.astral.sh/uv/getting-started/installation/).

### Getting Started

```bash
# Install dependencies and set up the workspace
uv sync

# Install git hooks
pre-commit install
```

Pre-commit hooks run Ruff and Ty checks automatically.
Pre-push hooks run package tests plus additional security scanning.
