---
name: cron-job-discord-delivery
category: devops
description: How to deliver cron job results to Discord channels — the deliver mechanism, not send_message
version: 1.0.0
---

# Cron Job → Discord Delivery

The correct pattern for sending scheduled job results to Discord channels.

## The Problem

Cron jobs **cannot use `send_message`**. The scheduler explicitly disables the `messaging` toolset:

```python
# cron/scheduler.py:419
disabled_toolsets=["cronjob", "messaging", "clarify"]
```

This prevents recursive messaging, but means `send_message` is unavailable to cron agents.

## The Wrong Approaches (that will fail)

- ❌ Writing to `~/.hermes/discord-outbox/` — nobody reads it, files pile up forever
- ❌ Calling `send_message` — tool is filtered out, agent will say "not available in this context"
- ❌ Making raw Discord API calls via `urllib`/`curl` — works sometimes but fragile, no error handling
- ❌ Hallucinating a "403 Forbidden" and writing to outbox as fallback — this is what bad models do

## The Correct Approach: `deliver` Mechanism

The cron scheduler has a built-in delivery system. Configure it with:

```python
# When creating/updating a cron job:
cronjob(
    action="create",
    prompt="... your task. Put your report as your final response — it will be auto-delivered.",
    deliver="discord:1485340236316807278",  # channel ID
    schedule="every 60m"
)
```

### How It Works

1. Agent runs, does work, produces a final response
2. Scheduler captures the final response
3. Scheduler calls `_send_discord()` (same REST API as `send_message`)
4. Message posts to the target channel as "The Architect" (bot)

### Deliver Target Formats

| Target | Effect |
|--------|--------|
| `"local"` | Print to stdout only (default) |
| `"origin"` | Send back to wherever triggered the job |
| `"discord:CHANNEL_ID"` | Send to specific Discord channel |
| `"telegram:CHAT_ID"` | Send to Telegram chat |
| `"discord:CHANNEL_ID:THREAD_ID"` | Send to Discord thread |

### Cron Job Prompt Pattern

```
You are an autonomous agent running [task description].

Your task:
1. [do the work]
2. Format results as your final response

Do NOT try to use send_message — it's not available in this context.
Do NOT write files to discord-outbox/ — that directory is dead.
Do NOT make raw Discord API calls.
Just output your report as your final message — the scheduler handles delivery.
```

### Verification

Check delivery succeeded:
```bash
# Recent messages in the target channel
python3 -c "
import aiohttp, asyncio
async def check():
    headers = {'Authorization': 'Bot TOKEN'}
    url = 'https://discord.com/api/v10/channels/CHANNEL_ID/messages?limit=3'
    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers=headers) as r:
            for m in await r.json():
                print(f\"{m['timestamp']} {m['author']['username']}: {m['content'][:100]}\")
asyncio.run(check())
"
```

## Key Insight

The `deliver` field is the right path for **agent-driven posts** — when an LLM cron job's final response is the message you want shipped. For everything else (script-driven conditional posts, manual delivery from tooling, raw API access), see the "Script-Driven Delivery" section above. Don't reach for `send_message` (filtered out), `discord-outbox/` (dead directory), or outbox-as-fallback patterns (hallucination bait).

## Pattern: Script-Driven Delivery (raw curl is legitimate here)

The "raw curl is wrong" rule applies to **agent-driven posts** — when an LLM cron job's final response is being delivered. For **script-driven cron jobs** (jobs that have a `script` field set, regardless of `no_agent`), raw curl is the correct pattern because the script — not the scheduler — owns the decision logic.

**Why scripts bypass the deliver mechanism:**
- Conditional posts based on stats/thresholds (only post if growth > N)
- Multi-source aggregation (combine data before posting)
- Stateful de-duplication (skip if same payload already posted recently)
- The deliver field only ships the agent's final text response — it can't conditionally skip

**Example pattern (`~/.hermes/scripts/dream_disp.py`):**
```python
DREAM_GARDEN_ID = "1497265517013237902"

def post_to_discord(content):
    token = subprocess.check_output(
        "grep DISCORD_BOT_TOKEN ~/.hermes/.env | cut -d= -f2-",
        shell=True, text=True
    ).strip()
    result = subprocess.run([
        "curl", "-sS", "-w", "\\nHTTP:%{http_code}",
        "-X", "POST",
        f"https://discord.com/api/v10/channels/{DREAM_GARDEN_ID}/messages",
        "-H", f"Authorization: Bot {token}",
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"content": content[:1900]})
    ], capture_output=True, text=True, timeout=30)
    return 200 if "HTTP:200" in result.stdout or '"id"' in result.stdout else 0
```

**Key differences from the deliver mechanism:**
| Aspect | `deliver` field | Script-driven curl |
|---|---|---|
| Decision authority | Scheduler (always sends final text) | Script logic (conditional) |
| Token source | Internal scheduler config | `~/.hermes/.env` (DISCORD_BOT_TOKEN) |
| Retry handling | Scheduler handles | Script returns 0/200, caller decides |
| Best for | Reports, digests, cron output | Stateful, conditional, aggregated posts |

When auditing a cron job: check whether the prompt has logic ("if growth > N, post...") — if yes, it's likely script-driven, not deliver-driven. The `last_delivery_error` field reflects the **scheduler's** delivery attempts (the agent's final response), NOT the script's posts. To verify script-driven posts, check the script's own state file (usually `~/.hermes/palace/<job>_state.json` for palace jobs).

## Verification: After a Config Change

After editing a cron job's `deliver`, `model`, or other fields, **force-run it to verify the change took effect**:

```
cronjob(action="run", job_id="<job_id>")
```

This queues the job for immediate execution (sets `next_run_at` to ~now). Then poll `cronjob(action="list")` — `last_run_at`, `last_status`, and `last_delivery_error` should reflect the new run. Watch for `next_run_at` advancing past the run time (the scheduler bumps it after firing).

**Caveat for script-driven jobs:** force-run alone won't tell you if the Discord channel works — the script may legitimately skip the post (no new insights, threshold not crossed, etc.). The `last_run_at` will update and `last_status` will be `ok` regardless. **Always probe the channel directly** to validate the channel ID before relying on the cron job:

```bash
TOK=$(grep DISCORD_BOT_TOKEN ~/.hermes/.env | cut -d= -f2-)
curl -sS -w "\nHTTP:%{http_code}\n" \
  -X POST "https://discord.com/api/v10/channels/<CHANNEL_ID>/messages" \
  -H "Authorization: Bot $TOK" \
  -H "Content-Type: application/json" \
  -d '{"content":"verification test"}'
```

If HTTP 200 + a message ID comes back, the channel ID is valid and the bot token has access. Send a recognisable test message so the operator can delete it from the channel later if they want.

## Pitfall: Stale `last_delivery_error` field

The `last_delivery_error` string in `cronjob(action='list')` output is the LAST EVER recorded delivery error — it does not clear on subsequent success. A 404 from a transient hiccup days ago will keep showing up forever, even when the job is healthy. This produces false-positive "channel is gone" diagnoses.

When triaging a suspected broken cron delivery:
- DO NOT read `last_delivery_error` as a current-state signal
- DO probe the channel directly: `curl -sS -w "\nHTTP:%{http_code}" "https://discord.com/api/v10/channels/$CH" -H "Authorization: Bot $TOKEN"`
- DO read the most recent run's output file at `~/.hermes/cron/output/<job_id>/`
- DO check `last_status` (per-run) and ignore `last_delivery_error` unless `last_status: "error"` for the most recent run

See `discord-bot-troubleshooting` skill → "Stale `last_delivery_error` in cron listings" for the full diagnostic flow.
