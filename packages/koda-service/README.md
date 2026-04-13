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

`koda-service` is the service boundary around the Koda core. It defines the public protocol
consumed by clients such as `koda-tui`, owns the DTOs that cross that boundary, and ships the
in-process service implementation used by the app today.

## Responsibilities

- Define the public `KodaService` protocol and shared `ServiceStatus`.
- Define service-boundary DTOs in `koda_service.types`.
- Map Koda core models, messages, sessions, tools, and stream events into service DTOs.
- Validate runtime readiness for provider credentials, model selection, and agent creation.
- Provide the in-process implementation for chat, catalogs, and session management.

## Package Structure

```text
packages/koda-service/
├── src/koda_service/
│   ├── __init__.py                  # Public package exports
│   ├── protocols.py                 # KodaService protocol and AgentBuilder type
│   ├── exceptions.py                # Service/runtime and startup-style errors
│   ├── types/                       # Service-boundary DTOs
│   ├── mappers/                     # Core -> service mapping helpers
│   └── services/
│       └── in_process/
│           ├── __init__.py          # In-process service exports
│           └── service.py           # InProcessKodaService and readiness logic
└── tests/
```

## Public Surface

For consumers, the intended imports are:

- `koda_service` for `KodaService`, `AgentBuilder`, and `ServiceStatus`
- `koda_service.types` for service-boundary DTOs
- `koda_service.exceptions` for service-layer and user-fixable startup errors
- `koda_service.services.in_process` for `InProcessKodaService`

Most clients should depend on the protocol and DTOs. Import the concrete in-process
implementation only when you want the bundled runtime.
