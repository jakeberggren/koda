<div align="center">
<pre>
╔════════════════════════════════════════════════════════════════╗
║   ██╗  ██╗ ██████╗ ██████╗  █████╗        █████╗ ██████╗ ██╗   ║
║   ██║ ██╔╝██╔═══██╗██╔══██╗██╔══██╗      ██╔══██╗██╔══██╗██║   ║
║   █████╔╝ ██║   ██║██║  ██║███████║█████╗███████║██████╔╝██║   ║
║   ██╔═██╗ ██║   ██║██║  ██║██╔══██║╚════╝██╔══██║██╔═══╝ ██║   ║
║   ██║  ██╗╚██████╔╝██████╔╝██║  ██║      ██║  ██║██║     ██║   ║
║   ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝      ╚═╝  ╚═╝╚═╝     ╚═╝   ║
╚════════════════════════════════════════════════════════════════╝
</pre>
</div>

koda-api is the client/backend boundary package for Koda. It defines how clients talk to runtime backends and
keeps transport/runtime details isolated behind shared contracts.

## Core Components

- **Backends** that implement the `KodaBackend` contract (currently in-process).
- **Mappers** that convert core runtime/provider/session/message/tool types into shared contract models.
- **Backend factory** for backend selection and creation based on settings.

## Architecture Notes

- **Boundary ownership:** `koda_common.contracts` is the stable client/backend boundary.
- **Dependency direction:** clients (`koda-tui`, future apps) depend on contracts, not on `koda` core types.
- **Backend responsibility:** backends in `koda-api` may use core/runtime internals, but must return contract types.
- **Mapping rule:** all core-to-contract conversion happens in `koda_api.mappers`, not in clients.
- **Backend implementations:** new backends should implement `KodaBackend` and be wired through `create_backend`.
- **Clients:** treat contract models as the only public API; avoid importing backend internals.

## Project Structure

```
packages/koda-api/
├── src/koda_api/
│   ├── backends/
│   │   ├── __init__.py         # Backend types + factory
│   │   └── in_process.py       # In-process backend implementation
│   ├── mappers/
│   │   ├── __init__.py         # Mapper exports
│   │   ├── events.py           # Provider event -> contract stream events
│   │   ├── messages.py         # Core messages -> contract messages
│   │   ├── models.py           # Core model defs -> contract model defs
│   │   ├── sessions.py         # Core sessions -> session info
│   │   └── tools.py            # Core tool types -> contract tool types
│   └── __init__.py
└── tests/
```
