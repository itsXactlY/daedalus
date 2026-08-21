# Dream Garden Dispatch Pattern

A metrics-based autonomous loop that posts mazemaker dream insights to Palace's #dream-garden channel on a regular cadence.

## Trigger Structure

```yaml
trigger:
  source: cron (pre-run script + agent verification)
  cadence: every 6 hours
  threshold: +1000 insights growth since last dispatch
```

## Execution Flow

1. **Pre-run script** collects current dream stats and writes to outbox
2. **Agent verification** (this session):
   - Call `mcp__mazemaker__mazemaker_dream_stats`
   - Read `dream_disp_state.json` for `last_total_insights`
   - Calculate growth: `current - previous`
   - If growth > 1000: update outbox and state file
   - If growth <= 1000: respond `[SILENT]` or confirm no update needed

## State Management

**File**: `~/.hermes/palace/dream_disp_state.json`

```json
{
  "last_post": "2026-06-16T16:54:07+00:00",
  "last_total_insights": 12251521,
  "growth_since_last": 0,
  "threshold_crossed": false
}
```

## Outbox Format

**File**: `~/.hermes/discord-outbox/dream-garden_{CHANNEL_ID}.md`

The pre-run script writes here; the agent should verify/update stats before confirming delivery.

## Palace Integration

- **Channel**: #dream-garden (ID: 1497265517013237902)
- **Bot**: The Architect (ID: 928821955463905330)
- **Roles**: Palace Steward (bot), Palace Architect (user)
- **Verify**: Check `~/.hermes/palace/audit.log` and `~/.hermes/palace/palace_manifest.json`

## Session Pattern (Cron Agent)

```python
# 1. Check current stats
mcp__mazemaker__mazemaker_dream_stats()

# 2. Read previous state
read_file("~/.hermes/palace/dream_disp_state.json")

# 3. Compare and decide
if current_insights - previous_insights > 1000:
    # Update outbox with fresh stats
    write_file("discord-outbox/dream-garden_{CHANNEL_ID}.md", fresh_content)
    # Update state
    patch("dream_disp_state.json", ...)
else:
    # Silent pass
    return "[SILENT]"

# 4. Confirm Palace is operational
read_file("~/.hermes/palace/audit.log")
```

## Metrics to Track

| Metric | Source | Format |
|--------|--------|--------|
| total_insights | mazemaker_dream_stats.total_insights | integer |
| sessions | mazemaker_dream_stats.sessions | integer |
| bridge_insights | mazemaker_dream_stats.insight_types.bridge | integer |
| cluster_insights | mazemaker_dream_stats.insight_types.cluster | integer |
| dae_coverage | mcp__mazemaker__mazemaker_health.dae.coverage | float (0-1) |

## Pitfall: Stale Stats in Outbox

The pre-run script may write before the latest stats are available. Always verify `current_insights` from live MCP calls and update the outbox if growth > threshold. The HTTP 200 confirms delivery mechanism worked, but not necessarily that content was fresh.