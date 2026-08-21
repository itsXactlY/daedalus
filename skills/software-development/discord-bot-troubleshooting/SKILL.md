---
name: discord-bot-troubleshooting
description: Systematic approach to diagnose and fix Discord bot connectivity and responsiveness issues in the Daedalus agent environment
category: software-development
---

# Discord Bot Troubleshooting Skill

## When to Use
When a Discord bot appears to be offline, not responding, or not working properly despite being configured.

## Prerequisites
- Access to Hermes agent environment
- Discord bot token configured in `~/.hermes/.env`
- Basic familiarity with Linux command line

## Step-by-Step Approach

### 1. Verify Environment Variables Are Loaded
The most common issue: Discord bot token not being loaded from `.env` file.

```bash
# Check if .env file exists and contains token
cat ~/.hermes/.env | grep DISCORD

# Load environment variables properly
export $(grep -v '^#' ~/.hermes/.env | xargs)

# Verify the token is loaded
echo $DISCORD_BOT_TOKEN | head -c 10  # Should show first 10 chars
```

### 2. Start Gateway with Proper Environment
Ensure the gateway starts with loaded environment variables:

```bash
# Method 1: Source venv and export then run
cd /home/alca/.hermes
source hermes-agent/venv/bin/activate
export $(grep -v '^#' .env | xargs)
hermes gateway run --replace

# Method 2: Direct path with explicit python
cd /home/alca/.hermes/hermes-agent
source ../hermes-agent/venv/bin/activate
export $(grep -v '^#' ../../.env | xargs)
python hermes_cli/main.py gateway run --replace
```

### 3. Verify Bot Connection in Logs
Watch for these key indicators in `~/.hermes/logs/gateway.log`:

✅ **Successful connection signs:**
- `Connecting to discord...`
- `logging in using static token`
- `Shard ID None has connected to Gateway`
- `[Discord] Connected as [BotName]#[Tag]`
- `[Discord] Synced X slash command(s)`
- `✓ discord connected`
- `Gateway running with 2 platform(s)`

### 4. Test Bot Responsiveness
During the gateway runtime (typically ~60 seconds due to built-in timeout):

**In Discord:**
- Send a **direct message** to the bot (often required first)
- Use the exact bot name/tag as shown in logs
- Try **slash commands** by typing `/` in a server where bot is present
- If `require_mention: true` in config, you must `@mention` the bot in servers

**Expected responses:**
- Bot shows "thinking..." status
- Executes commands like `/help`, `/status`, `/reset`, `/sethome`
- Returns appropriate feedback messages

### 5. Common Configuration Checks
Verify these in `~/.hermes/config.yaml` under `discord:` section:
- `require_mention: true` (bot won't respond to unmentioned messages in servers)
- `auto_thread: true` (creates threads for conversations)
- `free_response_channels: ''` (leave empty unless specific channels)

Environment variables to verify in `~/.hermes/.env`:
- `DISCORD_BOT_TOKEN=your_token_here`
- `DISCORD_HOME_CHANNEL=channel_id_here` (optional)
- `DISCORD_ALLOWED_USERS=user_id_here` (optional)

### 6. Permission Requirements
Ensure bot has these Discord permissions:
- Read Messages/View Channels
- Send Messages
- Use Application Commands (for slash commands)
- Read Message History (if reading past messages)
- If bot appears offline: Check application not reset/reinvited needed

### 7. Troubleshooting Flow
If bot still not responding:

1. **Check logs immediately after startup** for auth/connection errors
2. **Verify exact bot name/tag** - case sensitive, include discriminator (`#3295`)
3. **Test in DM first** - many bots require DM initiation
4. **Check server permissions** - bot may lack needed permissions
5. **Look for rate limiting** in logs if spamming commands
6. **Verify intents** - bot may not be subscribed to message events

## Stale `last_delivery_error` in cron listings (false-positive trap)

**Symptom:** `cronjob(action='list')` shows a job with `last_status: "ok"` AND a non-null `last_delivery_error` field simultaneously. Easy to misread as "the last run failed to deliver" — almost always wrong.

**Why it's misleading:** The `last_delivery_error` field is the LAST EVER recorded delivery error, not the most recent run's outcome. It does not clear when a subsequent run succeeds. A single transient 404 from days/weeks ago will keep showing up in the list forever, even when the job has been delivering fine ever since.

**Real example (2026-06-17):** dream-garden-insights (e7f349c74358) showed:
```
last_status: "ok"
last_delivery_error: "delivery error: Discord API error (404): Unknown Channel"
```
The 404 was stale. Direct Discord API call on the script's target channel returned HTTP 200, the most recent run's output file showed HTTP 200 from the pre-run script, and the operator's screenshot of #dream-garden showed fresh posts landing every 180m. The job was healthy; the error string was leftover history.

**Mandatory verification before concluding a cron delivery is broken:**

1. **Probe the channel directly via Discord REST API** — this is the source of truth, not the cron list:
   ```bash
   TOKEN=$(grep '^DISCORD_BOT_TOKEN=' ~/.hermes/.env | cut -d= -f2-)
   CHANNEL_ID=<id from cron job's deliver target or script>
   curl -sS -w "\nHTTP:%{http_code}\n" \
     "https://discord.com/api/v10/channels/$CHANNEL_ID" \
     -H "Authorization: Bot $TOKEN"
   ```
   HTTP 200 = channel exists, bot has access. HTTP 404 = channel ID wrong or channel deleted.

2. **Read the most recent output file** at `~/.hermes/cron/output/<job_id>/` — the most recent `*.md` shows what actually happened in the last run (script output + agent response).

3. **Check the channel visually** — ask the operator for a screenshot or list recent messages via Discord API. If fresh posts are landing, delivery is working.

4. **Check `last_status` as the primary signal** — it reflects the most recent run. `last_delivery_error` is a footnote, not a verdict.

**Only conclude "delivery is broken" if ALL three of these agree:**
- Cron list `last_status: "error"` for the most recent run
- Direct API call on the target channel returns 4xx/5xx
- Most recent output file shows a failure (no HTTP 200 in the script section, agent response reports failure)

If the cron list says error but the API call succeeds and recent output files show success, the error is stale — investigate whether the cron tracker's `last_delivery_error` should be cleared on subsequent success (this would be a hermes-internal fix; not a Discord-side issue).

## Key Learnings from Experience
- Environment variables from `.env` **must be explicitly loaded** - they don't auto-load
- Gateway has built-in timeout (~60 seconds) - not a malfunction
- Bot connection and command syncing in logs **proves** it's working
- Lack of visible response often means **incorrect interaction method** (wrong channel, not DMing first, not using exact name, missing mention)
- Successful connection logs show: connected → synced commands → ✓ discord connected
- The **most valuable diagnostic** is watching the gateway logs in real-time during startup
- **Never trust `last_delivery_error` alone as a current-state signal** — verify with direct API call + recent output file + operator-visible channel state. False-positive "channel is gone" diagnoses waste operator attention and erode trust.
- **External API hard caps are gateway-killers if the calling wrapper doesn't catch them** — apply the two-layer pattern (pre-flight trim + sentinel-returning mutation helper) for any wrapper that could hit a 4xx cap error mid-loop. See `references/discord-slash-command-100-cap.md` for the worked example.

## Slash command sync failure modes (100-command cap, sync crashes)

The Discord adapter in `plugins/platforms/discord/adapter.py` syncs slash commands on connect via `_safe_sync_slash_commands`. Discord enforces a **hard cap of 100 global application commands per app** — and historically a single hit took down the entire gateway task.

**Symptom** (real user incident 2026-06-18 00:10:56 CEST):
```
discord.errors.HTTPException: 400 Bad Request (error code: 30032):
  Maximum number of application commands reached (100).
  File "adapter.py", line 1326, in _safe_sync_slash_commands
    await mutate(http.upsert_global_command, app_id, desired)
  ...
  File "adapter.py", line 1134, in _run_post_connect_initialization
    raise  # ← kills the gateway
```
`hermes gateway status` shows the service as `active (running)` but on the OLD code path (`plugins/platforms/discord/adapter.py`, the pre-restructure layout) the gateway task is dead — Discord stops responding entirely until manual restart.

**Important — symptom depends on which code path is running.** The fork and upstream have diverged (the fork restructured to `gateway/platforms/discord.py`). On the NEW code path (fork/main, current upstream main), `_run_post_connect_initialization` has a broad `except Exception` that catches 30032 and keeps the gateway alive — the log is just noisy. On the OLD code path (stale local checkouts, pre-restructure plugins folder), the gateway actually dies. Verify which path is running before claiming "the gateway died" — check `git log -1 --format=%h -- plugins/platforms/discord/adapter.py gateway/platforms/discord.py` to see which file exists on the deployed commit.

**Root cause:** Two nested try/except blocks in `_run_post_connect_initialization`:
- The inner `try` catches `Exception` but only handles rate-limits (HTTP 429) — everything else re-raises.
- The outer `try` only catches `asyncio.TimeoutError` and `asyncio.CancelledError` — so the re-raise propagates out and the gateway task dies.

**Trigger conditions (any one is enough on a fresh install or after adding plugins):**
- Many plugins auto-register slash commands
- Heavy `COMMAND_REGISTRY` entries
- The consolidated `/skill` group (supports up to 25 categories × 25 skills = 625 slots)
- Race between `fetch_commands()` and `upsert_global_command()` (cap reached between the two calls)
- Manual registration via the Discord UI pushed the app to 100 from another process

**The two-layer resilience fix** (apply both — the upstream #46078 registration-time cap is necessary but NOT sufficient):

1. **Pre-flight trim** (defense): when `tree.get_commands()` already returns >100 commands, drop the lowest-priority entries (existing commands kept first, sorted by name) BEFORE any upsert. The API is never called in a state we know will fail. Drops are silent (no API call), so `summary["skipped"]` stays 0 — the proof is that the dropped commands never appear in `upsert_global_command.await_args_list`.

2. **Mutation-level swallow** (resilience): the `mutate()` closure inside the sync catches the cap error, returns a sentinel object instead of raising, and the loop counts that op as `skipped`. The gateway stays alive.

Detection: `_is_discord_command_cap_error(exc)` matches `exc.code == 30032` (preferred — set by discord.py) with fallback to `response.status == 400` + the literal text "Maximum number of application commands reached". Catches `Exception` broadly in `mutate()` so the test environment (where `discord.HTTPException` is a MagicMock attribute, not a real exception class) doesn't break the except clause.

**Summary dict surface (so callers can see the degraded sync, not be surprised by it):**
- `kept` — number of commands the sync actually tried to keep (≤ cap, ≤ desired)
- `skipped` — number of API calls that hit the cap mid-sync
- `capped` — `True` iff any part of the sync was constrained by the cap
- `total` — original desired set size (pre-trim), for the warning log

The caller in `_run_post_connect_initialization` logs a single concise warning when `capped=True` instead of crashing.

**Verification on a live gateway after deploying the fix:**
```bash
journalctl --user -u hermes-gateway.service -n 200 --no-pager | grep -E "(30032|capped|hit the.*command cap)"
# Expected: ZERO matches after the fix is in. If you see "kept=100 skipped=N" in a
# warning, the cap was hit but the gateway survived — that's the soft-fail path.
```

**Upstream context:** `NousResearch/hermes-agent` PR #46078 (`5e851bc6b fix(discord): cap slash commands at Discord's 100-command limit`, merged 2026-06-14) caps REGISTRATION (so `tree.get_commands()` never returns >100 commands on a fresh install). It does NOT make the sync RESILIENT if 30032 ever surfaces. Both layers are needed — pull upstream first, then apply this resilience layer on top.

For the full implementation pattern, the test fixtures, and the exact code shape, see `references/discord-slash-command-100-cap.md` in this skill.

## LLM API errors surfacing in Discord (raw 4xx in chat)

**Symptom:** Discord shows a raw LLM provider error message as the bot's reply — e.g. `Error code: 400 - {'error': {... 'message': 'Model name not specified, model name cannot be empty (request id: 20260618203718398085375cRyUPLVk)'}}` or `HTTP 429: Rate limit exceeded`. The bot is "up" and connected, but its reasoning layer is failing and Discord is faithfully rendering the error text. Two flavours:

- **Live conversation failure:** the user just typed a message in a Discord channel, the bot tried to answer, the LLM call failed, the raw error got posted as the response.
- **Cron-driven failure delivered to Discord:** a scheduled job's `deliver` field ships the failed agent's final error text straight to a channel. Looks identical from the user's seat.

**The diagnostic trace path (works for both flavours):**

1. **Grab the request_id from the Discord message** — provider error text usually ends with `(request id: <hex-ish id>)`. Grep `errors.log` and `agent.log` for that string to isolate the exact matching call.
2. **Find the session_id from the matching log line** — it's in brackets at line start, e.g. `[20260618_223705_6cecd4de]`. That brackets the call that produced the Discord-visible error.
3. **Read `errors.log` and `agent.log` lines tagged with that session_id** to see the immediate predecessor log line — it almost always names the root cause directly. Common predecessor strings:
   - `Credential pool provider mismatch: pool=<X>:<Y>, agent=<X> — skipping pool mutation to avoid cross-provider contamination` → then `model=` ends up empty in the API call (hermes-agent code bug)
   - `model= summary=HTTP 400: Model name not specified...` (literally empty model field) — see root causes below
   - `Request timed out.` — different fix path, look at `agent.api_max_retries` and provider latency
4. **Trace the source: live session or cron?** — session_ids with the `cron_<jobid>_<timestamp>` shape came from a scheduled job; everything else is a live gateway-launched conversation. For cron, get the job_id and check `~/.hermes/cron/jobs.json` for `model`/`provider` fields.

**Root cause 1: credential pool provider mismatch (hermes-agent bug)**

The session launches with `provider=custom` (legacy/old path) but the credential pool is keyed under `custom:rapeit`. The pool-lookup code logs the mismatch and refuses to mutate the pool ("to avoid cross-provider contamination"). Side effect: the `model=` string never gets set on the API call, so it goes out empty and the provider returns 400.

This hits the GATEWAY code path specifically — CLI sessions (e.g. `hermes chat -m MiniMax-M3 --provider rapeit`) work fine because they pass the provider explicitly. The fix is in `hermes-agent`'s `run_agent` pool-lookup code; the lookup should fall back to `config.model.default_model` when pool mismatch happens, instead of skipping the mutation.

Workaround until the upstream fix lands: ensure any agent that gets routed through the gateway has a non-default provider that matches the pool key — i.e. don't rely on bare `custom`, pass an explicit provider name.

**Root cause 2: cron job with `model=None, provider=None` after a provider migration**

The 2026-06-17 MiniMax-M3 migration on rapeit updated some cron jobs' `model`/`provider` fields and missed others. Symptom in `~/.hermes/cron/jobs.json`:

```json
{
  "job_id": "e7f349c74358",
  "name": "dream-garden-insights",
  "model": null,        // <-- should be "MiniMax-M3"
  "provider": null,     // <-- should be "rapeit"
  "last_status": "error"
}
```

When such a job fires, the conversation_loop has no model to set on the API call → 400. Verify by reading the file directly:

```bash
python3 -c "
import json
data = json.load(open('/home/alca/.hermes/cron/jobs.json'))
jobs = data if isinstance(data, list) else data.get('jobs', [data])
for j in jobs:
    m, p = j.get('model'), j.get('provider')
    flag = ' BREAK' if m is None or p is None else ''
    print(f\"  {j.get('job_id','?')[:8]}  {j.get('name','?'):32}  model={m}  provider={p}{flag}\")
"
```

Fix each broken job with:

```
cronjob(action="update", job_id="<job_id>", model={"model":"MiniMax-M3","provider":"rapeit"})
```

Then `cronjob(action="run", job_id="<job_id>")` to force-run and verify.

**Root cause 3: missing prefill file (collateral damage from a config edit)**

`config.yaml` has `agent.system_prompt` and `prefill_messages_file: prefill.json` configured, but the file is missing. The next config reload logs `Prefill messages file not found: /home/alca/.hermes/prefill.json` and silently drops the system_prompt + prefill on the floor. The bot then runs without the override you intended.

Common cause: a config-replace or git checkout operation renamed the file (e.g. `prefill.json` → `prefill_.json` with a trailing underscore). Verify:

```bash
ls -la ~/.hermes/prefill*.json
```

If only the underscored variant exists, restore the link the config expects: `mv ~/.hermes/prefill_.json ~/.hermes/prefill.json` (or `ln -s prefill_.json prefill.json` if you want to keep both names).

**Verification after any of the above fixes:**

```bash
# Force-run the affected job (cron case) OR
# re-trigger the conversation by sending a Discord message (live case)

# Then grep the next 5 minutes of logs for the same error class
tail -F ~/.hermes/logs/errors.log | grep "Model name not specified\|provider mismatch"
# Expected: no new matches. If matches keep coming, escalate — the pool-mismatch
# bug might be in a code path the above fixes don't cover.
```

**Pitfall: the `cron-fleet-restore` job doesn't fix None model fields**

If `cronjob(action='list')` shows a one-shot "fleet restore" job (e.g. `cron-fleet-restore-2026-06-20` in 2026-06), it was designed to migrate `repeat`/`schedule` fields back to `*/15` after rate-limiting throttling. It does NOT patch `model`/`provider` on jobs that were left at `None` — those have to be fixed individually with `cronjob(action='update', job_id=X, model=...)`. Verify by reading the prompt of the restore job; if it only mentions `schedule` and `repeat`, it won't help with `model=None`.

### Cloudflare WAF Blocking (error code 1010)
**Symptom:** REST API calls to `discord.com/api/v10/` return 403 with body `error code: 1010`. Gateway WebSocket connection works (messages received) but `send_message` to Discord fails.

**Cause:** Cloudflare's WAF blocks datacenter IPs on Discord's REST API endpoints. The machine's IP is classified as a datacenter/cloud IP and is rejected at the Cloudflare layer before reaching Discord's servers.

**Diagnosis:**
```python
import os, json, urllib.request
env_text = open(os.path.expanduser("~/.hermes/.env")).read()
token = env_text.split("DISCORD_BOT_TOKEN=")[1].split("\n")[0]
req = urllib.request.Request(
    "https://discord.com/api/v10/users/@me",
    headers={"Authorization": f"Bot {token}"}
)
try:
    resp = urllib.request.urlopen(req)
    print("REST API works:", json.loads(resp.read()))
except Exception as e:
    print(f"REST API blocked: {e}")  # 403 + error code: 1010 = Cloudflare block
```

**Why WebSocket works but REST doesn't:**
- Gateway connects to `gateway.discord.gg` (WebSocket) — different Cloudflare endpoint, not IP-blocked
- `_send_discord()` in `tools/send_message_tool.py:489` makes direct REST POST to `discord.com/api/v10/channels/{id}/messages` — blocked by Cloudflare

**Impact:**
- `send_message(target="discord:...")` always fails from datacenter IPs
- Cron jobs writing to `discord-outbox/` as fallback — but **gateway does NOT process the outbox** (no outbox pickup code exists in gateway). Files pile up undelivered.

**Workaround:** Route Discord sends through the gateway adapter's `discord.py` client (WebSocket) instead of REST API. Or use a residential proxy. Or accept that cron jobs can't send to Discord from this IP.

### discord-outbox is a dead end
The `discord-outbox/` directory in `~/.hermes/` is written to by agents as a fallback when `send_message` fails, but the gateway has **zero code** that reads or processes files from this directory. It's not a delivery mechanism — it's a silent data graveyard.

## Verification Checklist
When troubleshooting, confirm:
- [ ] .env file contains `DISCORD_BOT_TOKEN`
- [ ] Environment variables loaded before starting gateway
- [ ] Gateway starts without import/module errors
- [ ] Logs show: connecting → logged in → gateway connected → synced commands
- [ ] Gateway shows "running with 2 platform(s)" (Telegram + Discord)
- [ ] You interact with bot using correct method during runtime window
- [ ] Bot shows "thinking..." when processing requests

## Recovery Procedure
If bot appears stuck or unresponsive:
1. Check logs for graceful shutdown indications
2. Restart with proper environment loading
3. Wait for "✓ discord connected" in logs
4. Immediately test interaction in Discord
5. Remember: Runtime limited to ~60 seconds by design

---

## Messaging Patterns (merged from `discord-messaging-via-hermes`, `discord-outbox-file-write`, `discord-outbox-messaging`, `discord-system-reporting`)

### Primary method: `send_message` tool

**ALWAYS use `send_message`** to post to Discord channels. Example:
```
send_message(target="discord:1485340236316807278", message="Your report content here")
```

**DO NOT** write files to `~/.hermes/discord-outbox/` — the gateway has zero code that reads from it (see "discord-outbox is a dead end" above). It's a silent data graveyard.

**DO NOT** make raw HTTP calls to the Discord API via `urllib.request` in Python — Discord returns HTTP 403 (error code 1010) due to Cloudflare blocking Python's default User-Agent. Use `curl` as fallback only when `send_message` is unavailable (see Cloudflare WAF section above).

### System health report format

When sending automated reports to Discord, use this markdown structure:
```
**Hermes Agent System Health Check**
⏰ Timestamp: [current timestamp]
🖥️ Host: [hostname]

**System Resources:**
• Disk Usage: [used]/[total] ([percent] used) [emoji]
• CPU Load: [1min], [5min], [15min] [emoji]
• Memory: [used]/[total] ([percent] used) [emoji]

**Services Status:**
• Hermes Gateway: [status]
• Ollama: [status]

**Notes:** [observations / recommendations]
**Next Check:** [time]
```

Use consistent emoji: ✅ normal, ⚠️ warnings. Keep under ~2000 chars.

---

## Channel Reference (merged from `discord-context-awareness`)

Key channels from the backup server:

**Primary reporting destinations:**
- **dev-control-room** (1485340236316807278) — Development control center. **WHERE ALL REPORTS SHOULD BE MADE.** Free response (no @mention needed).
- **admin-control** (1485339913430896883) — Primary admin command center.
- **ops-control-room** (1485339988215337192) — Discord home channel, ops hub.

**Trading channels:**
- **trading-command**, **trading-signals**, **trading-analysis**, **trading-risk**, **trading-news**, **trading-results**, **trading-backtests**, **trading-war-room**

**Development channels:**
- **dev-agent-jobs**, **dev-code-review**, **dev-debugging**, **dev-deployments**, **dev-test-runs**, **dev-planning**

**Feed channels:**
- **feed-system-health**, **feed-market-data**, **feed-external-alerts**, **feed-cron-reports**, **feed-agent-events**

**Palace channels (Rabbithole Server):**
- **#dream-garden** (1497265517013237902): Daily/weekly insights, consolidation.
- **#throne-room**, **#war-room**, **#observatory**, **#memory-vault**, **#forge**, **#gatehouse**, **#messenger-hall**, **#dungeon** — full mapping in `references/palace-channels.md`.

### Routing logic
- Development/code/status → `send_message(target="discord:1485340236316807278")`
- Trading ops/signals → `send_message(target="discord:<trading-channel-id>")`
- System alerts/incidents → `send_message(target="discord:1485339988215337192")`
- Research tasks → `send_message(target="discord:<research-channel-id>")`
- When in doubt, default to **dev-control-room** (1485340236316807278)

### Free response channels (Hermes can reply without @mention):
`admin-control`, `ops-control-room`, `trading-command`, `trading-analysis`, `trading-war-room`, `dev-control-room`, `dev-debugging`, `research-requests`