# Mazemaker memory provider — implementation

Created 2026-05-29 (commit 9721d64). Resolves the long-standing gap where
`memory.provider: mazemaker` in config.yaml had no matching plugin.

## What it does

Saves every Hermes turn as an `auto:turn:<session>:<ts>` memory in the local
mazemaker pod. Called by the MemoryManager after every assistant response via
`sync_turn(user, asst)`.

## Source

- **Backend repo:** `client/hermes-plugins/mazemaker-memory-provider/__init__.py`
- **Installed path:** `~/.hermes/plugins/mazemaker/__init__.py`
- **Shipped via:** install.sh (copies during install), source.tar.gz (bundled)
- **Exempted from** the .py publish gate via `-not -path '*/client/hermes-plugins/*'`

## How it works

```python
class MazemakerMemoryProvider(MemoryProvider):
    def sync_turn(self, user: str, asst: str) -> None:
        label = f"auto:turn:{session_id}:{int(time.time()):x}"
        content = f"session:{session_id} @ ...\n=== USER ===\n{user}\n\n=== ASSISTANT ===\n{asst}"
        # Truncate to 3200 chars, then:
        POST http://127.0.0.1:8765/tools/call
        {"name": "mazemaker_remember", "arguments": {"content": ..., "label": label}}
```

- Connects to wonderland at `127.0.0.1:8765` (configurable via `MM_WONDERLAND_URL`)
- Fails silently if pod unreachable — no Hermes disruption
- Content capped at 3200 chars (avoids multi-MB memory bloat)

## Activation

Zero-config — the existing `memory.provider: mazemaker` in config.yaml
activates it automatically once the plugin file exists in the right directory.

## Verification

```bash
ls ~/.hermes/plugins/mazemaker/__init__.py          # file exists
hermes config get memory.provider                    # returns "mazemaker"
# Via MCP:
mazemaker_browse(label_prefix='auto:turn')           # shows recent turn memories
```

## Pitfalls

- Only activates on NEW Hermes sessions — existing sessions already loaded
  their memory provider at init time and won't pick up a new plugin mid-session.
- Plugin must be at `~/.hermes/plugins/mazemaker/`, NOT at
  `~/.hermes/hermes-agent/plugins/memory/mazemaker/`. The user-installed
  path (`$HERMES_HOME/plugins/`) survives Hermes updates; the bundled path
  (`plugins/memory/`) gets overwritten.
- If the mazemaker pod is not running, `sync_turn` logs a debug line and
  returns — no Hermes errors, but no memories saved either.
