# Command Execution

Koda's `bash` tool can run commands in one of three execution modes:

- `host` - execute directly on the local machine
- `docker` - execute inside a short-lived Docker container
- `seatbelt` - execute inside a macOS `sandbox-exec` sandbox

The default is `host`.

## Configure Execution

### Host

```bash
export KODA_BASH_EXECUTION_SANDBOX=host
```

### Docker

Set the execution backend and Docker image:

```bash
export KODA_BASH_EXECUTION_SANDBOX=docker
export KODA_BASH_EXECUTION_DOCKER_IMAGE=my-koda-bash:latest
```

Koda does not ship or manage a universal Docker image. If you enable Docker
execution, you are responsible for providing an image that matches the runtime
contract below.

### Seatbelt

Enable the macOS seatbelt sandbox with:

```bash
export KODA_BASH_EXECUTION_SANDBOX=seatbelt
```

Seatbelt mode is only supported on macOS and requires `sandbox-exec` to be
available on the host system.

## Docker Runtime Contract

Koda starts a fresh container for each command and currently invokes Docker with
these expectations:

- the image must include `bash`
- Koda runs `bash --noprofile --norc -c <command>`
- the container must support arbitrary `uid:gid` via `--user`
- the container root filesystem is mounted read-only
- writable `tmpfs` mounts are provided for `/tmp` and `/var/tmp`
- the workspace is bind-mounted at `/workspace`
- the command starts with working directory set somewhere under `/workspace`

In practice, the image should contain whatever tooling you want available to the
assistant, for example `python`, `uv`, `git`, `rg`, and `jq`.

## Example Dockerfile

This is a complete example image suitable for local development:

```dockerfile
# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        fd-find \
        findutils \
        git \
        jq \
        less \
        procps \
        ripgrep \
        tree \
        unzip \
        zip \
    && rm -rf /var/lib/apt/lists/*

# Keep tool caches under /tmp so they continue to work when Koda runs the
# container with a read-only root filesystem and tmpfs-backed temp dirs.
ENV HOME=/tmp
ENV UV_CACHE_DIR=/tmp/uv-cache
ENV XDG_CACHE_HOME=/tmp/.cache

WORKDIR /workspace
```

Build it from the repository root with:

```bash
docker build -t my-koda-bash:latest -f path/to/Dockerfile .
```

## Seatbelt Runtime Contract

Koda starts a fresh `sandbox-exec` process for each command with these
expectations:

- this mode is macOS-only
- the host must provide `sandbox-exec`
- Koda runs `bash --noprofile --norc -c <command>` inside the sandbox
- network access is denied
- filesystem reads are broadly allowed
- filesystem writes are restricted to the configured workspace and a fresh
  temporary scratch directory for that command
- `HOME`, `TMP`, `TEMP`, `TMPDIR`, and `XDG_CACHE_HOME` are redirected into that
  scratch directory so common tools can still write temp files and caches
- the command starts with working directory set somewhere under the configured
  workspace

In practice, seatbelt mode is a good fit when you are on macOS and want a more
restricted local executor without maintaining a Docker image.

## Notes

- Docker execution is useful when you want a more controlled local toolchain than
  the host machine provides.
- Seatbelt execution is useful on macOS when you want to block network access and
  restrict writes to the workspace plus per-run temporary storage.
- Network access is not disabled by Koda's Docker executor today.
- Because containers are ephemeral per command, filesystem state outside the
  mounted workspace and temp directories is not preserved between invocations.
- In seatbelt mode, the temporary scratch directory is ephemeral per command and
  is not preserved between invocations.

## Safety

`host` execution runs commands directly on the local machine and should be treated
as fully trusted execution.

`docker` execution adds meaningful isolation and is the recommended option when
you want to reduce risk on systems where Docker is available. Koda runs each
command in a short-lived container with a read-only root filesystem, dropped
Linux capabilities, `no-new-privileges`, and a writable mount only for the
workspace.

`seatbelt` execution adds meaningful restrictions for macOS workflows. Koda runs
commands under `sandbox-exec`, denies network access, allows broad reads, and
limits writes to the workspace plus a per-run scratch directory.

Neither `docker` nor `seatbelt` should be treated as a hardened security boundary
for fully untrusted or adversarial code. In particular, Docker currently allows
network access, and seatbelt still allows broad filesystem reads outside the
workspace.
