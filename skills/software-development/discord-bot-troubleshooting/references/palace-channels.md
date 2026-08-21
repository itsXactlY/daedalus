# Palace Channel Reference (Rabbithole Backup Server)

## The Architect's Palace Channels

When operating in the Palace context, these channels are available:

| Channel | ID | Purpose |
|---------|-----|---------|
| #dream-garden | 1497265517013237902 | Daily/weekly insights, consolidation, stale task cleanup |
| #throne-room | 1497265474981855253 | Primary admin command center |
| #war-room | 1497265480006635561 | Incident response |
| #observatory | 1497265484985532447 | Observatory/monitoring |
| #memory-vault | 1497265490370891836 | Memory vault |
| #forge | 1497265495596859403 | Development/creation |
| #gatehouse | 1497265500730691756 | Entry point |
| #messenger-hall | 1497265506577547384 | Outgoing messages |
| #dungeon | 1497265511417774151 | Quarantine/debugging |

## Palace Roles

- Palace Architect (admin)
- Palace Steward (bot role - The Architect has this)
- Palace Warden, Scribe, Smith, Oracle

## Cron Job Pattern

Dream garden insights cron (`dream-garden-insights`) runs every 3 hours:
1. Pre-run script dispatches to #dream-garden with current stats
2. Verify dispatch via HTTP status (200 = success)
3. Check `mazemaker_dream_stats` for insight growth
4. Threshold: +1000 insights since last report triggers garden update

State tracked in: `~/.hermes/palace/dream_disp_state.json`