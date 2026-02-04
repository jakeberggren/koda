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

Shared utilities library providing settings management, structured logging, and database connectivity.

## Core Components

- **Settings management** with layered configuration: default values, environment variable overrides, JSON file persistence, and system keychain storage for API keys.
- **Structured logging** via structlog with console and rotating file output, context variables for correlation, and configurable log levels.
- **Database configuration** with engine creation, caching, and LibSQL support for local and remote sync scenarios.

## Project Structure

```
packages/koda-common/
├── src/koda_common/
│   ├── db/
│   │   ├── config.py            # Database configuration and settings
│   │   ├── engine.py            # Engine creation and caching
│   │   └── __init__.py
│   ├── logging/
│   │   ├── config.py            # Structured logging setup
│   │   └── __init__.py
│   ├── settings/
│   │   ├── settings.py          # Settings and environment models
│   │   ├── manager.py           # Settings manager
│   │   ├── store.py             # Storage backends (JSON, keychain)
│   │   └── __init__.py
│   └── __init__.py
└── tests/
```
