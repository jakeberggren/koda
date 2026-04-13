<div align="center">
<pre>
╔═══════════════════════════════════════════════════════════════╗
║   ██╗  ██╗ ██████╗ ██████╗  █████╗    ████████╗██╗   ██╗██╗   ║
║   ██║ ██╔╝██╔═══██╗██╔══██╗██╔══██╗   ╚══██╔══╝██║   ██║██║   ║
║   █████╔╝ ██║   ██║██║  ██║███████║█████╗██║   ██║   ██║██║   ║
║   ██╔═██╗ ██║   ██║██║  ██║██╔══██║╚════╝██║   ██║   ██║██║   ║
║   ██║  ██╗╚██████╔╝██████╔╝██║  ██║      ██║   ╚██████╔╝██║   ║
║   ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝      ╚═╝    ╚═════╝ ╚═╝   ║
╚═══════════════════════════════════════════════════════════════╝
</pre>
</div>

`koda-tui` is the terminal interface for Koda. It owns the interactive chat experience,
turns `koda-service` stream events into UI state, and renders model and tool output in the
terminal.

## Core Components

- **prompt_toolkit** for the application loop, full-screen layout, dialogs, and keybindings.
- **Rich** for markdown, code, diffs, and styled transcript rendering.
- **Streaming coordination** for incremental text, thinking, tool, and completion updates.
- **Palette-driven controls** for provider setup, model selection, thinking level, sessions,
  theme, scrollbar, and queued-input behavior.
- **In-process bootstrap** that wires settings, telemetry, the bundled service, and the TUI agent.

## Package Structure

```text
packages/koda-tui/
├── src/koda_tui/
│   ├── __init__.py             # CLI entrypoint and app bootstrap
│   ├── __main__.py             # Module entrypoint
│   ├── agent.py                # TUI-specific agent builder and tool wiring
│   ├── actions.py              # TUI actions backed by settings/service operations
│   ├── converters.py           # Service DTO -> TUI state conversion
│   ├── state.py                # Shared TUI state
│   ├── app/
│   │   ├── application.py      # App orchestration and settings synchronization
│   │   ├── keybindings.py      # Keyboard shortcuts and submission behavior
│   │   ├── output.py           # Synchronized terminal output
│   │   ├── queue.py            # Queued input handling
│   │   ├── response.py         # Response lifecycle helpers
│   │   └── streaming.py        # Stream event processing and cancellation
│   ├── components/
│   │   ├── chat_area.py        # Chat transcript view
│   │   ├── file_suggestions.py # File suggestion UI
│   │   ├── input_area.py       # Prompt input widget
│   │   ├── queued_inputs.py    # Queued input display
│   │   ├── status_bar.py       # Status/footer UI
│   │   └── __init__.py
│   ├── rendering/
│   │   ├── renderer.py         # Rich + prompt_toolkit rendering
│   │   └── __init__.py
│   ├── ui/
│   │   ├── layout.py           # Layout composition
│   │   ├── styles.py           # Theme-specific prompt_toolkit styles
│   │   └── palette/            # Command palette, dialogs, and palette commands
│   └── utils/
│       └── model_selection.py  # Model and thinking helper utilities
└── tests/
```
