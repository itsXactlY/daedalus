---
name: daedalus-gateway-debugging
description: How to debug the Daedalus messaging gateway - Discord, Telegram, platform issues
category: devops
version: 1.1
tags: [gateway, debugging, discord, telegram, platforms, daedalus]
priority: high
---


> Ported from `hermes-gateway-debugging` during the 2026-08-21 Daedalus skills alignment. Pre-rename history lives in git and `~/.daedalus/skills-archive/2026-08-21-hermes-legacy/`.
# Daedalus Gateway Debugging

The gateway routes messages between platforms (Discord, Telegram, etc.) and the agent.

## Architecture

```
Platform (Discord/Telegram/...)
    |
    v
gateway/run.py (351KB — handles everything)
    |
    +---> gateway/session.py (conversation persistence)
    +---> gateway/delivery.py (message delivery)
    +---> gateway/hooks.py (event hooks)
    +---> gateway/platforms/ (platform adapters)
    |
    v
AIAgent (run_agent.py)
```

## Check Gateway Status

```bash
# Is it running?
cat ~/.daedalus/gateway.pid
ps aux | grep gateway

# Check logs
journalctl -u daedalus-gateway --since "1 hour ago"

# Restart
kill $(cat ~/.daedalus/gateway.pid)
cd ~/.daedalus && python3 gateway/run.py &
```

## Common Issues

### 1. Gateway Not Starting
- Check port conflicts
- Check `~/.daedalus/config.yaml` for platform configs
- Check API keys in `~/.daedalus/.env`

### 2. Messages Not Delivered
- Check `channel_directory.json` for channel mappings
- Check gateway hooks for filter/block rules
- Check platform-specific auth (Discord bot token, Telegram bot token)

### 3. Discord Issues
- Bot token in `~/.daedalus/.env` as `DISCORD_TOKEN`
- Channel mappings in `channel_directory.json`
- Gateway connects via WebSocket, not REST API
- Cloudflare WAF blocks REST API from datacenter IPs — WebSocket works

### 4. Agent Not Responding
- Check if `run_agent.py` AIAgent is initialized
- Check model availability (API key, rate limits)
- Check context window — if full, session needs compression

### 5. Boot Log Shows "No module named 'tools.X'" / MCP Registers 0 Tools
Seen 2026-08-11 (commit bfa8fbbce): after a "super-clean base" strip + v0.20.0
plugin port, the gateway booted but silently lost features:
- `mazemaker` MCP server: `registered 0 tool(s) from 0 server(s)` (should be 34)
- Discord/Telegram PLUGINS fail to load (`Failed to load plugin` + ImportError)
- BUT the platforms themselves still work (gateway/platforms/discord.py is a
  different code path) — so Discord messaging alone does NOT prove health.

Diagnosis flow (in this order):
1. Read the FULL boot log: `journalctl -u daedalus-gateway --since ...` or
   `~/.daedalus/gateway.log` — grep for `No module named`, `Failed to load plugin`,
   `Traceback`.
2. DON'T assume credentials are stripped. Verify first:
   `grep -E 'DISCORD|TELEGRAM|ALLOWED' ~/.daedalus/.env | sed 's/=.*/=<set>/'`
3. Prove WHEN the damage happened — compare against the auto-backup commit
   (cron commits ~/auto-backup hourly):
   `git log --oneline -5 && git show <auto-backup-commit>:tools/schema_sanitizer.py`
   If the file is already missing in an auto-backup from BEFORE your own
   changes, your changes are NOT the cause.
4. Root cause class: the local branch references modules that never existed
   there — they only live in a release tag. Find them:
   `git ls-tree -r --name-only v2026.8.3 | grep -E 'schema_sanitizer|platforms/helpers|authz_mixin|whatsapp_identity'`
   Restore with: `git show v2026.8.3:tools/schema_sanitizer.py > tools/schema_sanitizer.py`
5. Check for missing registry API used by ported code (mcp_tool.py needs):
   `register_toolset_alias`, `get_toolset_for_tool`, `get_registered_toolset_aliases`,
   `get_toolset_alias_target`, `_generation` (bumps on every (de)register).
   grep the caller, then add the missing methods to tools/registry.py.

Verification (must re-run, not claim):
```bash
cd ~/.daedalus && ~/.daedalus/venv/bin/python -c "
from tools.mcp_tool import discover_mcp_tools
names = discover_mcp_tools()
print(len(names), 'MCP tools registered')"
# Expect: 34 MCP tools (mcp__mazemaker__* prefix!)
```
GOTCHA: registered MCP names are `mcp__mazemaker__mazemaker_recall` — a filter
like `n.startswith('mazemaker')` returns 0 even when everything works. Filter
on `mcp__mazemaker__` instead.

Then restart the gateway and confirm: `Connected` for discord+telegram AND
`loaded` plugin lines (no `Failed to load plugin`).

### 6. "Unauthorized user: None on discord" — NORMAL
This is the allowlist (`DISCORD_ALLOWED_USERS`) rejecting someone who isn't
allowed — NOT a token problem. No action needed. Only investigate if a
legitimate user stops getting responses.

## Key Files

| File | Purpose |
|------|---------|
| `gateway/run.py` | Main loop, slash commands, dispatch (351KB) |
| `gateway/session.py` | Conversation persistence |
| `gateway/delivery.py` | Message delivery to platforms |
| `gateway/hooks.py` | Hook system for events |
| `gateway/platforms/*.py` | Platform-specific adapters |
| `channel_directory.json` | Channel ID → name mappings |
| `gateway.pid` | Process ID file |
