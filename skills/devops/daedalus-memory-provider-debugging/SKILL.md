---
name: daedalus-memory-provider-debugging
description: Debug memory providers - why honcho/neural/memory plugins fail or don't store data
category: devops
version: 1.1
tags: [memory, provider, debugging, honcho, neural, plugins, daedalus, tool-routing]
priority: high
---


> Ported from `hermes-memory-provider-debugging` during the 2026-08-21 Daedalus skills alignment. Pre-rename history lives in git and `~/.daedalus/skills-archive/2026-08-21-hermes-legacy/`.
# Memory Provider Debugging

Daedalus supports multiple memory providers. When data doesn't arrive, here's how to diagnose.

## Provider Chain

```
config.yaml: memory.provider = "honcho" | "neural" | "builtin"
    |
    v
agent/memory_provider.py (interface)
    |
    +---> plugins/memory/honcho/ (conversation memory)
    +---> plugins/memory/mazemaker/ (semantic knowledge graph)
    +---> plugins/memory/byteover/ (alternative)
    +---> plugins/memory/hindsight/ (retrospective learning)
    +---> plugins/memory/holographic/ (holographic memory)
    +---> plugins/memory/mem0/ (Mem0 integration)
    +---> plugins/memory/retaindb/ (alternative)
    +---> plugins/memory/supermemory/ (alternative)
```

## Diagnostic Steps

### 1. Check Which Provider Is Active
Look at startup logs for "Memory provider: X"

### 2. Check Provider Is Loaded
```python
from hermes_tools import terminal
result = terminal("python3 -c \"from agent.memory_provider import MemoryProvider; print('OK')\"")
```

### 3. Check Plugin Init
Each plugin has `__init__.py` that exports a provider class.
If the file is missing or has import errors, provider silently falls back to builtin.

### 4. Check Config
```yaml
memory:
  provider: honcho  # or neural, builtin
```

### 5. Check Env Vars
- `HONCHO_API_KEY` for Honcho
- `MSSQL_SERVER`, `MSSQL_PASSWORD` for Neural+MSSQL
- Missing env vars = silent fallback

### 6. Check Database Connection
- Honcho: API health check
- Neural: SQLite file exists at `~/.daedalus/data/neural_memory.db`
- MSSQL: `pyodbc` connection test

## Common Failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| Nothing stored | Provider not loaded | Check config.yaml + plugin __init__.py |
| Data in wrong format | Embedding magnitude mismatch | L2 normalize (see neural-memory-file-sync) |
| Silent fallback to builtin | Import error in plugin | Check plugin logs for tracebacks |
| Old data not found | Session ID changed | Session IDs are per-conversation |
| C++ bridge errors | Stale cache | Set `use_cpp: false` in config |
| Tool returns "Unknown tool" | Memory tools not routed through manager | Check model_tools.py has _memory_manager_ref + set_memory_manager() — see neural-memory-testing skill |
## Chronological Query (neural_recall != Chronologie)

`neural_recall` gibt SEMANTISCH ähnliche Ergebnisse, nicht die NEUESTEN. Für chronologische Queries direkt SQLite nutzen:

```sql
SELECT id, label, content, created_at FROM memories ORDER BY id DESC LIMIT 5;
```

Siehe auch: `daedalus-clean-context-setup` Skill für MEMORY.md Deaktivierung.
