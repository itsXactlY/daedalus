---
name: memory-provider-status
description: Memory provider status - Honcho is dead, Neural Memory is the only provider
category: devops
version: 2.0
tags: [memory, neural, honcho, deprecated, provider, hermes]
priority: critical
---

# Memory Provider Status

## Current State

**Neural Memory is the ONLY memory provider.** Honcho was garbage and got completely replaced.

## What Happened

- Honcho was the original conversation memory provider
- It was unreliable — data didn't arrive, sessions were flaky, debugging was painful
- Neural Memory was built from scratch as a full replacement
- Neural Memory does EVERYTHING Honcho did, plus semantic knowledge graph, embeddings, spreading activation
- Honcho is deprecated. Do not use it. Do not configure it.

## Neural Memory Capabilities (What Honcho Couldn't Do)

| Feature | Honcho | Neural Memory |
|---------|--------|---------------|
| Conversation storage | Basic | Full with embeddings |
| Semantic search | No | Yes (cosine similarity) |
| Knowledge graph | No | Yes (connections, spreading activation) |
| Cross-session memory | Limited | Full (persistent SQLite/MSSQL) |
| Self-learning | No | Yes (connection weights adapt) |
| Dream engine | No | Yes (NREM/REM/Insight consolidation) |
| Embedding-based recall | No | Yes (FastEmbed) |

## Config

```yaml
memory:
  provider: neural  # ONLY valid option now
```

## Neural Memory Plugin (Upstream)

Location: `~/hermes-upstream/plugins/memory/mazemaker/__init__.py` (594 lines)

**IMPORTANT: Work in upstream `~/hermes-upstream/`, NOT in `~/.hermes/` (that's the installed runtime).**

Pattern: Same as honcho/holographic/mem0 plugins. Import `MemoryProvider` from `agent.memory_provider`. Implement all required methods. Has `register(ctx)` entry point.

4 Tool Schemas: `neural_remember` (store), `neural_recall` (search), `neural_think` (connections), `neural_graph` (stats)

Required Methods:
- name property
- is_available() -> bool
- initialize(session_id, **kwargs)
- system_prompt_block() -> str
- prefetch(query, session_id="") -> str
- queue_prefetch(query, session_id="")
- sync_turn(user_content, assistant_content, session_id="")
- get_tool_schemas() -> List[Dict]
- handle_tool_call(name, args) -> str
- shutdown()

Optional Hooks: on_session_end, on_pre_compress, on_memory_write

Config: `memory.provider = neural` in config.yaml. SQLite backend at `~/.mazemaker/data/memory.db`. FastEmbed 1024d embeddings.

## Files

- `plugins/memory/mazemaker/` — The plugin (ACTIVE)
- `plugins/memory/honcho/` — DEPRECATED, do not touch
- `agent/memory_provider.py` — Provider interface (points to neural)

## If Someone Asks About Honcho

The answer is: "Dead. Neural Memory replaced it completely. Don't use it."
