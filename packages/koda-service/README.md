<div align="center">
<pre>
╔═════════════════════════════════════════════════════════════════════════════════════════════════╗
║   ██╗  ██╗ ██████╗ ██████╗  █████╗       ███████╗███████╗██████╗ ██╗   ██╗██╗ ██████╗███████╗   ║
║   ██║ ██╔╝██╔═══██╗██╔══██╗██╔══██╗      ██╔════╝██╔════╝██╔══██╗██║   ██║██║██╔════╝██╔════╝   ║
║   █████╔╝ ██║   ██║██║  ██║███████║█████╗███████╗█████╗  ██████╔╝██║   ██║██║██║     █████╗     ║
║   ██╔═██╗ ██║   ██║██║  ██║██╔══██║╚════╝╚════██║██╔══╝  ██╔══██╗╚██╗ ██╔╝██║██║     ██╔══╝     ║
║   ██║  ██╗╚██████╔╝██████╔╝██║  ██║      ███████║███████╗██║  ██║ ╚████╔╝ ██║╚██████╗███████╗   ║
║   ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝      ╚══════╝╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚═╝ ╚═════╝╚══════╝   ║
╚═════════════════════════════════════════════════════════════════════════════════════════════════╝
</pre>
</div>

koda-service is the service boundary and runtime orchestration layer around the Koda core. It
defines the public service protocol used by clients such as `koda-tui`, owns the boundary DTOs
that cross that service edge, and wires the in-process implementation used today.

## Responsibilities

- Define the public `KodaService` protocol consumed by clients.
- Define service-boundary DTOs in `koda_service.types`.
- Map Koda core models and events into service DTOs.
- Own startup orchestration for creating settings and a ready service.
- Provide the in-process service implementation and runtime wiring.

## Package Structure

```text
packages/koda-service/
├── src/koda_service/
│   ├── __init__.py                  # Minimal public package surface
│   ├── protocols.py                 # KodaService protocol
│   ├── exceptions.py                # Service and startup exceptions
│   ├── startup.py                   # StartupContext and startup orchestration
│   ├── bootstrap.py                 # Lower-level runtime assembly helpers
│   ├── types/                       # Service-boundary DTOs
│   ├── mappers/                     # Core -> service mapping helpers
│   └── services/
│       └── in_process/
│           ├── service.py           # InProcessKodaService
│           ├── runtime.py           # Runtime bundle + runtime factory
│           ├── chat.py              # Chat behavior
│           ├── sessions.py          # Session behavior
│           └── catalog.py           # Provider/model catalog behavior
└── tests/
```

## Public Surface

For consumers, the intended imports are:

- `koda_service` for the `KodaService` protocol
- `koda_service.startup` for `create_startup_context`
- `koda_service.exceptions` for startup and service-layer exceptions
- `koda_service.types` for service-boundary DTOs

Clients should not need to import from implementation modules such as
`koda_service.services.in_process` unless they are doing lower-level composition or testing.
