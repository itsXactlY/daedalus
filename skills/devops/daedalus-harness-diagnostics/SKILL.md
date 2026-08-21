---
name: daedalus-harness-diagnostics
description: >-
  Use when models fail at autonomous tool or skill discovery.
version: 1.0.0
author: Daedalus Agent
license: MIT
metadata:
  daedalus:
    tags: [daedalus, diagnostics, prompt, compression, tools, skills, config]
---


> Ported from `hermes-harness-diagnostics` during the 2026-08-21 Daedalus skills alignment. Pre-rename history lives in git and `~/.daedalus/skills-archive/2026-08-21-hermes-legacy/`.
# Daedalus Harness Diagnostics

Class-level skill for diagnosing why models struggle with the Daedalus harness
across ALL providers. The root cause is almost always **prompt bloat**, not
model capability. When every model becomes "a dumb slice of toast," this is
the diagnostic playbook.

## When to use

- Model ignores skills, never calls tool_search, skips mazemaker recall
- Model gives generic answers instead of using available tools
- Model worked before but now struggles (harness updated, config drifted)
- User reports "models are dumb" or "skills don't work"
- After any Daedalus update, config migration, or skill consolidation
- Provider returns HTTP 404 consistently (stale base_url in credential pool)

## Step 1: Measure the prompt

```bash
daedalus prompt-size          # human-readable breakdown
daedalus prompt-size --json   # machine-parseable
```

Key thresholds:
- System prompt total > 25 KB → **RED** — most models drown
- System prompt total 15-25 KB → **YELLOW** — strong models survive, weak ones don't
- System prompt total < 15 KB → **GREEN**
- Skills index > 10 KB → too many skills competing for attention
- Tool schemas > 50 KB → heavy but unavoidable with many toolsets

## Step 2: Check compression

```bash
daedalus config get compression.enabled
```

If `false`, this is the #1 fixable issue. Without compression, context
accumulates without bound. After 5-10 turns of tool calls, the model loses
its own instructions in the noise.

```bash
daedalus config set compression.enabled true
```

## Step 3: Audit deferred tool discovery

MCP tools (mazemaker, pulse, ac-infinity, etc.) are **deferred tools** — not
in the direct tool list. Models must use `tool_search` → `tool_describe` →
`tool_call` to access them. Most models skip this because:

1. They see 28 direct tools and assume that's everything
2. `tool_search` requires prior knowledge that hidden tools exist
3. Instructions to "call mazemaker_recall FIRST" conflict with it not being direct

Check what's direct vs deferred:
```bash
daedalus prompt-size   # shows "Tool schemas: N tools" = direct
tool_search(query="mazemaker")   # shows deferred tools
```

Fix: Add explicit mention in MEMORY.md that MCP tools are accessed via
`tool_search`. Or restructure toolsets to make critical MCP tools direct.

## Step 4: Check skill preloading

```bash
daedalus config get skills.preloaded
```

Only preloaded skills have their **content** in context. The rest are just
57-char descriptions in the index. With 137 skills:
- Index = 14 KB of noise
- Models pick wrong skills or skip them entirely
- Fix: preload the 5-10 most critical, reduce index to top 20-30

## Step 5: Run daedalus doctor

```bash
daedalus doctor
```

Flags:
- Config version outdated → `daedalus config migrate`
- Model slug mismatch → fix provider/model alignment
- Deprecated keys → manual cleanup
- Dangling skill references → audit after consolidation

## Step 6: Check harness version

```bash
daedalus --version
```

If >500 commits behind, significant behavioral changes are likely missing.
```bash
daedalus update
```

## Step 7: Audit instruction layers

Check for contradictions between:
- SOUL.md (identity/philosophy)
- MEMORY.md (protocol rules)
- USER.md (preferences)
- Skills preloaded

Common conflict: SOUL says "autonomous" but MEMORY says "strict protocol
with penalties for deviation." Models freeze under contradictory pressure.

## Step 8: Check for stale base_url in credential pool

When a provider returns **HTTP 404** on every request (not 401/403), the base_url
in the credential pool may be stale. The OpenAI SDK appends `/chat/completions`
(or `/v1/chat/completions`) itself — if the stored base_url already includes that
path, the actual requests go to a doubled URL that 404s.

```bash
cd ~/.daedalus && python3 -c "
import json
with open('auth.json') as f:
    data = json.load(f)
for prov, creds in data.get('credential_pool', {}).items():
    if not isinstance(creds, list): continue
    for c in creds:
        url = c.get('base_url', '')
        if '/chat/completions' in url or '/responses' in url:
            print(f'STALE [{prov}]: {url}')
"
```

Fix: strip the endpoint suffix back to the base:
```bash
cd ~/.daedalus && python3 -c "
import json
with open('auth.json') as f:
    data = json.load(f)
for prov, creds in data.get('credential_pool', {}).items():
    if not isinstance(creds, list): continue
    for c in creds:
        url = c.get('base_url', '')
        for suffix in ['/v1/chat/completions', '/chat/completions', '/v1/responses', '/responses']:
            if url.endswith(suffix):
                c['base_url'] = url[:-len(suffix)]
                # Re-add /v1 if the provider needs it (e.g. opencode.ai)
                if 'opencode.ai' in c['base_url'] and not c['base_url'].endswith('/v1'):
                    c['base_url'] += '/v1'
                print(f'FIXED [{prov}]: {url} -> {c[\"base_url\"]}')
with open('auth.json', 'w') as f:
    json.dump(data, f, indent=2)
"
```

**How it happens:** The TUI/desktop/gateway persists the full resolved URL
(including `/chat/completions`) into the credential pool after a model switch.
A later session picks up that URL and the SDK doubles it. The
`normalize_opencode_base_url()` function in `hermes_cli/models.py` only ensures
`/v1` is present — it does NOT strip `/chat/completions` because it shouldn't
need to; the pool should never store the full endpoint.

## Pitfalls

1. **Prompt bloat is invisible** — the model doesn't know it's drowning. It
   just fails to find the signal in 75 KB of noise. The user sees "dumb model"
   but the model is actually following the wrong instruction from the noise.

2. **Compression disabled is the silent killer** — it looks like a config
   preference but it's actually a context management guarantee. Without it,
   every session degrades over time.

3. **Deferred tools are undiscoverable** — models don't know to call
   `tool_search` unless explicitly told. The old harness had MCP tools as
   direct tools. The new two-layer architecture broke autonomous discovery.

4. **Skill index bloat causes paralysis** — 137 skill descriptions are 14 KB
   of competing noise. Models either pick the first plausible one or skip
   skills entirely. Preloading 5-10 key skills + trimming the index helps.

5. **Config drift is cumulative** — v24 → v33 means 9 versions of behavioral
   changes the model isn't getting. Each version may change defaults, add
   knobs, or fix bugs that affect tool routing.

6. **Dangling refs waste tool calls** — after skill consolidation, any
   reference to the old skill name (e.g., `hermes-agent`) causes a failed
   `skill_view` on every session start.

7. **Contradictory instructions cause model freeze** — when SOUL.md says
   "be autonomous" and MEMORY.md says "follow strict protocol or face
   penalties," models default to inaction (safest response to contradiction).

8. **Stale credential_pool base_url doubles the endpoint** — when a provider
   consistently returns HTTP 404 (not 401/403), check `auth.json` credential_pool
   for a `base_url` that already includes `/chat/completions` or `/responses`.
   The OpenAI SDK appends these itself; a stored full endpoint becomes
   `.../chat/completions/v1/chat/completions` → 404. The
   `normalize_opencode_base_url()` function only ensures `/v1` is present, it
   does NOT strip `/chat/completions`. See Step 8 for the diagnostic + fix.

## Quick reference: diagnostic commands

| Command | What it shows |
|---------|---------------|
| `daedalus prompt-size` | Full prompt breakdown by component |
| `daedalus doctor` | Config health, version drift, auth status |
| `daedalus config get compression.enabled` | Compression status |
| `daedalus config get skills.preloaded` | Which skills are in context |
| `daedalus config get toolsets` | Active tool clusters |
| `daedalus mcp list` | MCP server status and tool counts |
| `daedalus --version` | Harness version vs upstream |
| `daedalus config get agent.tool_use_enforcement` | How tool usage is enforced |
| `python3 -c "..."` (Step 8) | Credential pool base_url staleness check |

## Case study: 2026-08-02 harness degradation

See `references/harness-health-diagnostic-2026-08.md` for the full forensic
analysis that produced this skill — 8 compounding issues found in a single
investigation session.
