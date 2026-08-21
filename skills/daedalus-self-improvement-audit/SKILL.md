---
name: daedalus-self-improvement-audit
name: self-improvement-audit
version: 1.0.0
category: autonomous-ai-agents
description: Systematic self-improvement audit for Daedalus Agent — analyze skills, memory, config, tool usage, errors, and communication patterns using parallel subagents.
author: daedalus
tags: [meta, self-improvement, audit, quality]
---


> Ported from `hermes-self-improvement-audit` during the 2026-08-21 Daedalus skills alignment. Pre-rename history lives in git and `~/.daedalus/skills-archive/2026-08-21-hermes-legacy/`.
# Self-Improvement Audit

Systematic audit of agent health across 6 dimensions using parallel subagents.

## When to Use
- After major config changes or migrations
- Periodically (monthly) to catch drift
- When user asks "how can you improve?"
- After accumulating 1000+ error log lines

## Audit Dimensions (6 parallel subagents)

### 1. Skills Analysis
- Scan ~/.daedalus/skills/ for duplicates, overlaps, quality
- Check for: identical files, overlapping content, excessive length, missing metadata
- Flag hardcoded paths, domain bloat

### 2. Memory System
- Check MEMORY.md and USER.md capacity (warn at 80%)
- Look for: stale entries, duplicated content, misplaced entries
- Verify config.yaml drift (reasoning_effort, compression, providers)

### 3. Behavioral Patterns
- Analyze errors.log for top error categories
- Check cron job execution status
- Look for: auth failures, connection errors, rate limiting
- Check plugin/provider health

### 4. Tool Usage Patterns
- Analyze which tools are used vs available
- Find tools with 100% failure rate (disable or fix)
- Identify underutilized tools (session_search, delegate_task, execute_code)
- Check for sequential calls that could be parallel

### 5. MemPalace Data Quality
- Check KG entity types (should NOT be "unknown")
- Verify temporal bounds on facts
- Look for duplicate KG databases
- Check wing/room organization (not flat)
- Count noise vs signal in embeddings

### 6. Communication Patterns
- Verbosity consistency (too terse vs too verbose)
- Formatting (markdown in CLI = bad)
- Language consistency with user
- MemPalace citation compliance
- Duplicate responses across sessions

**Known violations to check:**
- Memory id 118277: Oscillates 7-token recalls ↔ 709-token dumps (user wants "zero fluff")
- Memory id 217445: Heavy markdown (**bold**, ##headers, tables) in CLI despite terminal-first user
- Memory id 579378: MCP mempalace 96% failure rate = zero citations in 21K+ messages
- Memory id 217449/122604: "favorite color" duplicated 4+ times, 6,000+ sync_turn() duplicates
- Memory id 25121: Conflict detection bug - same label + similar + _content_differs=False → creates duplicate

**User context for fixes:**
- Timezone: Europe/Berlin
- USER.md: "German when user speaks German, English otherwise" (memory id=571604)
- Direct style: "Prefers direct, terse, command-focused responses — no filler" (memory id=22542)

## Execution Pattern

```
1. session_search() → find recent sessions
2. delegate_task × 6 (parallel) → one per dimension
   NOTE: max_concurrent_children = 3. Split into TWO batches of 3 if doing 6.
3. Synthesize findings
4. Execute safe fixes in parallel while collecting results
5. Present ask-user list with clear tradeoffs
6. Apply user-approved fixes
7. Save audit results as skill: self-improvement-audit-results
```

### Lessons Learned (2026-04-26) + (2026-06-11)

### MCP Server Health Check (2026-06-11)
Before audit, verify MCP servers are running:
```
ss -tlnp | grep <configured_port>
curl -s http://127.0.0.1:<port>/health
```
Disabled servers should be removed from config to prevent error log spam.
Pattern: Port 8910 not listening -> 730 "MCP server 'btquant' failed initial connection" errors.

### Config Provider Key Validation (2026-06-11)
Providers with `type: custom` do NOT accept `description` or `type` keys.
These cause warnings like: `providers.llama-turbo: unknown config keys ignored`
Fix: Remove `description` and `type` from custom provider configs.

### Error Source Breakdown Pattern (2026-06-11)
When analyzing errors.log, classify by source:
- MCP connection failures: Check if port is listening
- Background review denials: Check `approvals.cron_mode` - intentional security
- Discord API errors: Check channel IDs still exist
- Rate limits: Check model tier (free vs paid)

### delegate_task concurrency limit
- `max_concurrent_children` defaults to 3
- Requesting 6 parallel tasks → BLOCKED with "Too many tasks"
- Fix: split into 2 calls of 3 tasks each, run sequentially

### Claude Code (bash claude) subagent hangs with large prompts
- Claude Code via PTY buffers output — `process(action="poll")` shows `output_preview: ""` even when running
- Tasks with 10+ checklist items hang silently for 3+ minutes before producing output
- Fix: for systematic audits, use direct `execute_code` with parallel `terminal()` calls instead
- For multi-dimension audits, use `delegate_task` in batches of 3 (not one massive claude subagent)
- Kill with `process(action="kill")` and replace with direct tool calls — don't babysit

### Skills Quality Audit + Autonomy Repair (2026-08-12)

Full audit of ~/.daedalus/skills (295 SKILL.md, 1800 files) + curator lifecycle repair.
Verified with the [auto-routed skills] block appearing in the live prompt — the
deterministic auto-router fires without user command. Commits bb29d18be, c47293ae9.

**Missing config shim after port (load_config_readonly)**:
- After the 0.20→0.8.0 port, `load_config_readonly()` was REMOVED from
  hermes_cli/config.py but 24 callers remained (agent/curator.py,
  curator_backup.py, web_search_registry.py, video/image_gen_registry.py,
  hermes_state.py, gateway/platforms/base.py). All silently fell back to `{}`
  → user config was IGNORED since the port.
- Symptom: `daedalus curator status` shows runs=0 / last run=never; config edits
  have no effect; background features silently dead.
- Diagnosis: `grep -rn "load_config_readonly" --include="*.py" | wc -l` vs
  `grep -c "def load_config_readonly" hermes_cli/config.py`. Callers > definition
  → missing shim.
- Fix: restore as a thin shim over `load_config()` (merged DEFAULT_CONFIG +
  user overrides; NO write/migrate side effects). Test suite must be run after.

**Config sections in dead leaf files**:
- `curator` + `auxiliary.curator` existed only in the dead config_defaults.py
  leaf, NOT in the active DEFAULT_CONFIG dict in config.py. After any port,
  check the ACTIVE config source, not legacy leaves.

**Zero-caller lifecycle hooks (maybe_run_curator)**:
- curator docs said "runs inactivity-triggered from session start" but
  `maybe_run_curator()` had ZERO callers in the codebase. Docs lie — verify
  with grep before trusting documented behavior.
- Fix pattern: wire `_maybe_run_curator_async()` daemon thread into
  AIAgent.__init__ (best-effort, try/except, local threading import). Gate
  first run with should_run_now(): seed last_run_at and defer the first pass
  by interval_hours so it doesn't mass-prune on first boot.

**Auto-backup cron commits runtime state**:
- Hourly auto-backup does `git add -A` → runtime artifacts (.curator_state,
  .curator_backups/) get committed alongside real changes. After adding any
  background subsystem, immediately add its state dirs to .gitignore.
- Untrack leaked files: `git rm -r --cached <paths>` + gitignore + commit.

### Critical fixes found and applied
- **remember_protocol plugin broken**: `ctx._remember_pre_llm_call` called on PluginContext stub class (defined locally, never attached). Fixed by using lambdas in register().
- **Dream Engine DB locks**: 153x "database is locked" — dream_engine.py connections missing WAL mode. Fixed: added `PRAGMA journal_mode=WAL` + `PRAGMA busy_timeout=5000`.
- **Hardcoded paths**: 88 occurrences of `~/` in skills. Fixed: `sed -i 's|~/|~/|'` on operational skills (not references/).
- **Skills overlap**: neural-memory-debugging (1018L) + neural-memory-adapter-fix → merged. dayz-debugging + dayz-integrations → merged.
- **Neural memory duplicate DBs**: `~/.daedalus/neural_memory.db` (273 memories) and `~/.daedalus/plugins/memory/mazemaker/memory.db` (empty) → deleted both.
- **USER.md empty**: 0 chars — user profile not persisted. Created with language prefs, quality standard, role expectation, pet peeves.
- **prefill.json missing**: caused startup warning. Created.

### MEMORY.md vs USER.md principle
- MEMORY.md = system state, operational facts, project inventory
- USER.md = user preferences, language rules, quality standards, pet peeves
- Never mix: user prefs in MEMORY.md → migrate to USER.md

### ask-user list (decide BEFORE executing)
1. remember_protocol plugin update vs disable
2. Telegram desktop app vs bot polling conflict
3. Skills overlap merge decisions
4. Hardcoded path normalization (88 occurrences, 26 files fixed)
5. delegate_task usage — expand or keep minimal?

## Safe Fixes (do automatically)
- Memory consolidation (merge duplicates, right-size entries)
- Skill deduplication (delete identical files, merge overlaps)
- Config corrections (remove dead providers, fix reasoning_effort)
- Stale DB cleanup (neural_memory.db, empty orphans)
- Empty skill directory removal
- Hardcoded path normalization in operational skills
- prefill.json creation
- USER.md creation when empty
- MCP server disable: `daedalus config set mcp_servers.<name>.enabled false`
- Provider key cleanup: Remove `description`/`type` from `type: custom` providers

## Unsafe Fixes (ask user first)
- Deleting skills with overlap (may have unique content)
- Changing compression settings
- Modifying personality/system_prompt
- Pruning custom_providers
- Plugin code changes
- Dream engine WAL modifications

## Pitfalls
- Don't auto-delete skills without verifying content is merged elsewhere
- Don't change config without user confirmation for impactful settings
- MEMORY.md edits must use exact string matching (replace mode)
- Cron jobs may look unexecuted because scheduler needs gateway running
- Neural memory init can hang if GPU memory policy says no fallback — test with `EMBED_NO_SHARED=1`
- Telegram polling conflicts: often the desktop app (not the bot) competing for the same token
- Skills reference bloat: `references/` subdirs can have 10K+ lines of raw docs — trim to summaries
