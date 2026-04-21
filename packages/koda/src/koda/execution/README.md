# Command Execution

Koda's `bash` tool can run commands in one of two execution modes:

- `host` - execute directly on the local machine
- `docker` - execute inside a short-lived Docker container

The default is `host`.

## Configure Docker Execution

Set the execution backend and Docker image:

```bash
export KODA_BASH_EXECUTION_SANDBOX=docker
export KODA_BASH_EXECUTION_DOCKER_IMAGE=my-koda-bash:latest
```

Koda does not ship or manage a universal Docker image. If you enable Docker
execution, you are responsible for providing an image that matches the runtime
contract below.

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

## Notes

- Docker execution is useful when you want a more controlled local toolchain than
  the host machine provides.
- Network access is not disabled by Koda's Docker executor today.
- Because containers are ephemeral per command, filesystem state outside the
  mounted workspace and temp directories is not preserved between invocations.

## Safety

`host` execution runs commands directly on the local machine and should be treated
as fully trusted execution.

`docker` execution adds meaningful isolation and is the recommended option when
you want to reduce risk. Koda runs each command in a short-lived container with a
read-only root filesystem, dropped Linux capabilities, `no-new-privileges`, and a
writable mount only for the workspace.

This improves containment, but it is not a hardened security boundary. The mounted
workspace remains writable, network access is currently allowed, and Docker should
not be treated as sufficient isolation for fully untrusted or adversarial code.
