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

KODA is an agentic coding assistant designed for the terminal. KODA is built to understand,
navigate and safely modify real codebases, as a complete coding companion for end-to-end software creation.

The current state of KODA is a lightweight, provider-agnostic agent framework with a simple CLI for running
and testing interactive chat agents. Future improvements include persistent sessions, a fully built-out TUI, and
more advanced tooling for improved codebase navigation and safe editing capabilities.

## CLI Usage

KODA provides a basic CLI tool for testing and interacting with agents.

### Basic Commands

#### Interactive Chat Session

Start an interactive chat session (default mode):

```bash
koda
```

With provider and model options:

```bash
koda --provider openai --model gpt-5.1
koda -p anthropic -m claude-opus-4-5
```

Type `exit`, `quit`, or `q` to end the session.

### Help

Get help for any command:

```bash
koda --help
```
