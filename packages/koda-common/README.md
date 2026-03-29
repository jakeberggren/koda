<div align="center">
<pre>
╔═══════════════════════════════════════════════════════════════════════════════════════════════════════╗
║   ██╗  ██╗ ██████╗ ██████╗  █████╗        ██████╗ ██████╗ ███╗   ███╗███╗   ███╗ ██████╗ ███╗   ██╗   ║
║   ██║ ██╔╝██╔═══██╗██╔══██╗██╔══██╗      ██╔════╝██╔═══██╗████╗ ████║████╗ ████║██╔═══██╗████╗  ██║   ║
║   █████╔╝ ██║   ██║██║  ██║███████║█████╗██║     ██║   ██║██╔████╔██║██╔████╔██║██║   ██║██╔██╗ ██║   ║
║   ██╔═██╗ ██║   ██║██║  ██║██╔══██║╚════╝██║     ██║   ██║██║╚██╔╝██║██║╚██╔╝██║██║   ██║██║╚██╗██║   ║
║   ██║  ██╗╚██████╔╝██████╔╝██║  ██║      ╚██████╗╚██████╔╝██║ ╚═╝ ██║██║ ╚═╝ ██║╚██████╔╝██║ ╚████║   ║
║   ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝       ╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════════════╝
</pre>
</div>

`koda-common` is the shared utilities library for Koda. It provides settings management, structured logging, and shared path helpers.

## Core Components

- **Settings management** with layered configuration: default values, environment variable overrides, JSON file persistence, and system keychain storage for API keys.
- **Structured logging** via structlog with console and rotating file output, context variables for correlation, and configurable log levels.
- **Shared path helpers** for locating the Koda home directory plus default config, log, and session paths.

## Package Structure

```text
packages/koda-common/
├── src/koda_common/
│   ├── logging/
│   │   ├── config.py            # Structured logging setup
│   │   ├── settings.py          # Logging-related settings models
│   │   ├── types.py             # Shared logging types
│   │   └── __init__.py
│   ├── settings/
│   │   ├── settings.py          # Settings and environment models
│   │   ├── manager.py           # Settings manager
│   │   ├── store.py             # Storage backends (JSON, keychain)
│   │   └── __init__.py
│   ├── paths.py                 # Shared filesystem paths
│   └── __init__.py
└── tests/
```
