---
name: mazemaker-plugin-arch
description: How the neural memory plugin works inside Daedalus - embedding, graph, recall, tools
category: devops
version: 1.0
tags: [mazemaker, plugin, embedding, graph, recall, knowledge-graph, hermes]
priority: high
---

# Mazemaker Plugin Architecture

How the semantic knowledge graph plugs into Hermes Agent.

## Plugin Location

```
~/.hermes/plugins/memory/mazemaker/
├── __init__.py          # Tool registration (neural_remember, neural_recall, neural_think, neural_graph)
├── memory_client.py     # Core engine — auto-detects backend (Python/MSSQL)
├── memory_client.py     # Client interface for the agent
├── embed_provider.py    # Embedding generation (FastEmbed by default)
├── config.py            # Configuration from config.yaml
├── cpp_bridge.py        # C++ bridge for fast graph ops (optional)
├── mssql_store.py       # MSSQL backend (pyodbc)
```

## How Tools Register

1. `__init__.py` imports and registers tools via `tools/registry.py`
2. Tools must ALSO be in `model_tools.py` discovery list
3. Provider initialized in `run_agent.py` after honcho init

## The 4 Tools

| Tool | Purpose |
|------|---------|
| `neural_remember` | Store a memory with embedding + auto-connections |
| `neural_recall` | Semantic search — find similar memories |
| `neural_think` | Spreading activation — explore connected ideas |
| `neural_graph` | Knowledge graph statistics |

## Auto-Detection

`memory_client.py` checks for `MSSQL_SERVER` + `MSSQL_PASSWORD` env vars:
- If set: C++ bridge → MSSQL
- If not: Python-only (FastEmbed + SQLite)

## Embedding Backends

- **FastEmbed** (default): `embedding_backend=fastembed` in config
- **sentence-transformers**: older, larger embeddings (~28 magnitude vs FastEmbed ~1.0)
- **C++ bridge**: AVX2 cosine similarity, spreading activation

## Connection Pattern

Memories auto-connect via embedding similarity + spreading activation.
Connections weighted 0.0-1.0. `neural_think` traverses the graph.

## Pitfalls

1. **3-Copy Sync**: dev/runtime/test copies must match (see mazemaker-file-sync skill)
2. **Embedding magnitude mismatch**: old sentence-transformers ~28 vs FastEmbed ~1.0 — L2 normalize
3. **C++ bridge stale cache**: disable with `use_cpp=False` after DB changes
4. **Memory full**: neural memory has capacity limits — monitor with `neural_graph`
5. **Tool registration**: tools must be in both `__init__.py` AND `model_tools.py`

## Tool Routing Fix (2026-04-21) — CRITICAL

`handle_function_call()` in `model_tools.py` always dispatched to `registry.dispatch()`.
Neural tools were injected into `self.tools` (sent to LLM) but NEVER in the tool registry.
Result: `"Unknown tool: neural_remember"` on any direct `handle_function_call()` call.

**Fix applied**: `model_tools.py` now has `_memory_manager_ref` + `set_memory_manager()`.
`handle_function_call()` checks memory manager BEFORE `registry.dispatch()`.

```
# model_tools.py — new module variable + setter
_memory_manager_ref = None

def set_memory_manager(mm):
    global _memory_manager_ref
    _memory_manager_ref = mm

# In handle_function_call(), before registry.dispatch():
if _memory_manager_ref and _memory_manager_ref.has_tool(function_name):
    result = _memory_manager_ref.handle_tool_call(function_name, function_args)
else:
    result = registry.dispatch(...)
```

`run_agent.py` calls `set_memory_manager(self._memory_manager)` after tool injection.
Calls `set_memory_manager(None)` on shutdown for clean teardown.

## GPU Engine DB Isolation (2026-04-21)

`gpu_recall.py` loads from `~/.mazemaker/gpu_cache/` — hardcoded global path.
When `Mazemaker(db_path="/tmp/test.db")` is used, GPU engine STILL loads production
cache → phantom IDs from production DB appear in isolated test databases.

**Fix**: In `memory_client.py NeuralMemory.__init__()`:
```python
self._gpu = None
if db_path == DB_PATH:  # only load GPU cache with default DB
    try:
        from gpu_recall import GpuRecallEngine
        self._gpu = GpuRecallEngine()
        ...
```

## Embedder Double-Load (2026-04-21)

`Memory.__init__` created `EmbeddingProvider`, then `NeuralMemory.__init__` created ANOTHER
one → FastEmbed loaded twice (~500MB model duplicated).

**Fix**: `NeuralMemory.__init__` accepts `embedder=None` parameter.
`Memory.__init__` passes `self._embedder` to `NeuralMemory` constructor.

## __init__.py Sync (2026-04-21)

`hermes-plugin/__init__.py` had `_load_config()` at line 586 — function doesn't exist.
Must use `get_config()` from `config.py` (imported at line 173).

mazemaker's `hermes-plugin/__init__.py` must stay in sync with hermes-agent's
`plugins/memory/mazemaker/__init__.py`. If they diverge, the installer overwrites with wrong version.

## harness neural_remember Bug (2026-04-21)

The harness's `neural_remember` tool always returns ID 1256 regardless of content.
This is because hash backend conflict detection sees all "similar" content as conflicts
and returns the superseded ID.

**Workaround**: Use direct Python API with `detect_conflicts=False`:
```python
m.remember("content", label="label", detect_conflicts=False)
```

## MSSQL Sync State (2026-04-21)

SQLite: 2,355 memories, 289,655 edges
MSSQL: 2,625 memories, 3,814 edges

MSSQL has 270 MORE memories (old data from before SQLite-first migration).
MSSQL has way fewer edges (graph connections only in SQLite).

SQLite = Source of Truth. MSSQL = optional mirror (one-way: SQLite → MSSQL).
For full sync: run `migrate.sh` from mazemaker.

## Dream Engine Race Condition (2026-04-21, BENIGN)

MSSQL `connection_history` unique index `UX_connection_history_unique` causes
duplicate key errors when two dream cycles run concurrently.

```
MERGE connection_history ... ON source_id=? AND target_id=?
→ Race: both check, both find empty, both INSERT → duplicate key
```

Already handled with `logger.debug()` (not ERROR). Harmless. SQLite doesn't have this issue.

## Config (config.yaml)

```yaml
memory:
  provider: neural
  neural:
    embedding_backend: fastembed
    use_cpp: false  # disable if stale cache
    mssql:
      server: localhost
      database: NeuralMemory
```

Credentials in `~/.hermes/.env`:
```
MSSQL_SERVER=localhost
MSSQL_DATABASE=NeuralMemory
MSSQL_USERNAME=SA
MSSQL_PASSWORD=***
```
