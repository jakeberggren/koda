<div align="center">
<pre>
╔════════════════════════════════════════════════════════════════╗
║   ██╗  ██╗ ██████╗ ██████╗  █████╗     ████████╗██╗   ██╗██╗   ║
║   ██║ ██╔╝██╔═══██╗██╔══██╗██╔══██╗    ╚══██╔══╝██║   ██║██║   ║
║   █████╔╝ ██║   ██║██║  ██║███████║       ██║   ██║   ██║██║   ║
║   ██╔═██╗ ██║   ██║██║  ██║██╔══██║       ██║   ██║   ██║██║   ║
║   ██║  ██╗╚██████╔╝██████╔╝██║  ██║       ██║   ╚██████╔╝██║   ║
║   ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝       ╚═╝    ╚═════╝ ╚═╝   ║
╚════════════════════════════════════════════════════════════════╝
</pre>
</div>

koda-tui is the terminal interface for Koda, focused on a simple chat loop, streaming responses, and rich rendering
for code and tool output. It sits on top of the core agent package and provides the interactive experience.

## Core Components

- **prompt_toolkit** for the application loop, layouts, and keybindings.
- **Rich** for markdown/code rendering, diffs, and styled output.
- **Async streaming** pipelines that update shared UI state as events arrive.
- **Backend abstraction** to swap between local and mock backends.

## Project Structure

```
packages/koda-tui/
├── src/koda_tui/
│   ├── app/
│   │   ├── application.py      # App entrypoint
│   │   ├── keybindings.py      # Keyboard shortcuts
│   │   ├── output.py           # Synchronized Output
│   │   └── __init__.py
│   ├── clients/
│   │   ├── base.py             # Client interface
│   │   ├── local.py            # Local client wrapper
│   │   ├── mock.py             # Mock client
│   │   └── __init__.py
│   ├── components/
│   │   ├── chat_area.py        # Chat transcript view
│   │   ├── input_area.py       # Prompt input widget
│   │   ├── status_bar.py       # Status/footer UI
│   │   └── __init__.py
│   ├── rendering/
│   │   ├── renderer.py         # Rich + prompt_toolkit rendering
│   │   └── __init__.py
│   ├── ui/
│   │   ├── layout.py           # Layout composition
│   │   ├── styles.py           # Prompt_toolkit styles
│   │   └── palette/            # Command Palette UI and Management
│   ├── __main__.py             # Module entrypoint
│   ├── state.py                # Shared TUI state
│   └── __init__.py
└── tests/
```
