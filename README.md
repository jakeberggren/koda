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

Koda is a minimal coding assistant that can navigate, understand, and modify codebases.
Koda currently runs through `koda-tui`, a purpose-built prompt-toolkit TUI built on top of Koda's
service layer and core agent runtime.

## Installation and Usage

To install Koda locally, run the install script:

```bash
curl -fsSL https://raw.githubusercontent.com/jakeberggren/koda/main/install.sh | bash
```

Then, start an interactive chat session:

```bash
koda
```

Koda prompts for provider credentials on first launch.

Koda can also run as a Docker Sandboxes agent kit. The kit installs Koda inside
an isolated microVM-based sandbox and launches it with Docker Sandboxes-managed
credentials and network policy. The current kit uses OpenAI as the default provider.

```bash
sbx secret set -g openai
sbx run --kit "git+https://github.com/jakeberggren/koda.git#ref=main&dir=kit/koda" koda
```

This requires Docker Sandboxes, an early-access feature from Docker.
For setup details, see the [Docker Sandboxes documentation](https://docs.docker.com/ai/sandboxes/).

## Models and Providers

Koda ships with a bundled `models.json` model catalog, which defines
available providers, provider API compatibility, base URLs, model IDs, context
windows, output limits, capabilities, and thinking modes.

To add custom providers or to override a built-in provider, use
`~/.koda/models.json`. Provider and model IDs are matched case-insensitively, and
user-defined entries take precedence when they use the same IDs as built-in
entries.

Example `~/.koda/models.json` adding OpenRouter as a provider:

```json
{
  "providers": {
    "openrouter": {
      "name": "OpenRouter",
      "description": "Unified Interface with access to all major LLMs",
      "api": "openai-completions",
      "base_url": "https://openrouter.ai/api/v1",
      "models": [
        {
          "id": "moonshotai/kimi-k2.6",
          "name": "Kimi K2.6",
          "context_window": 256000,
          "max_output_tokens": 32000
        }
      ]
    }
  }
}
```

The `api` field must be one of Koda's supported provider adapters:
`openai-responses`, `openai-completions`, or `anthropic-messages`. Configure
credentials through the TUI provider setup flow or with the provider-specific
environment variable, such as `OPENROUTER_API_KEY` for the example above.

## Agent

Koda runs with a small set of built-in tools for reading, searching, editing, and
executing commands in the current workspace. File-oriented tools are scoped to the
workspace and respect `.gitignore` patterns.

| Tool | Purpose |
| ---- | ------- |
| `read_file` | Read file contents with line-based offsets and limits |
| `write_file` | Create new files |
| `edit_file` | Apply focused text replacements to existing files |
| `grep` | Search file contents with ripgrep |
| `glob` | Find files by glob pattern |
| `bash` | Run shell commands for tests, builds, linters, git, and inspection |

### Bash and Command Execution

The built-in `bash` tool supports configurable command execution modes:

- `host` - Default, non-sandboxed execution on the local machine. This is
  intended for trusted environments, such as when Koda itself is already running
  inside a Docker Sandboxes microVM.
- `seatbelt` - Runs each command with macOS `sandbox-exec`, allowing network
  access and limiting writes to the workspace plus temporary storage.
- `bubblewrap` - Planned Linux sandbox mode. Not yet available.

Command execution mode can be configured in `~/.koda/config.json` or with
environment variables. See the [command execution README](packages/koda/src/koda/execution/README.md)
for details on execution modes and configuration.

## TUI

Koda's current user-facing interface is `koda-tui`, a prompt-toolkit based
full-screen terminal UI for chat, streaming responses, tool output, model
selection, and session management.

Open the command palette with `Ctrl+P` or `Ctrl+K` to configure providers,
switch models, manage sessions, and adjust TUI behavior or appearance.

### Keyboard Shortcuts

| Key | Action |
| --- | ------ |
| `Enter` | Submit the current message |
| `Shift+Enter` / `Ctrl+Enter` | Insert a newline |
| `Ctrl+C` | Cancel streaming, or press twice while idle to exit |
| `Escape` | Cancel streaming, or clear queued input |
| `Ctrl+P` / `Ctrl+K` | Open the command palette |
| `Ctrl+T` | Cycle supported thinking levels |
| `@` | Open workspace file suggestions |
| `Up` / `Down` | Navigate multi-line input or file suggestions |
| `Tab` / `Enter` | Accept the selected file suggestion |

## Development

### Project Structure

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
│   │   ├── execution/           # Bash command execution backends
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
│   │   ├── utils/               # TUI helper utilities
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

### Development Setup

Koda uses [Astral's](https://astral.sh/) Python toolchain:

- **uv** — package and workspace management
- **ruff** — linting and formatting
- **ty** — type checking

#### Prerequisites

Install uv from the [Astral docs](https://docs.astral.sh/uv/getting-started/installation/).

#### Getting Started

```bash
# Install dependencies and set up the workspace
uv sync

# Install git hooks
pre-commit install
```

Pre-commit hooks run Ruff and ty checks automatically.
Pre-push hooks run package tests plus additional security scanning.
