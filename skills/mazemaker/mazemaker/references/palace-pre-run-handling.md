# Palace Verification & Pre-Run Handling

## Pattern Observed (2026-06-16)

Cron job `dream-garden-insights` has a pre-run script (`dream_disp.py`) that already dispatched when HTTP 200 is returned. The agent should:

1. **Verify Palace first**: `mcp__pulse__pulse_health` (pod liveness) + `mcp__mazemaker__mazemaker_dream_control` (dream engine status)
2. **Check dream stats**: `mcp__mazemaker__mazemaker_dream_stats` for current insight counts
3. **Compare to state file**: `~/.hermes/palace/dream_disp_state.json`
4. **Only act if threshold crossed AND pre-run didn't already dispatch**

## State File Fields (Verified)

```json
{
  "last_post": "2026-06-16T10:36:55+00:00",
  "cycles_posted": 32,
  "last_total_insights": 12251521,
  "palace_status": "operational"
}
```

## Outbox File (Verified)

`~/.hermes/discord-outbox/dream-garden_1497265517013237902.md` - Single report format

## Key Insight

Pre-run script output `HTTP 200` means dispatch already happened. No need to redundantly post. When the +1000 threshold was met by pre-run dispatch, the agent should check if genuinely new info exists beyond the pre-run's output before responding.