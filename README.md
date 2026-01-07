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

KODA is a lightweight agentic coding assistant designed for the terminal. KODA is built to be a complete coding companion capable of navigating, understanding, and modifying codebases and completing coding tasks for end-to-end software creation.

The current state of KODA is a lightweight, provider-agnostic agent framework combined with a simple Terminal UI (TUI). Future improvements include persistent sessions, enhanced TUI features, and
more advanced tooling for improved codebase navigation and safe editing capabilities.

## Usage

Start an interactive chat session (default mode):

```bash
koda
```

Press Ctrl+C twice to exit the session.

## Project Structure

Koda is a monorepo workspace managed by uv, containing two main packages:

- koda: Provider-agnostic core library that handles agent logic, tool execution, and LLM provider integration
- koda-tui: Interactive terminal interface.

```
packages/
├── koda/           # Core agent framework
│   ├── agents/     # Agent orchestration
│   ├── config/     # Configuration and settings
│   ├── messages/   # Message types and handling
│   ├── providers/  # LLM provider adapters (OpenAI, Anthropic)
│   ├── tools/      # Agent tools (filesystem operations, etc.)
│   └── utils/      # Utilities and exceptions
│
└── koda-tui/       # Terminal user interface
    ├── app.py      # Main TUI application
    ├── backends/   # Backend implementations (local, mock)
    ├── input.py    # Input handling
    └── renderer.py # Output rendering with Rich
```
