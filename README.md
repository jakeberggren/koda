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

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/jakeberggren/koda/main/install.sh | bash
```

## Uninstall

```bash
rm -f ~/.local/bin/koda
rm -rf ~/.local/share/koda
```

## Usage

Start an interactive chat session:

```bash
koda
```

Press Ctrl+C twice to exit the session.

## Command Execution

Koda's built-in `bash` tool runs in `host` mode by default. It also supports:

- `docker` for short-lived containerized execution
- `seatbelt` for macOS `sandbox-exec` execution

Example configuration:

```bash
# Host execution (default)
export KODA_BASH_EXECUTION_SANDBOX=host

# Docker execution
export KODA_BASH_EXECUTION_SANDBOX=docker
export KODA_BASH_EXECUTION_DOCKER_IMAGE=my-koda-bash:latest

# macOS seatbelt execution
export KODA_BASH_EXECUTION_SANDBOX=seatbelt
```

Koda does not bundle a standard Docker image. If you want Docker-backed
execution, provide an image that includes `bash` and the tools you want available
inside the sandbox.

In short:

- `host` is fully trusted local execution
- `docker` adds useful isolation but is not a hardened security boundary
- `seatbelt` adds useful macOS restrictions, including blocked network access and
  write access limited to the workspace plus per-run temporary storage

More execution details live in
[`packages/koda/src/koda/execution/README.md`](packages/koda/src/koda/execution/README.md).

## Project Structure

Koda is a uv-managed monorepo with four workspace packages:

- **koda** — Core agent/runtime library: agent loop, LLM abstractions, sessions, telemetry, and tools
- **koda-service** — Service boundary and in-process runtime used by clients
- **koda-tui** — Interactive terminal UI built on top of the service layer
- **koda-common** — Shared settings, logging, and path utilities

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
│   │   ├── protocols.py         # Public KodaService protocol
│   │   ├── exceptions.py        # Service/runtime and startup-style errors
│   │   ├── mappers/             # Core -> service DTO mapping
│   │   ├── services/            # In-process service implementation
│   │   └── types/               # Service-boundary DTOs
│   └── tests/
│
├── koda-tui/                    # Terminal user interface
│   ├── src/koda_tui/
│   │   ├── __init__.py          # CLI entrypoint and app bootstrap
│   │   ├── agent.py             # TUI-specific agent builder and tool wiring
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
    │   ├── logging/             # Logging configuration
    │   ├── settings/            # Settings management + secret storage
    │   └── paths.py             # Shared filesystem paths
    └── tests/
```

## Development Setup

Koda uses [Astral's](https://astral.sh/) Python toolchain:

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
