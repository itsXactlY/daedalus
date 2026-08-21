---
name: mazemaker-forensic
description: "Systematic forensic audit of neural memory — the 'psychologist' approach: diagnose WHY it fails, not just HOW to fix it."
tags: [mazemaker, debugging, forensics, root-cause, audit]
priority: high
---

# Mazemaker Forensic Audit

When neural memory "doesn't work" after installation, don't debug one symptom at a time.
Do a **full forensic sweep** — 7 independent failure modes can coexist and mask each other.

## When to Use This Skill
- "Neural memory is installed but doesn't work"
- Agent sees neural tools but they return errors
- Recall returns garbage or wrong IDs
- Everything "should work" but doesn't

## Audit Procedure

### Step 1: Load Context (parallel)
Load these skills FIRST — they contain the bug history:
- `mazemaker-debugging` — 5 critical bugs found 2026-04-21
- `mazemaker-plugin-architecture` — tool routing, GPU isolation
- `mazemaker-fix` — conflict detection, embedder injection
- `mazemaker-first` — health check protocol

### Step 2: Live Code Inspection (run as Python)
Check each fix is actually applied in deployed code:

```python
checks = {}
# model_tools.py — _memory_manager_ref routing
# run_agent.py — set_memory_manager call
# __init__.py — get_config not _load_config, no duplicate class, _dream not _dream_engine
# memory_client.py — _reliable_backends check, embedder param, GPU isolation
# embed_provider.py — FastEmbedBackend exists, 915 lines not 875
# Source vs Deployed sync status
```

### Step 3: Database Audit
```python
# Total memories/connections
# NULL embeddings, self-loops
# Benchmark garbage (DD*, turn-*, session-summary)
# Embedding dimension (1024d expected)
# Embedding magnitude (1.0 expected = normalized)
# GPU/C++ phantom ID detection
```

### Step 4: Source vs Deployed Comparison
```bash
# Files that MUST be identical:
# memory_client.py, memory_client.py, embed_provider.py, __init__.py, config.py
diff ~/projects/mazemaker/hermes-plugin/FILE \
     ~/.hermes/hermes-agent/plugins/memory/mazemaker/FILE
```

### Step 5: Write Report
Structured markdown with:
- Executive Summary (one paragraph)
- Each Failure Mode: Symptom → Root Cause → Why So Hard To Debug → Fix → Status
- DB State snapshot
- What's STILL broken
- Recommendations

## Known Failure Modes (checklist)

| # | Failure Mode | Symptom | Quick Check |
|---|-------------|---------|-------------|
| 1 | Tool Routing | "Unknown tool: neural_remember" | `_memory_manager_ref` in model_tools.py |
| 2 | Conflict Detection | Always returns same ID | `_reliable_backends` in memory_client.py |
| 3 | Embedding Backend | Similarity ~0.07, 384d not 1024d | `FastEmbedBackend` in embed_provider.py |
| 4 | GPU DB Isolation | Phantom IDs from production DB | `db_path == DB_PATH` guard in memory_client.py |
| 5 | Double-Loading | FastEmbed loads twice, slow startup | `embedder=None` param in NeuralMemory.__init__ |
| 6 | _load_config() | NameError on init | `get_config` not `_load_config` in __init__.py |
| 7 | Cross-Repo Sync | Changes don't take effect | Source vs Deployed line count / md5 match |

## Pitfalls

- **Fixes mask each other**: Fix #1 (tool routing) exposes #2 (conflict detection). Fix #2 exposes #3 (embedding garbage). Fix #3 exposes #4 (GPU isolation). Always check ALL modes.
- **Hash backend is a time bomb**: Works "somehow" but produces garbage similarity. Never use for conflict detection.
- **Source ≠ Deployed**: The `mazemaker` source may be outdated vs deployed `hermes-agent` files. Always compare.
- **embed_provider.py line count is a health indicator**: 915 lines = has FastEmbed. 875 lines = missing FastEmbed. If it drops to 875, FastEmbed was overwritten.

## Output Format

Write report to `~/projects/mazemaker/docs/FORENSIC-AUDIT-{date}.md`.
Include timestamp, sources consulted, and pass/fail for each of the 7 modes.
