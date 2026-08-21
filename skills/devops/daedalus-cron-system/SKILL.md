---
name: daedalus-cron-system
description: How the Daedalus cron system works - scheduling, jobs, autonomous tasks
category: devops
version: 1.0
tags: [cron, scheduler, jobs, autonomous, daedalus]
priority: high
---


> Ported from `hermes-cron-system` during the 2026-08-21 Daedalus skills alignment. Pre-rename history lives in git and `~/.daedalus/skills-archive/2026-08-21-hermes-legacy/`.
# Daedalus Cron System

Autonomous task scheduling for Daedalus Agent.

## Location

```
~/.daedalus/cron/
├── scheduler.py    # Scheduler daemon
├── jobs.py         # Job definitions
├── .tick.lock      # Tick lock file
└── output/         # Job output storage
```

## How It Works

1. Scheduler reads job definitions from `jobs.py`
2. Each job has a schedule (cron-like or interval)
3. At trigger time, scheduler spawns a fresh agent session
4. Agent runs the job prompt autonomously
5. Output stored in `cron/output/`

## Job Types

| Type | Description |
|------|-------------|
| **Cron** | Fixed schedule (e.g., every hour, daily at 9am) |
| **Interval** | Every N minutes/hours |
| **One-shot** | Run once at specific time |

## Creating Jobs

Use the `cronjob` tool or add to `jobs.py`:

```python
# Via cronjob tool
cronjob(action='create', name='health-check', schedule='0 * * * *', 
        prompt='Check system health and report to Discord')

# Via jobs.py (persistent)
{
    'name': 'health-check',
    'schedule': '0 * * * *',
    'prompt': 'Check system health...',
    'skills': ['discord-system-reporting'],
    'model': 'xiaomi/mimo-v2-pro'
}
```

## Job Context

Cron jobs run in FRESH sessions with:
- No chat history
- No current conversation context
- Self-contained prompts only
- Skills loaded from `skills` list

## Skills On Jobs

Skills can be attached to jobs. They're loaded before the prompt runs.

**⚠️ KNOWN BUG:** Passing both `skills=[...]` and `repeat='forever'` in a single `cronjob(action='create')` call causes:
  `'<=' not supported between instances of 'str' and 'int'`
**Workaround:** Create without skills first, then `update` to attach:
```python
job = cronjob(action='create', name='haus-suche', schedule='0 * * * *',
              prompt='Search for houses...')
cronjob(action='update', job_id=job['job_id'],
        skills=['haus-suche-discord'])
```

## Pitfalls

1. **No context** — cron jobs have no conversation history
2. **Self-contained prompts** — must include ALL needed info
3. **Model pinning** — jobs can pin a specific model/provider
4. **Output delivery** — use `deliver` parameter for Discord/Telegram
5. **Don't schedule recursively** — cron sessions should NOT schedule more cron jobs

## Known Bugs & Workarounds

### Bug: `next_run_at` Wrong for Daily Jobs

The harness miscalculates `next_run_at` for daily schedules (`0 0 * * *`). It sets the date to tomorrow instead of today's midnight, meaning a job scheduled at noon would run tomorrow but a job scheduled after midnight could also be delayed.

**Workaround:** Use system crontab as fallback:
```bash
# Add to root crontab (not harness cron)
echo "0 0 * * * cd /path/to/scripts && python script.py >> /path/to/log 2>&1" | crontab -
```
The `crond` daemon on the system is reliable and independent of the harness scheduler.

### Bug: Skills + Repeat Conflict

Passing both `skills=[...]` and `repeat='forever'` in a single `cronjob(action='create')` call causes a comparison error (`'<=' not supported between instances of 'str' and 'int'`).

**Workaround:** Create without skills first, then `update` to attach:
```python
job = cronjob(action='create', name='haus-suche', schedule='0 * * * *',
              prompt='Search for houses...')
cronjob(action='update', job_id=job['job_id'],
        skills=['haus-suche-discord'])
```
