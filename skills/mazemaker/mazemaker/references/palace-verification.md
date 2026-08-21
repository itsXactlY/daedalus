## Palace Status Verification Pattern

When running cron jobs that post to Palace channels, ALWAYS verify both systems before dispatch:

1. **Pod liveness**: `mcp__pulse__pulse_health` → `{"status": "ok"}` = pod up
2. **Dream engine status**: `mcp__mazemaker__mazemaker_dream_control` → `{"running": "external"}` = dream worker active
3. **Dream stats**: `mcp__mazemaker__mazemaker_dream_stats` → `sessions`, `total_insights` for delta calculation

If ANY system reports degraded/failure, skip the outbox file write to avoid stale reports.

## State-Based Delta Detection

State file location: `~/.hermes/palace/dream_disp_state.json`

Key fields to track:
- `last_total_insights` - compare vs `mazemaker_dream_stats` → `total_insights`
- `last_post` - ISO timestamp of last successful dispatch
- `cycles_posted` - increment after successful report

Delta = current_total - last_total_insights

Only write outbox if delta >= +1000 threshold.

## Pre-Run Script Confirmation

Pre-run scripts output HTTP status in the Script Output block:
- `Dream garden dispatch: HTTP 200` = already dispatched, no redundant action needed
- Check outbox file `dream-garden_1497265517013237902.md` for content freshness
- Verify the state file was NOT updated by the pre-run (indicates no threshold met)

When pre-run already dispatched, the cron agent should respond with `[SILENT]` unless genuinely new information exists.