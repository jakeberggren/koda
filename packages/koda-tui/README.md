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

koda-tui is the terminal interface for Koda. It owns the interactive chat experience,
streams service events into UI state, and renders model/tool output in the terminal.
It sits on top of `koda-service`, which provides the in-process runtime used today.

## Core Components

- **prompt_toolkit** for the application loop, layouts, dialogs, and keybindings.
- **Rich** for markdown, code, diffs, and styled output rendering.
- **Streaming coordination** for turning service events into incremental UI updates.
- **Command palette flows** for model selection, session management, thinking controls, and API key entry.

## Project Structure

```text
packages/koda-tui/
├── src/koda_tui/
│   ├── app/
│   │   ├── application.py      # App entrypoint and orchestration
│   │   ├── keybindings.py      # Keyboard shortcuts
│   │   ├── output.py           # Synchronized terminal output
│   │   ├── queue.py            # Queued input handling
│   │   ├── response.py         # Response lifecycle helpers
│   │   └── streaming.py        # Stream event processing
│   ├── components/
│   │   ├── chat_area.py        # Chat transcript view
│   │   ├── input_area.py       # Prompt input widget
│   │   ├── queued_inputs.py    # Queued input display
│   │   ├── status_bar.py       # Status/footer UI
│   │   └── __init__.py
│   ├── rendering/
│   │   ├── renderer.py         # Rich + prompt_toolkit rendering
│   │   └── __init__.py
│   ├── ui/
│   │   ├── layout.py           # Layout composition
│   │   ├── styles.py           # Prompt_toolkit styles
│   │   └── palette/            # Command palette, dialogs, and palette commands
│   ├── actions.py              # TUI actions backed by the service layer
│   ├── converters.py           # Service DTO -> TUI state conversion
│   ├── state.py                # Shared TUI state
│   ├── __main__.py             # Module entrypoint
│   └── __init__.py
└── tests/
```
