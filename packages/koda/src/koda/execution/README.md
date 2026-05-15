# Command Execution

Koda's `bash` tool currently supports two execution modes, with one more planned:

- `host` - execute directly on the local machine
- `seatbelt` - execute inside a macOS `sandbox-exec` sandbox
- `bubblewrap` - planned Linux sandbox mode, not yet available

The default is `host`.

## Configure Execution

Persist the execution mode in `~/.koda/config.json`:

```json
{
  "core": {
    "bash_execution_sandbox": "host"
  }
}
```

Use `seatbelt` instead of `host` to enable the macOS sandbox. Note that
Seatbelt mode is only supported on macOS and requires `sandbox-exec` to be
available on the host system. `host` is the default execution mode and runs
commands directly on the local machine.

Environment variables can override the persisted setting for one shell session:

```bash
export KODA_BASH_EXECUTION_SANDBOX=seatbelt
```

## Seatbelt Runtime Contract

Koda starts a fresh `sandbox-exec` process for each command with these
expectations:

- this mode is macOS-only
- the host must provide `sandbox-exec`
- Koda runs `bash --noprofile --norc -c <command>` inside the sandbox
- network access is allowed
- filesystem reads are broadly allowed
- filesystem writes are restricted to the configured workspace and a fresh
  temporary scratch directory for that command
- `HOME`, `TMP`, `TEMP`, `TMPDIR`, and `XDG_CACHE_HOME` are redirected into that
  scratch directory so common tools can still write temp files and caches
- the command starts with working directory set somewhere under the configured
  workspace

In practice, seatbelt mode is a good fit when you are on macOS and want a more
restricted local executor while preserving normal networked developer workflows.

## Notes

- Seatbelt execution is useful on macOS when you want to restrict writes to the
  workspace plus per-run temporary storage while preserving networked developer
  workflows.
- In seatbelt mode, the temporary scratch directory is ephemeral per command and
  is not preserved between invocations.

## Safety

`host` execution runs commands directly on the local machine and should be treated
as fully trusted execution.

`seatbelt` execution adds meaningful restrictions for macOS workflows. Koda runs
commands under `sandbox-exec`, allows network access and broad reads, and limits
writes to the workspace plus a per-run scratch directory.

`seatbelt` should not be treated as a hardened security boundary for fully
untrusted or adversarial code. It allows network access and broad filesystem
reads outside the workspace.
