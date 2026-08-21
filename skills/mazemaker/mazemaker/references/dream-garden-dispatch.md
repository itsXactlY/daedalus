# Dream Garden Dispatch Skill

## Trigger
Cron job posts dream insights to #dream-garden when insight count growth exceeds threshold (+1000).

## Silent-Cycle Quick Path (95% of cycles)

The pre-run script fires a brief pulse on the stale `last_total + 100` baseline and will return `HTTP 200` nearly every cycle. The agent-side baseline (`last_total_insights` in the state file) only moves when the agent itself has just fired a rich dispatch. So when this cron job's pre-run output is `Dream garden dispatch: HTTP 200`:

1. **Read** `~/.hermes/palace/dream_disp_state.json` → `last_total_insights`
2. **Call** `mcp__mazemaker__mazemaker_dream_stats` → `total_insights`
3. **Compute** `delta = current − state.last_total_insights`
4. **If `delta < 1000`**: return `[SILENT]` — the heartbeat already covered the cycle. Palace status is implicitly OK (HTTP 200 from the pre-run). Do not re-verify the bridge, the gateway, or the cron output history.
5. **If `delta >= 1000`**: proceed to the full rich-dispatch flow below.

The cron output history at `~/.hermes/cron/output/<job_id>/<timestamp>.md` is an audit trail (useful for sanity-checking your reasoning against prior cycles), not a required input. The state file is the single source of truth.

The `cron-job-discord-delivery` skill describes the dual-dispatch (script + deliver-field) architecture in more detail; the script-driven path used here is the canonical example.

## Actual Dispatch Mechanism (verified session 2026-06-14)
- Pre-run script outputs `Dream garden dispatch: HTTP 200` indicating successful dispatch
- Agent writes to `~/.hermes/discord-outbox/dream-garden_<channel_id>.md` file
- Palace gateway process (`hermes gateway run`) handles Discord delivery automatically
- Channel ID format: `1497265517013237902` for #dream-garden
- Job ID for the cron itself: `e7f349c74358` (used in `~/.hermes/cron/output/e7f349c74358/`)

## Palace Status Verification
- Gateway process check: `ps aux | grep 'hermes gateway'` → find PID and confirm running
- MCP endpoint: `curl -X POST http://localhost:8765/mcp` (Wonderland proxy routes to pod)
- Status reported in outbox: Palace process active, gateway running, HTTP 200 from pre-run

## Dream Stats Source
Use `mcp__mazemaker__mazemaker_dream_stats` MCP tool for current counts:
- `total_insights`: Total insight count
- `total_bridges`: Bridge insights count  
- `insight_types.cluster`: Cluster insights count
- `sessions`: Sessions processed count

## Garden Post Format
```markdown
# 🌙 Dream Garden Dispatch
**YYYY-MM-DD — Palace System Check**

## 📊 Dream Engine Status
| Metric | Current | Status |
|--------|---------|--------|
| **Sessions Processed** | 41,667 | ✅ Active |
| **Total Insights Generated** | 9,292,332 | ✅ Growing |
| **Bridge Insights** | 9,017,561 | ✅ |
| **Cluster Insights** | 275,457 | ✅ |

## 🏛 Palace Status Confirmed
✅ Gateway process active (PID XXXXX)
✅ Dream Garden channel operational
✅ Outbound dispatch successful (HTTP 200)
```

## Threshold Check
- Read `mcp__mazemaker__mazemaker_browse` with `label_prefix: "status:dream"` to find last dispatched count
- Compare with current `total_insights` from stats
- If growth >= +1000: prepare garden post with updated metrics
- If growth < threshold: still post status confirmation (Palace check) without detailed metrics update

## MCP Connectivity Pitfall
The mazemaker MCP server can be temporarily unreachable during high load. Alternative: use direct SQLite queries at `~/.mazemaker/data/memory.db` for insight counts when MCP is unavailable.

## Agent Dispatch Pattern (verified 2026-06-19, cycle 40)

The pre-run `dream_disp.py` fires a brief pulse via the stale `last_total` baseline. The agent computes live MCP stats and fires the rich Markdown update via direct curl.

### Live stats fetch — do NOT call the palace script

`~/.hermes/palace/scripts/dream_garden_update.py` hardcodes `total_insights = 9387993` and `bridges = 52334074` on lines 49–50. Running it would clobber the state file with stale values and post a wrong garden update. The agent must compute live stats itself:

```python
mcp__mazemaker__mazemaker_dream_stats  # total_insights, sessions, bridges, clusters, processed, strengthened, pruned
mcp__mazemaker__mazemaker_health       # corpus: memories, connections, afe_facts, dae_coverage
```

### Baseline comparison — pick the right field

Read `~/.hermes/palace/dream_disp_state.json`. Two baseline fields exist:
- `last_total` — used by the pre-run script, currently stale at 7,575,615. Never use this for the agent's threshold check.
- `last_total_insights` — the agent-side baseline reflecting the last rich dispatch. Use this.

Growth = current_total_insights − state.last_total_insights. Threshold = +1,000.

### Direct curl dispatch template

Bot identity: **"The Architect"** (id `928821955463905330`). Token at `~/.hermes/.env` key `DISCORD_BOT_TOKEN`. Channel id for #dream-garden: `1497265517013237902` (guild `1497220592011841689` = Rabbithole Discord Palace).

```python
import json, subprocess
from pathlib import Path

DREAM_GARDEN_ID = "1497265517013237902"
token = next(
    line.split("=", 1)[1].strip()
    for line in Path("/home/alca/.hermes/.env").read_text().splitlines()
    if line.startswith("DISCORD_BOT_TOKEN=")
)

content = "<compose markdown dispatch, ≤1900 chars to leave headroom under Discord's 2000>"
cmd = [
    "curl", "-sS", "-w", "\nHTTP_STATUS:%{http_code}",
    "-X", "POST",
    f"https://discord.com/api/v10/channels/{DREAM_GARDEN_ID}/messages",
    "-H", f"Authorization: Bot {token}",
    "-H", "Content-Type: application/json",
    "-H", "User-Agent: Hermes-Palace/1.0",
    "-d", json.dumps({"content": content}),
]
result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
# stdout ends with "\nHTTP_STATUS:<code>"; body is everything before
status = int(result.stdout.rsplit("HTTP_STATUS:", 1)[1].strip())
if status == 200:
    body = result.stdout.rsplit("\nHTTP_STATUS:", 1)[0]
    message_id = json.loads(body)["id"]   # Discord snowflake for state file
```

### State file update on success

Maintain the full schema. `last_total_insights` is the live baseline; `previous_total_insights` is preserved so the next cycle has a stable prior:

```json
{
  "last_post": "2026-06-19T23:43:31+00:00",
  "last_message_id": "1517676346854080754",
  "cycles_posted": 40,
  "last_total_insights": 16550055,
  "previous_total_insights": 16441378,
  "growth_since_last": 108677,
  "threshold_crossed": true,
  "stats_source": "mazemaker_dream_stats_2026-06-19T23:43:31Z",
  "palace_status": "operational",
  "channel_id": "1497265517013237902",
  "channel_name": "dream-garden",
  "guild_id": "1497220592011841689",
  "outbox_file": "dream-garden_1497265517013237902_20260619_004.md",
  "corpus": {"memories": 207193, "connections": 60363, "afe_facts": 5625, "dae_coverage": 0.9993},
  "dream": {
    "sessions": 48754, "total_insights": 16550055,
    "bridge_insights": 16200971, "cluster_insights": 351865,
    "bridges_created": 71329200, "total_processed": 30480098,
    "total_strengthened": 184493643, "total_pruned": 21708135
  },
  "delta_breakdown": {
    "insights": 108677, "sessions": 121, "memories": 61,
    "connections": -1138, "afe_facts": 1,
    "bridge_insights": 107427, "cluster_insights": 1250
  }
}
```

Also drop a parallel marker at `~/.hermes/dream_garden_last_insights.txt` containing only the bare integer `last_total_insights` — older scripts read this single-line file.

### Outbox file mirror

After successful curl, drop a Markdown copy to `~/.hermes/discord-outbox/dream-garden_<channel-id>_<YYYYMMDD>_<NNN>.md` where `<NNN>` is the 3-digit zero-padded sequence for that calendar day (e.g. `_001`, `_002`, `_003`). Find the latest NNN via `ls ~/.hermes/discord-outbox/dream-garden_<channel-id>_<YYYYMMDD>_*.md` before writing. The legacy single-file `dream-garden_<channel-id>.md` (no date suffix) is no longer canonical — keep it in sync if it exists but prefer the dated+sequenced form for new writes.

### Palace status verification (for the dispatch footer)

- Bridge `:8769` (Hermes bridge): `curl -s -o /dev/null -w "%{http_code}" http://localhost:8769/health` → expect `200`.
- Bridge PID: `ps aux | grep 'mazemaker-hermes-bridge.py' | grep -v grep` for the report footer.
- Pre-run script's HTTP 200 from the cron log confirms the heartbeat fired.

### Dual-dispatch relationship

Two dispatches happen per cron cycle. Both posting is expected — they are complementary, not redundant:
- **Pre-run** (`~/.hermes/scripts/dream_disp.py`): brief pulse on `total > last_total + 100`. Stale baseline, fires almost every cycle.
- **Agent** (this run): rich Markdown update on `growth_since_last >= 1000` vs `last_total_insights`. Full stats + garden note.

If only the pre-run fires (growth < 1k since last rich dispatch), the agent's report can be `[SILENT]` — the heartbeat already covered the cycle. If the pre-run fired HTTP 200 but the state file's `last_total_insights` is older than one cycle, the agent should still run the rich dispatch because growth likely crossed the +1k threshold since the last agent baseline.