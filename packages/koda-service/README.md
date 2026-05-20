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

`koda-service` is the application service boundary around the Koda core. It defines the
public protocol consumed by clients such as `koda-tui` and ships the local service
implementation used by the app today.

## Responsibilities

- Define the public `KodaService` protocol and shared `ServiceStatus`.
- Validate runtime readiness for provider credentials, model selection, and agent creation.
- Provide the local implementation for chat, catalogs, and session management.

## Package Structure

```text
packages/koda-service/
├── src/koda_service/
│   ├── __init__.py                  # Public package exports
│   ├── protocols.py                 # KodaService protocol
│   ├── exceptions.py                # Service/runtime and startup-style errors
│   └── services/
│       └── local/
│           ├── __init__.py          # Local service exports
│           ├── config.py            # LocalRuntimeConfig
│           ├── runtime.py           # Agent dependency creation/cache
│           └── service.py           # LocalKodaService and readiness logic
└── tests/
```

## Public Surface

For consumers, the intended imports are:

- `koda_service` for `KodaService`, `ChatRequest`, `LocalKodaService`, `LocalRuntimeConfig`, `ServiceDiagnostics`, and `ServiceStatus`
- `koda_service.exceptions` for service-layer and user-fixable startup errors
- `koda_service.services.local` for `LocalKodaService`

Most clients should depend on the protocol. Import the concrete local implementation only
when you want the bundled runtime.
