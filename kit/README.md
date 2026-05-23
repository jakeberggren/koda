<div align="center">
<pre>
╔═════════════════════════════════════════════════════════════════╗
║   ██╗  ██╗ ██████╗ ██████╗  █████╗       ██╗  ██╗██╗████████╗   ║
║   ██║ ██╔╝██╔═══██╗██╔══██╗██╔══██╗      ██║ ██╔╝██║╚══██╔══╝   ║
║   █████╔╝ ██║   ██║██║  ██║███████║█████╗█████╔╝ ██║   ██║      ║
║   ██╔═██╗ ██║   ██║██║  ██║██╔══██║╚════╝██╔═██╗ ██║   ██║      ║
║   ██║  ██╗╚██████╔╝██████╔╝██║  ██║      ██║  ██╗██║   ██║      ║
║   ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝      ╚═╝  ╚═╝╚═╝   ╚═╝      ║
╚═════════════════════════════════════════════════════════════════╝
</pre>
</div>

# Koda Kit

Koda Kit runs [Koda](https://github.com/jakeberggren/koda) inside a Docker
Sandboxes sandbox. It keeps provider credentials on the host and lets Docker
Sandboxes inject them into matching outbound requests.

## Requirements

- Docker Sandboxes / `sbx` CLI installed and signed in.
- At least one supported provider secret.

For Docker Sandboxes setup, see the
[Docker Sandboxes documentation](https://docs.docker.com/ai/sandboxes/).

## Quickstart

Store a provider key with Docker Sandboxes:

```bash
sbx secret set -g openai  # and/or anthropic, bergetai, github
```

Then start Koda:

```bash
sbx run --kit "git+https://github.com/jakeberggren/koda.git#ref=main&dir=kit/koda" koda
```

Koda opens as an interactive terminal UI inside the sandbox.

## Supported Credentials

The kit currently declares proxy-managed credentials for:

| Service | Secret command | Environment variable |
| --- | --- | --- |
| OpenAI | `sbx secret set -g openai` | `OPENAI_API_KEY` |
| Anthropic | `sbx secret set -g anthropic` | `ANTHROPIC_API_KEY` |
| BergetAI | `sbx secret set -g bergetai` | `BERGETAI_API_KEY` |
| GitHub | `sbx secret set -g github` | `GH_TOKEN` |

For GitHub access through the GitHub CLI, you can store your current token:

```bash
echo "$(gh auth token)" | sbx secret set -g github
```

### How Credentials Work

The kit sets `KODA_CREDENTIAL_MODE=proxy-managed`. In this mode, Koda does not
ask you to paste provider API keys into the TUI. Add or rotate provider secrets
with `sbx secret set -g ...` outside Koda, then create a new sandbox so the
updated secret is available.

Inside the sandbox, Docker Sandboxes exposes placeholder credential environment
variables such as `OPENAI_API_KEY=proxy-managed`. The real secret is not written
into the sandbox. Docker injects it into matching outbound requests based on the
kit's `network.serviceDomains` and `network.serviceAuth` mappings.

This means Koda cannot verify provider connectivity from the provider palette.
Model access is verified when the first real provider request is made.

Note that only built-in providers are supported when running Koda through
Docker Sandboxes.
