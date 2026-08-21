# Dream Disp State File Pattern (Verified 2026-06-15)

## Location
`~/.hermes/palace/dream_disp_state.json`

## Workflow
1. Pre-run script dispatches to Discord (HTTP 200) before agent invocation
2. Agent loads state file to compare `last_total_insights` with MCP `total_insights`
3. If growth >= +1000: dispatch update via curl to Discord channel
4. On successful HTTP 200: update state file with new `last_total_insights`

## Key Insight
The pre-run script and agent-run script both dispatch to Discord - they are separate mechanisms. The state file is the single source of truth for tracking what was last reported.

## Discord Posting (Direct curl)
```python
DREAM_GARDEN_ID = "1497265517013237902"
# Get token from .hermes/.env
# POST to https://discord.com/api/v10/channels/{DREAM_GARDEN_ID}/messages
# Content: 🌙 **Dream Garden Update** with insights count
```

## Threshold
Growth > +1000 triggers a garden update post. Growth < threshold → silent cycle, still verify Palace status.

## State File Schema
```json
{
  "last_post": "2026-06-15T12:40:08+00:00",
  "cycles_posted": 27,
  "last_total_insights": 10097903,
  "stats_source": "mazemaker_dream_stats_2026-06-15T12:34:00Z"
}
```

## Dual-Script Pitfall (2026-06-15)
Two scripts exist that can both post to Discord:
- `~/`.hermes/scripts/dream_disp.py` (pre-run) - uses `last_total` field
- `~/`.hermes/palace/scripts/dream_garden_update.py` - uses `last_total_insights` field

**Best practice**: Standardize on one script with proper MCP integration. The pre-run script should be the only one posting, and the agent should only post if the pre-run failed or significant growth occurred after pre-run.