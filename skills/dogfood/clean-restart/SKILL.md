---
name: clean-restart
description: Kill any running daedalus session, clear regen-able neural-memory caches (embed_cache.pkl, gpu_cache, embed.sock, sqlite WAL artifacts) and all __pycache__ dirs under the project + deployed plugin paths so the next `daedalus` launch boots fresh against the current code. Preserves user data (memory.db, dream_sessions.db, lstm_weights.bin, models/). Use when you've changed neural-memory-adapter code and want a clean reload.
---

# /clean-restart — kill hermes session and reset caches for a fresh boot

## What this does

Run the helper script
`/home/alca/projects/neural-memory-adapter/tools/hermes-clean-restart.sh`
and report the result. The script:

1. Finds and kills any running `python … hermes` process (matches
   `hermes-agent/venv/bin/python … hermes`, not unrelated `hermes-crypto`).
2. Removes regen-able caches under `~/.mazemaker/`:
   - `embed.sock` — stale UNIX socket from the killed shared-embed server
   - `embed_cache.pkl` — LRU embedding cache, rebuilds on demand
   - `gpu_cache/` — GPU recall tensor + metadata pickle
   - `memory.db-shm`, `memory.db-wal` — SQLite WAL artifacts
3. Purges every `__pycache__/` directory under the project source
   (`/home/alca/projects/neural-memory-adapter`) and the deployed plugin
   path (`~/.hermes/hermes-agent/plugins/memory/mazemaker/`) so the next
   import loads the current `.py` files, not stale bytecode.
4. Reports what was preserved (the user's actual data — never touched):
   `memory.db`, `dream_sessions.db`, `lstm_weights.bin`, `models/`,
   `access_logs/`, `backups/`.
5. Reports any auxiliary services still running (the dashboard
   `live_server.py` and `mcp_local.py` MCP server) — these are NOT
   killed because they're separate from hermes-agent itself; the user
   restarts them on demand if they want the new code there too.

## How to invoke from this skill

Run the helper script directly via the Bash tool. Pass `--dry` first
if the user wants a preview, otherwise run it for real:

```bash
bash /home/alca/projects/neural-memory-adapter/tools/hermes-clean-restart.sh
```

That's it — the script does everything and prints a green-tick report.
After it finishes, tell the user:

> Done. Run `hermes` to relaunch on the new code.

If you spot auxiliary services in the script's output (live_server.py
or mcp_local.py), surface those PIDs to the user with a one-line
suggestion so they can `kill <pid>` them if they want those refreshed
too — but DO NOT kill them yourself unless the user explicitly asks.

## When to use

- After committing changes to `python/__init__.py`, `python/memory_client.py`,
  `python/embed_provider.py`, etc., and you want hermes to pick up the
  new code on its next launch.
- When the FastEmbed warning, GPU waiter, or other startup-latency
  fixes don't seem to be taking effect — usually means the current
  hermes process is running pre-change Python loaded into memory.
- When `~/.mazemaker/sockets/embed.sock` is stale (server crashed / killed)
  and a new hermes can't connect to a phantom shared-embed server.

## When NOT to use

- DON'T run this with `hermes` actively in the foreground in another
  terminal — kills it mid-conversation. Make sure no live session you
  care about is running, OR exit those sessions cleanly first.
- DON'T treat this as a memory reset. `memory.db` is preserved
  precisely because it holds the user's persistent memories. If the
  user actually wants to wipe memory, that's a separate manual
  `rm ~/.mazemaker/data/memory.db*` operation, with confirmation.

## Output format

A short summary listing exactly what was killed/cleared/preserved,
followed by a single-line "Run `hermes` to relaunch." line. Don't
narrate every step — the script's own output is already informative,
just relay the salient parts.
