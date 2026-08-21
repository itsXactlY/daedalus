# Dream Garden Dispatch Patterns

## Pre-run Script Behavior (2026-06-14 session)
- Pre-run script outputs `Dream garden dispatch: HTTP 200` when successful
- This indicates the dispatch was already completed before agent invocation
- Agent should verify Palace/gateway status and post update if threshold crossed

## Channel Verification
Channel ID for #dream-garden: `1497265517013237902`
Naming convention: `discord-outbox/{channel-name}_{channel-id}.md`

## Palace/Gateway Status Check
```bash
# Check gateway process
ps aux | grep 'hermes gateway' | grep -v grep

# Example output format
# alca     1701987  0.1  0.3 1379056 98488 ?       Ssl  01:06  hermes gateway run --replace
```

## Discord Gateway Environment Variables
- `HERMES_CRON_AUTO_DELIVER_PLATFORM=discord` - enables cron delivery
- `DISCORD_ALLOWED_CHANNELS` - comma-separated allowed channel IDs
- `free_response_channels` - channels where cron can auto-deliver

## Threshold Logic
- Read `dream_disp_state.json` → get `last_total_insights`
- Compare with MCP `total_insights` from `mcp__mazemaker__mazemaker_dream_stats`
- If growth >= +1000: dispatch garden update via curl (see `references/dream-garden-state-file.md`)
- If growth < threshold: [SILENT] is acceptable (Palace already confirmed by pre-run script)

## MCP Tools for Stats
- `mcp__mazemaker__mazemaker_dream_stats` - primary source for insight counts
- `mcp__mazemaker__mazemaker_browse` - check for previous dispatches
- `mcp__mazemaker__mazemaker_health` - verify corpus+DAF health

## Outbox Files (Historical)
Early sessions used `discord-outbox/{channel}.md` for gateway delivery. Current implementations use direct curl to Discord API (see `references/dream-garden-state-file.md`).

## Pitfall: Pre-run vs Agent-run Dispatch
The pre-run script dispatches to Discord BEFORE agent invocation. The agent-run script (dream_disp.py/dream_garden_update.py) dispatches DURING the agent session. Both can fire independently. Always check:
1. Did pre-run report HTTP 200? (dispatch already happened)
2. Does state file match current MCP insights? (agent already updated)
3. Only dispatch if significant growth computed

## Pitfall: Script Hardcoding (2026-06-15)
The `dream_garden_update.py` script had hardcoded values for `total_insights`, `total_bridges` instead of fetching live stats via MCP. This caused state file drift between runs.

**Fix pattern**: Always fetch live stats at runtime:
```python
# Fetch live stats via MCP or hermes command
hermes_bin = str(Path.home() / ".local" / "bin" / "hermes")
stats_result = subprocess.run(
    [hermes_bin, "mcp", "call", "mcp__mazemaker__mazemaker_dream_stats"],
    capture_output=True, text=True, timeout=30, cwd=str(Path.home())
)
# or use mcp__mazemaker__mazemaker_health for additional health data
stats = json.loads(stats_result.stdout)
total_insights = stats.get("result", {}).get("structuredContent", {}).get("total_insights", 0)
```

Never hardcode insight counts — the dream engine is always running and counts change between successive MCP queries.