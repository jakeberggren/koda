<div align="center">
<pre>
╔═══════════════════════════════════════╗
║   ██╗  ██╗ ██████╗ ██████╗  █████╗    ║
║   ██║ ██╔╝██╔═══██╗██╔══██╗██╔══██╗   ║
║   █████╔╝ ██║   ██║██║  ██║███████║   ║
║   ██╔═██╗ ██║   ██║██║  ██║██╔══██║   ║
║   ██║  ██╗╚██████╔╝██████╔╝██║  ██║   ║
║   ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝   ║
╚═══════════════════════════════════════╝
</pre>
</div>


## CLI Usage

KODA provides a basic CLI tool for testing and interacting with agents.

### Basic Commands

#### Interactive Chat Session

Start an interactive chat session (default mode):

```bash
koda
```

With provider and model options:

```bash
koda --provider openai --model gpt-5.1
koda -p anthropic -m claude-opus-4-5
```

#### Streaming Responses

Enable streaming mode in the interactive session:

```bash
koda --stream
```

Or use the short flag:

```bash
koda -s
```

With provider and model options:

```bash
koda --stream --provider openai --model gpt-4
koda -s -p anthropic -m claude-3-opus
```

Type `exit`, `quit`, or `q` to end the session.

### Help

Get help for any command:

```bash
koda --help
```
