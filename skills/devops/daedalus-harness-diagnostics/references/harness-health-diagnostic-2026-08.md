# Harness Health Diagnostic — 2026-08-02

## Context

User reported that "updated hermes-agent harness is struggling to follow my old
workflow, using skills when needed on fly autonomous." All models affected.
Investigation session with mimo-v2.5-pro on OpenRouter.

## Environment

- Daedalus Agent v0.19.0 (2026.7.20) — 1355 commits behind upstream
- Config version v24 (current is v33)
- Model: xiaomi/mimo-v2.5-pro via opendeepseek provider
- MCP servers: mazemaker (enabled), pulse (enabled), ac-infinity (enabled)
- Toolsets: daedalus-cli, web
- Compression: DISABLED
- Tool use enforcement: auto
- Skills: 137 total, 1 preloaded (prompt-injection-defense)

## Findings (8 compounding issues)

### 1. System prompt bloat — 75+ KB before user speaks

```
System prompt total:  29.5 KB
Tool schemas:         45.4 KB (28 direct tools)
SOUL.md:               4.7 KB
MEMORY.md rules:       6.5 KB (Regel 1-5)
USER.md:               1.8 KB
Skills index:         14.4 KB (137 descriptions)
```

### 2. Compression disabled

`compression.enabled: false` — context accumulates without bound.

### 3. Dual-layer tool discovery

- 28 tools directly available
- 75 tools deferred (mazemaker 31, pulse 14, ac-infinity 29, video 1)
- Models must use tool_search → tool_describe → tool_call
- Most models never discover deferred tools

### 4. Skill preloading gap

Only `prompt-injection-defense` preloaded. 137 skills listed but content not
in context. Models see descriptions but can't follow instructions they haven't
read.

### 5. Dangling skill reference

System prompt references `hermes-agent` skill which was consolidated into
`daedalus-core-capabilities`. Causes failed skill_view on every session.

### 6. Config version drift

v24 vs v33 — 9 versions of behavioral changes missing.

### 7. Harness version drift

1355 commits behind upstream.

### 8. Contradictory instruction layers

SOUL.md: "be autonomous, build, ship, no micromanaging"
MEMORY.md: "ALWAYS call mazemaker FIRST, STRICT protocol, penalties for deviation"
→ Models freeze under contradictory pressure.

## Measurement commands used

```bash
daedalus prompt-size          # prompt breakdown
daedalus doctor               # config health
daedalus config get compression.enabled
daedalus config get skills.preloaded
daedalus config get toolsets
daedalus config get agent.tool_use_enforcement
daedalus --version
daedalus mcp list
```

## Fixes applied (2026-08-02 session)

| Fix | Before | After |
|-----|--------|-------|
| Compression | disabled | enabled |
| MEMORY.md | 6.1 KB | 1.7 KB |
| SOUL.md | 4.7 KB | 1.1 KB |
| USER.md | 1.4 KB | 0.5 KB |
| MESSAGING_CWD | in .env | removed |
| Empty skill dirs | 13 dirs + index-cache | cleaned |
| Harness version | v0.19.0 (1355 behind) | v0.19.1 (current) |
| Config version | v24 | v33 |

System prompt total: 29.6 KB → 25.3 KB (-14%)
Volatile context: 8.3 KB → 2.9 KB (-65%)

## Remaining items (user decision needed)

- Skills index still 14.3 KB (137 skills, user wants all kept)
- Model slug warning (cosmetic, provider works fine)
- Local patches (preloaded skills feature) saved in stash@{0} but won't
  apply cleanly to v0.19.1 codebase

## Recommended fixes (priority order, if not yet applied)

1. `daedalus config set compression.enabled true`
2. `daedalus update`
3. `daedalus config migrate`
4. Fix model slug (vendor prefix mismatch)
5. Preload 5-10 critical skills
6. Trim skill index (137 → top 20-30)
7. Add tool_search instruction to MEMORY.md for deferred tools
8. Align SOUL.md and MEMORY.md instruction layers
