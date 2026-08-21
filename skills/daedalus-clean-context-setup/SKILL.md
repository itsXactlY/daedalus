---
name: daedalus-clean-context-setup
description: Disable MEMORY.md/USER.md injection for pure neural memory recall, reduce prompt bloat
category: devops
version: 1.0
tags: [memory, context, config, neural, prompt-optimization, tool-bloat]
priority: high
---


> Ported from `hermes-clean-context-setup` during the 2026-08-21 Daedalus skills alignment. Pre-rename history lives in git and `~/.daedalus/skills-archive/2026-08-21-hermes-legacy/`.
# Clean Context Setup

Disable MEMORY.md/USER.md injection so the agent relies purely on neural memory (long-term recall) instead of having answers pre-loaded in the prompt.

## Problem

MEMORY.md and USER.md are injected into the system prompt at session start. This means:
- The agent already "knows" facts before neural_recall runs
- Neural memory becomes an echo, not a source
- 2,200+1,375 chars (~1,200 tokens) of static context every turn
- Self-fulfilling prophecy: agent finds answers in context, neural recall looks good but did nothing

## Config Changes (`~/.daedalus/config.yaml`)

```yaml
memory:
  memory_enabled: false       # Don't inject MEMORY.md into prompt
  user_profile_enabled: false # Don't inject USER.md into prompt
  memory_char_limit: 5        # Backup: even if enabled, limit to 5 chars
  user_char_limit: 5          # Backup: even if enabled, limit to 5 chars
  provider: neural            # Keep neural as memory provider
```

Developer recommendation: "if you only want it to rely on long term recall set the max characters for MEMORY/USER.md's to be like 5 characters"

## Tool Bloat — FIXED via platform_toolsets

`_HERMES_CORE_TOOLS` in `toolsets.py` is hardcoded — 37 tools in `daedalus-cli` preset.
**Workaround:** Use `platform_toolsets` with individual toolsets instead.

`toolsets: [daedalus-cli]` top-level key is **deprecated and ignored**. `platform_toolsets` is the real config.

### Applied config (`~/.daedalus/config.yaml`)

```yaml
platform_toolsets:
  cli:
  - web              # web_search, web_extract
  - terminal         # terminal, process
  - file             # read_file, write_file, patch, search_files
  - skills           # skills_list, skill_view, skill_manage
  - code_execution   # execute_code
  - delegation       # delegate_task
  - cronjob          # cronjob
  - todo             # todo
  - clarify          # clarify
  - memory           # memory
  - session_search   # session_search
```

**Cut:** browser(11), image_gen, tts, ha_*(4), send_message = 19 tools removed
**Result:** 22 schemas (18 toolset + 4 neural) vs 41 before = **-46% prompt bloat**

### Key insight

`platform_toolsets` with individual toolsets **BYPASSES** `_HERMES_CORE_TOOLS` entirely. You're not adding to the core list — you're replacing the preset with your own composition. Each toolset resolves to its tools, and only those schemas go into the prompt.

Neural Memory plugin injects 4 tools (neural_*) regardless of toolset config — cannot be disabled via toolsets.

## Tool Categories (reference)

## Chronological Queries (Critical!)

`neural_recall` gives SEMANTICALLY similar results, NOT chronologically newest.

For "what was the last entry?":
```python
import sqlite3
db = sqlite3.connect("~/.mazemaker/data/memory.db")
cur = db.cursor()
# By ID (reliable for inserts)
cur.execute("SELECT id, label, content, created_at FROM memories ORDER BY id DESC LIMIT 5").fetchall()
# Or by timestamp
cur.execute("SELECT id, label, content, created_at FROM memories ORDER BY created_at DESC LIMIT 5").fetchall()
```

**Semantik != Chronologie!** Always use direct SQL for temporal queries.

## Neural Memory Workarounds

### neural_remem returns ID 1256 silently

The `neural_remem` tool is broken — always returns ID 1256 without actually storing. Workaround:

```python
import sqlite3, numpy as np, time
from fastembed import TextEmbedding

db = sqlite3.connect("~/.mazemaker/data/memory.db")
cur = db.cursor()

# Insert directly
cur.execute("INSERT INTO memories (label, content, created_at) VALUES (?, ?, ?)",
            ("my-label", "my content", time.time()))
mid = cur.lastrowid

# Generate embedding (MUST match existing dim — check first!)
model = TextEmbedding(model_name="BAAI/bge-large-en-v1.5")  # 1024d
emb = list(model.embed(["my content"]))[0]
cur.execute("UPDATE memories SET embedding = ? WHERE id = ?",
            (emb.astype(np.float32).tobytes(), mid))

# Add connections
cur.execute("INSERT INTO connections (source_id, target_id, weight, created_at) VALUES (?, ?, 0.8, ?)",
            (mid, related_id, time.time()))

db.commit()
db.close()
```

**CRITICAL:** Check embedding dimensions match! DB has mixed 384d (old, all-MiniLM-L6-v2) and 1024d (current, bge-large). Using wrong dim = KNN index corruption.

```python
# Check existing dims
dims = cur.execute("SELECT length(embedding)/4 as dim, COUNT(*) FROM memories WHERE embedding IS NOT NULL GROUP BY dim").fetchall()
```

### NULL embedding fix

If memories have NULL embeddings (from bulk inserts or old data):

```python
nulls = cur.execute("SELECT id, content FROM memories WHERE embedding IS NULL").fetchall()
model = TextEmbedding(model_name="BAAI/bge-large-en-v1.5")
for mid, content in nulls:
    emb = list(model.embed([content]))[0]
    cur.execute("UPDATE memories SET embedding = ? WHERE id = ?",
                (emb.astype(np.float32).tobytes(), mid))
db.commit()
```

## Upstream Version

Local: v0.8.0. Upstream: v0.10.0 (600+ commits behind).
Key missing features: Fast Mode, Nous Tool Gateway, Web Dashboard.
`platform_toolsets` works in v0.8.0 — update not blocking but recommended.

## Verification

After config change, restart the agent session. Check prompt token count in logs:
- Before: ~67K+ tokens per turn
- After: ~58K tokens (-13% savings from MEMORY + tool reduction)

Token breakdown (optimized):
```
System prompt base:     ~5,000 tokens
SOUL.md:                ~1,000 tokens
Skills catalog:        ~15,000 tokens
Tool schemas (22):      ~7,000 tokens  (was ~12,000 with 41 tools)
MEMORY.md (disabled):       0 tokens
USER.md (disabled):         0 tokens
Conversation history:  ~30,000 tokens
─────────────────────────────────
TOTAL:                 ~58,000 tokens
```

Memory tool still works for writing to MEMORY.md (disk persistence), it just won't be injected.
