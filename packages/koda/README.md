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

`koda` is the core library for the Koda coding assistant. It contains the agent loop,
LLM abstractions, session model, telemetry hooks, and tool framework used by higher-level
packages such as `koda-service` and `koda-tui`.

## Responsibilities

- Run the agent loop and manage tool-call iterations.
- Define provider-agnostic LLM protocols, models, events, and registries.
- Provide built-in provider integrations for OpenAI and BergetAI.
- Model internal conversation messages and session persistence.
- Provide telemetry integration points.
- Expose the tool framework and built-in filesystem-oriented tools.

## Package Structure

```text
packages/koda/
├── src/koda/
│   ├── agents/
│   │   └── agent.py                # Core agent loop
│   ├── llm/
│   │   ├── drivers/                # Provider driver adapters
│   │   ├── providers/              # OpenAI and BergetAI providers
│   │   ├── models.py               # Model definitions and capabilities
│   │   ├── protocols.py            # LLM protocol
│   │   ├── registry.py             # Provider/model registries
│   │   └── types.py                # Requests, responses, stream events
│   ├── messages/
│   │   └── messages.py             # Internal message types
│   ├── sessions/
│   │   ├── manager.py              # Session orchestration
│   │   ├── session.py              # Session model
│   │   └── store.py                # In-memory and JSON session stores
│   ├── telemetry/
│   │   └── langfuse.py             # Langfuse integration
│   ├── tools/
│   │   ├── builtins/               # read/list/glob/grep/edit/write tools
│   │   ├── executor.py             # Tool execution runtime
│   │   ├── registry.py             # Tool registration
│   │   ├── config.py               # Tool configuration bundle
│   │   └── context.py              # Sandbox/context information
│   └── __init__.py
└── tests/
```

## Public Surface

The package re-exports its main building blocks from the following modules:

- `koda.llm` for LLM protocols, requests, responses, events, and registries
- `koda.sessions` for session management and persistence
- `koda.messages` for internal message models
- `koda.tools` for the tool framework and built-in tool registration helpers
- `koda.telemetry` for telemetry interfaces and Langfuse integration
- `koda.agents` for the core `Agent` implementation
