<div align="center">
<pre>
╔══════════════════════════════════════════════════════════════════════════════╗
║   ██╗  ██╗ ██████╗ ██████╗  █████╗        ██████╗ ██████╗ ██████╗ ███████╗   ║
║   ██║ ██╔╝██╔═══██╗██╔══██╗██╔══██╗      ██╔════╝██╔═══██╗██╔══██╗██╔════╝   ║
║   █████╔╝ ██║   ██║██║  ██║███████║█████╗██║     ██║   ██║██████╔╝█████╗     ║
║   ██╔═██╗ ██║   ██║██║  ██║██╔══██║╚════╝██║     ██║   ██║██╔══██╗██╔══╝     ║
║   ██║  ██╗╚██████╔╝██████╔╝██║  ██║      ╚██████╗╚██████╔╝██║  ██║███████╗   ║
║   ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝       ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝   ║
╚══════════════════════════════════════════════════════════════════════════════╝
</pre>
</div>

`koda` is the core library for the Koda coding assistant, in two layers:

- **The kernel**: the agent loop, LLMs, tools, messages and sessions.
- **The harness** (`koda.harness`): what makes the agent a coding agent. the
  workspace, the system prompt for it and the built-in tools.

```python
from koda import harness
from koda.agent import Agent

workspace = harness.Workspace(path)
agent = Agent(
    llm,
    instructions=harness.instructions(workspace),
    tools=harness.tools(workspace),
)
```

## Package Structure

```text
packages/koda/
├── src/koda/
│   ├── agent/
│   │   ├── agent.py                # The agent loop and its turn
│   │   ├── events.py               # What the agent streams
│   │   └── hooks.py                # Hooks run when the session changes
│   ├── llm/
│   │   ├── apis/                   # Anthropic Messages and OpenAI Responses/Completions/Codex
│   │   ├── auth/                   # OAuth login and refresh
│   │   ├── catalog.py              # Providers and models from models.json
│   │   ├── credentials.py          # Stored API keys and logins
│   │   ├── exceptions.py           # LLM-related exceptions
│   │   ├── models.py               # Provider, Connection and Model
│   │   ├── models.json             # Bundled catalog
│   │   ├── protocols.py            # LLM and Credentials protocols
│   │   ├── types.py                # Requests, responses, stream events
│   │   └── utils.py                # Shared LLM helper utilities
│   ├── messages/
│   │   └── messages.py             # Messages, tool calls and tool output
│   ├── sessions/
│   │   ├── exceptions.py           # Session-related exceptions
│   │   ├── session.py              # Session model
│   │   └── store.py                # In-memory and JSON session stores
│   ├── tools/
│   │   ├── base.py                 # The Tool protocol and ToolDefinition
│   │   ├── exceptions.py           # ToolError
│   │   ├── executor.py             # Runs tool calls
│   │   └── registry.py             # The tools by name
│   ├── harness/
│   │   ├── workspace.py            # The folder: paths, path errors and locks
│   │   ├── prompt.py               # SYSTEM.md, AGENTS.md and CLAUDE.md
│   │   └── toolbox/
│   │       ├── shell.py            # bash
│   │       ├── files/              # read_file, write_file, edit_file
│   │       └── search/             # glob, grep
│   └── paths.py                    # ~/.koda
└── tests/
```

## Public Surface

- `koda.agent` for `Agent`, its events and hooks
- `koda.llm` for the catalog, LLM protocols, requests, responses and events
- `koda.messages` for messages, tool calls and tool output
- `koda.sessions` for sessions and their stores
- `koda.tools` for the `Tool` protocol, `ToolRegistry`, `ToolExecutor` and `ToolError`
- `koda.harness` for `Workspace`, `instructions()` and `tools()`

LLM calls through OpenAI-compatible APIs can be traced to Langfuse, configured via the
`LANGFUSE_*` environment variables.
