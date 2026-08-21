---
name: claude-code-stuck-subagent-recovery
description: How to recover when Claude Code (bash claude) subagent hangs with no output — diagnose and fix autonomously without user intervention.
version: 1.0.0
category: autonomous-ai-agents
tags: [claude-code, subagent, debugging, hermes, self-diagnosis]
author: hermes
priority: medium
---

# Claude Code Stuck Subagent Recovery

## Problem

When `bash claude` (claude --dangerously-skip-permissions) is spawned as a background subagent, it can hang indefinitely with **zero output** — even after 3+ minutes. The PTY buffers output, making `process(action="poll")` show no progress.

## Symptoms

- `process(action="poll")` shows `status: running` but `output_preview: ""`
- `process(action="log")` shows 0 lines
- `process(action="wait")` times out
- Claude Code eventually completes but output is lost or delayed

## Root Cause

Claude Code via PTY mode buffers its output. The `--dangerously-skip-permissions` flag is fine, but the overall task prompt may be too large or complex, causing the subagent to think for a very long time before producing any visible output.

## Recovery Strategy

Do NOT just wait. Kill and replace with **direct parallel tool calls**:

### Step 1: Kill the Stuck Process

```python
process(action="kill", session_id="proc_xxx")
```

### Step 2: Run the Same Analysis in Parallel via execute_code

```python
execute_code(code="""
from hermes_tools import terminal, read_file

# Skills analysis
r = terminal("find ~/.hermes/skills -type f -name '*.md' | wc -l")
r2 = terminal("find ~/.hermes/skills -type d | while read d; do echo -n \"$d: \"; du -sh \"$d\" 2>/dev/null | cut -f1; done | sort -k2 -h | tail -20")
r3 = terminal("find ~/.hermes/skills -type f -name '*.md' -exec wc -l {} + 2>/dev/null | sort -rn | head -15")

# Config analysis
r4 = terminal("wc -l ~/.hermes/config.yaml && cat ~/.hermes/config.yaml | grep -A 50 'toolsets'")
r5 = terminal("cat ~/.hermes/config.yaml | grep -A 30 'memory'")

# Process/MCP analysis
r6 = terminal("ps aux | grep -E 'mcp|mazemaker' | grep -v grep")
r7 = terminal("ls -la ~/.mazemaker/")

# Cron jobs
r8 = terminal("cat ~/.hermes/cron/jobs.json 2>/dev/null || ls ~/.hermes/cron/")

# Plugins
r9 = terminal("ls ~/.hermes/plugins/memory/")

print("=== SKILLS COUNT ===")
print(r['output'])
print("=== SKILL DIR SIZES ===")
print(r2['output'])
print("=== BIGGEST FILES ===")
print(r3['output'])
""")
```

### Step 3: Synthesize Results

Use the tool outputs to compile the same report the subagent would have produced. The key is **parallel independent queries** — multiple `terminal()` calls in one `execute_code`, each focused on one dimension.

## Key Principle

> **Don't babysit a stuck subagent.** If `poll` shows nothing after 60s, kill it and do the work directly. Claude Code is great for complex reasoning tasks, but for systematic audits with clear checklist items, direct tool calls are faster and more reliable.

## When to Use Claude Code vs Direct Tools

| Task | Use Claude Code? | Use Direct Tools? |
|------|----------------|-------------------|
| Systematic multi-dimension audit | No — hangs on large prompts | Yes — parallel queries |
| Complex code review with reasoning | Yes — benefits from LLM reasoning | Yes |
| Finding files by pattern | No | Yes — `search_files`, `terminal find` |
| Reading specific file contents | Sometimes | Yes — `read_file` |
| Writing/refactoring code | Yes | Sometimes |
| Single-shot code task | Yes | Yes |

## Prevention

For future self-diagnosis tasks, write the prompt to be **modular** — break into 3-4 smaller subagent calls instead of one massive prompt, or just use direct tool calls for systematic audits.

## Lessons Learned (2026-05-07)

- Claude Code via PTY buffers output heavily — don't trust `poll` to show progress
- A 12-part audit prompt with 10 bullet points is too large — Claude thinks for minutes before output
- Direct `execute_code` with 10+ parallel `terminal()` calls completes in <5 seconds and produces complete data
- The self-improvement-audit skill already existed but the parallel subagent pattern (split into batches of 3) didn't apply here — the issue was Claude Code itself, not the concurrency model
