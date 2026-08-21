---
name: daedalus-mcp-visibility
description: "MCP tools vanish under tool_search=auto; set off to fix."
category: devops
---


> Ported from `hermes-mcp-visibility` during the 2026-08-21 Daedalus skills alignment. Pre-rename history lives in git and `~/.daedalus/skills-archive/2026-08-21-hermes-legacy/`.
# Daedalus MCP tool visibility — the deferral trap

## Symptom
A configured MCP server (mazemaker, pulse, ac-infinity, btquant) is clearly
RUNNING — `ps` shows the container, `/health` returns ok, `mcp_servers` is
defined in `config.yaml` — yet the agent never calls its tools. It greps files,
uses `session_search`, or claims it "can't reach mazemaker" instead of just
recalling. This is the #1 reason agents "don't use mazemaker even though they
should."

## Root cause
`tools.tool_search.enabled: auto` (the default) triggers **deferral**: every
MCP and plugin tool is stripped from the model-facing tool array and replaced
by three bridge tools (`tool_search`, `tool_describe`, `tool_call`). Core tools
(`read_file`, `write_file`, `terminal`, `skill_view`, `skills_list`,
`skill_manage`, `delegate_task`, `web_search`, `memory`, … — 61 in
`_HERMES_CORE_TOOLS`) are NEVER deferred. So the model sees mazemaker_* / pulse_*
/ mcp__ac_infinity__* ONLY after it actively steers (`tool_search` →
`tool_describe` → `tool_call`). Small/mid models skip that step and the server
goes unused.

This is NOT a config error like "mcp missing from toolsets" — `mcp_servers` is
enough. The deferral logic is the blocker.

## Fix (one line, persistent)
```bash
daedalus config set tools.tool_search.enabled off
```
Verified persisted at `~/.daedalus/config.yaml` under `tools.tool_search.enabled: 'off'`.
With it off, `assemble_tool_defs` is a passthrough: all MCP tools are in the
hot list, callable with no steering. Empirical proof after the flip:
`mcp__mazemaker__mazemaker_health` returned 214k memories, `mazemaker_recall`
returned real semantic hits, `mcp__pulse__pulse_stats` and
`mcp__ac_infinity__discover_devices` both answered — all called DIRECTLY, no
`tool_search` in between.

## Verification
```bash
daedalus config get tools.tool_search.enabled   # → off
# then call any mcp tool directly, e.g.:
mcp__mazemaker__mazemaker_health              # live data = fixed
```

## Notes
- `tencent/hy3:free` resolves to 262144 context (from `context_length_cache.yaml`),
  not a flat 200k. The deferral budget is `min(20000, 10% of 262144)` = 20k tokens,
  so even the threshold path usually defers on a loaded MCP setup.
- If you ever WANT deferral back on (huge tool count), remember Core tools stay
  visible regardless; only MCP/plugin tools are the ones that get hidden.
- Skill tools (`skill_view`, `skills_list`, `skill_manage`) are Core — never
  deferred, so skill loading is unaffected by this setting.
