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
runs the `koda` agent, turns its stream events into UI state, and renders model and tool output in the
terminal.

## Core Components

- **prompt_toolkit** for the application loop, full-screen layout, dialogs, and keybindings.
- **Rich** for markdown, code, diffs, and styled transcript rendering.
- **Streaming coordination** for incremental text, thinking, tool, and completion updates.
- **Palette-driven controls** for provider setup, model selection, thinking level, sessions,
  theme, scrollbar visibility, and input behavior.
- **Settings** in `~/.koda/settings.json`, changed through the palette.

## Package Structure

```text
packages/koda-tui/src/koda_tui/
├── main.py         # Builds the app from its parts, sets up logging, and runs it
├── settings.py     # Settings, loaded from and saved to ~/.koda/settings.json
├── state.py        # AppState: what the UI shows
├── strings.py      # All user-facing text
├── workspace.py    # Workspace file index for @ mentions
├── app/            # The application: wiring, the agent, keybindings, exit prompt
├── messaging/      # Conversation (messages from agent events) and Outbox (sending)
├── palette/        # Command palette and its menus
├── views/          # Screen, chat, composer, pending messages, status bar
├── rendering/      # Rich-based rendering of messages, markdown, and diffs
├── ui/             # Primitives, widgets, and overlays on prompt_toolkit
├── appearance/     # Themes, tokens, icons, and sizes
└── terminal/       # Terminal protocol and key decoding
```
