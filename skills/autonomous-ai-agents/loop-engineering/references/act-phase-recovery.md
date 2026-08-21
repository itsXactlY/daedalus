# ACT Phase Recovery Patterns — When mazemaker MCP is Unavailable

When the mazemaker MCP server is unreachable (returns HTTP 502/503 or "3 consecutive failures"), the ACT phase of Tri-State Cadence cannot read `decision:rank-*` memories directly. This document provides alternative recovery paths.

## Recovery Priority Order

| Step | Action | Tool | Purpose |
|------|--------|------|---------|
| 1 | Check session_search for recent DECIDE phase outputs | `session_search(query="decision rank", limit=10)` | Find what decisions were written in recent cron runs |
| 2 | Read local decision files | `read_file ~/.hermes/loops/tri-state/decision_req_*.json` | Get decision instructions from filesystem |
| 3 | Verify cron job states | `read_file ~/.hermes/cron/jobs.json` | Check if jobs are already paused/superseded |
| 4 | Check loop runner log | `read_file ~/.hermes/loops/shared/loop_runner.log` | See execution history and phase timestamps |
| 5 | Verify service state directly | `systemctl --user status <name>` | Confirm in-place completions |
| 6 | Verify ports/networking | `ss -tlnp '( sport = :<port> )'` | Confirm services are bound correctly |
| 7 | Check file existence | `ls -la <path>` or `stat <file>` | Confirm artifact creation |

## Local Files to Inspect During Recovery

```
~/.hermes/loops/tri-state/
├── act_implement.py           # Current phase script
├── decision_req_*.json         # DECIDE phase outputs (last 24h)
├── discovery_seed_*.json       # DISCOVER phase seeds
└── measure_converge.py         # MEASURE phase script

~/.hermes/cron/
└── jobs.json                   # All cron job states and configs

~/.hermes/loops/shared/
└── loop_runner.log             # Execution history (timestamps, phases)
```

## Example Recovery Flow (2026-06-15)

ACT phase detected mazemaker unreachable. Recovery steps executed:

1. **session_search** found DECIDE phase outputs from 2026-06-14 and 2026-06-15
2. **read cron/jobs.json** confirmed `pulse-wurm-everything` (d60932b331b4) already paused
3. **systemctl --user status** confirmed bridge listening on 0.0.0.0:8769
4. **ss -tlnp** verified port binding: `0.0.0.0:8769` (correct)
5. **file checks** confirmed Weather Organism prototype and iterate_350.py exist

## Palace-Specific Recovery (2026-06-15)

When checking Palace status during dream garden dispatches:

| State | Check | Confirmed Recovery |
|-------|-------|-------------------|
| Palace status | `palace/state.json` + `palace/audit.log` + `palace/dream_disp_state.json` | ✅ Confirmed operational |
| Discord gateway alive | `ss -tlnp \| grep -E "(discord\\|11435)"` or curl localhost port | ✅ Process running |
| Pre-run dispatch completion | Script output showing "HTTP 200" + state file recent timestamp | ✅ Already dispatched |

**Key files for Palace verification**:
- `palace/dream_disp_state.json` — dispatch timestamps and insight counts
- `palace/audit.log` — creation events and application lifecycle
- `palace/manifest.json` — channel ID mappings and role assignments
- `discord-outbox/` — check for report files with correct channel ID

If pre-run script shows HTTP 200, dispatch already completed — no new message needed unless threshold crossed.

## Writing Results Recovery

When mazemaker is down, the ACT phase should:
- Complete actionable items that can be verified locally
- Write findings to its final response (cron auto-delivery)
- Include `[MAZEMAKER_UNAVAILABLE]` marker for later reconciliation
- Next successful mazemaker call should write `ops:tick-<date>-recovery` with what was accomplished

## Typical Blocked States to Check

| State | Check | Confirmed Recovery |
|-------|-------|-------------------|
| Cron decommission | `jobs.json` - `enabled: false` + `paused_reason` set | ✅ Already done |
| Bridge bind fix | `systemctl status` + `ss -tlnp` | ✅ Already done |
| Skill creation | File exists at `~/.hermes/skills/<path>/SKILL.md` | ✅ Already done |
| Service config | Override file exists + systemd daemon-reload needed | ⚠️ Requires `systemctl --user daemon-reload && systemctl --user restart <service>` |