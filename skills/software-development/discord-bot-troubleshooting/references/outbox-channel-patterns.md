# Discord Outbox Channel Patterns & State File References

Documented patterns for outbox file naming conventions and state tracking observed in Palace operations.

## Channel ID Patterns

### Palace Channels (from palace_manifest.json)

| Channel | ID | Purpose |
|---------|-----|---------|
| #dream-garden | 1497265517013237902 | Background consolidation, insights, weekly state |
| #messenger-hall | 1497265506577547384 | Briefings, reports, announcements |
| #dev-control-room | 1485340236316807278 | Development/testing outbox (non-Palace) |

**Key insight**: The 1485340236316807278 ID appears to be a backup/development channel, while 1497265517013237902 is the official #dream-garden channel in the Palace guild.

## State File Pattern

For cron jobs that need to track "last seen" values (insight counts, timestamps, etc.):

**Location**: `~/.hermes/palace/<job_name>_state.json` or `~/.hermes/<category>/<job_name>_state.json`

**Fields typically tracked**:
```json
{
  "last_post": "2026-06-15T19:07:32+00:00",
  "last_total_insights": 10109720,
  "cycles_posted": 28,
  "palace_status": "operational"
}
```

## Pre-Run Dispatch Verification

When a cron job's prompt mentions "Script Output" from a pre-run script:

1. **First check the state file** - If it shows recent `last_post` timestamp, dispatch already happened
2. **Check outbox directory** - Multiple files may exist; use the most recent with the correct channel ID
3. **Verify insight delta** - State file's `last_total_insights` vs known previous values determines if +threshold was crossed

## File Naming Conventions

| Pattern | Example | Context |
|---------|---------|---------|
| `{channel-name}_{channel-id}.md` | `dream-garden_1497265517013237902.md` | Single report, overwrites |
| `{channel-name}_{channel-id}_{date}_{seq}.md` | `dream-garden_1485340236316807278_20260615_001.md` | Sequential reports, preserves history |

**When pre-run script already dispatched**: Look for HTTP 200 confirmation in the script output and check if the threshold condition (+1000 insights) was already satisfied. If so, respond with `[SILENT]` unless there's genuinely new information to report.