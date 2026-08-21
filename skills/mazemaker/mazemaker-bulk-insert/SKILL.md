---
name: mazemaker-bulk-insert
category: devops
description: Workaround for when neural_remem tool is broken or for bulk-inserting memories directly into the neural memory SQLite database.
---

# Mazemaker Bulk Insert (Direct SQL)

## When to Use
- `neural_remem` tool is broken (returns same ID every time, doesn't actually store)
- You need to insert many memories at once (batch operation)
- You want to add memories with specific salience values
- You need to create connections (edges) between memories

## Prerequisites
- SQLite3 installed
- Access to `~/.mazemaker/data/memory.db`

## Database Schema

### memories table
```sql
CREATE TABLE memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT,
    content TEXT,
    embedding BLOB,
    salience REAL DEFAULT 1.0,
    created_at REAL DEFAULT (unixepoch()),
    last_accessed REAL DEFAULT (unixepoch()),
    access_count INTEGER DEFAULT 0
);
CREATE INDEX idx_mem_label ON memories(label);
```

### connections table (NOTE: NOT from_id/to_id!)
```sql
CREATE TABLE connections(
    id,
    source_id INT,    -- ← NOT "from_id"
    target_id INT,    -- ← NOT "to_id"  
    weight,
    edge_type TEXT,
    created_at
);
CREATE UNIQUE INDEX idx_connections_unique ON connections(source_id, target_id, edge_type);
```

## Step-by-Step

### 1. Insert Memories
```python
import sqlite3
db_path = os.path.expanduser("~/.mazemaker/data/memory.db")
conn = sqlite3.connect(db_path)

memories = [
    ("label-name", "Full content text here"),
    # ... more
]

for label, content in memories:
    conn.execute(
        "INSERT INTO memories (label, content, salience) VALUES (?, ?, ?)",
        (label, content, 1.2)  # salience > 1.0 for important memories
    )
conn.commit()
print(f"Total: {conn.execute('SELECT COUNT(*) FROM memories').fetchone()[0]}")
conn.close()
```

### 2. Insert Connections (Edges)
```python
# CRITICAL: columns are source_id/target_id, NOT from_id/to_id!
conn.execute(
    "INSERT INTO connections (source_id, target_id, weight, edge_type) VALUES (?, ?, ?, ?)",
    (from_id, to_id, 0.9, 'semantic')
)
# Always insert BOTH directions for undirected graph
conn.execute(
    "INSERT INTO connections (source_id, target_id, weight, edge_type) VALUES (?, ?, ?, ?)",
    (to_id, from_id, 0.9, 'semantic')
)
```

### 3. Generate Embeddings (REQUIRED for neural_recall to find them!)

Without embeddings, memories are invisible to semantic search. The search uses KNN on embedding vectors.

**IMPORTANT: BAAI/bge-m3 is NOT in FastEmbed's supported models!** Use `BAAI/bge-large-en-v1.5` instead (also 1024d).

```python
import sqlite3, numpy as np
from fastembed import TextEmbedding

db = sqlite3.connect("~/.mazemaker/data/memory.db")
cur = db.cursor()

nulls = cur.execute("SELECT id, content FROM memories WHERE embedding IS NULL ORDER BY id DESC LIMIT 50").fetchall()

# Use 1024d model matching existing embeddings
model = TextEmbedding(model_name="BAAI/bge-large-en-v1.5")
for mid, content in nulls:
    if not content:
        continue
    emb = list(model.embed([content]))[0]
    cur.execute("UPDATE memories SET embedding = ? WHERE id = ?",
                (emb.astype(np.float32).tobytes(), mid))

db.commit()
db.close()
```

Check existing embedding dims first (DB has mixed 384d + 1024d):
```python
dims = cur.execute("SELECT length(embedding)/4 as dim, COUNT(*) FROM memories WHERE embedding IS NOT NULL GROUP BY dim").fetchall()
# Output: [(384, 79), (1024, 2275)]
```

If you have 384d memories, they won't match in 1024d KNN search. Re-embed them with bge-large-en-v1.5.

The plugin's `generate_embeddings.py` script may fail or use wrong model. Direct Python is more reliable.

### 4. Verify
```bash
# Check count
sqlite3 ~/.mazemaker/data/memory.db "SELECT COUNT(*) FROM memories;"

# Check connections to new memories
sqlite3 ~/.mazemaker/data/memory.db "SELECT COUNT(*) FROM connections WHERE source_id >= 24401;"

# Check embedding status
sqlite3 ~/.mazemaker/data/memory.db "SELECT COUNT(*) FROM memories WHERE embedding IS NOT NULL AND id >= 24401;"
```

## NeuralMemory Python API (Preferred for Batch)

**Direct class approach** (avoids `neural_remem` tool lock issues):

```python
import sys
sys.path.insert(0, "~/projects/neural-memory-adapter/python")
from memory_client import Mazemaker

nm = Mazemaker(
    db_path="~/.hermes/neural_memory.db",  # or ~/.mazemaker/data/memory.db
    embedding_backend="fastembed",   # NOT "embedding_model"!
    use_cpp=False,                   # avoid binary compilation issues
)

# Store a memory
mem_id = nm.remember("content here", label="my-label")

# Check stats
print(nm.stats())   # NOT nm.get_stats() — that doesn't exist!

# Close when done (releases DB lock so neural_remem tool can use it again)
m.close()
```

**IMPORTANT**: If you use the Python API, ALWAYS call `nm.close()` when done. Otherwise the DB stays locked and `neural_remem` tool fails with "database is locked".

Stats output: `{'memories': N, 'connections': N, 'embedding_dim': 1024, 'embedding_backend': 'FastEmbedBackend'}`

## Session Archive Workflow (1,000+ Sessions → Neural Memory)

**Goal**: Archive massive session history (1,298 sessions, 355MB) into meaningful memories without flooding.

**Approach**: Group sessions by date+topic into summarized memories.

```python
import os, json, re
from collections import defaultdict

sessions_dir = "~/.hermes/sessions"
files = sorted([f for f in os.listdir(sessions_dir) if f.endswith(".json")])

# Load sessions (skip request_dump_* — those are empty request traces)
real_sessions = {}
for f in files:
    if "request_dump" in f:
        continue
    with open(os.path.join(sessions_dir, f)) as fp:
        data = json.load(fp)
    if data.get("messages"):
        real_sessions[f] = data

# Score sessions to filter trivial ones
def score_session(fname, data):
    msgs = data.get("messages", [])
    score = min(len(msgs), 50) + len([m for m in msgs if m.get("role") == "tool"])
    if "cron_" in fname:
        score = int(score * 0.3)  # de-prioritize automated sessions
    return score

# Topic detection
topic_keywords = {
    "mazemaker": ["neural memory", "embed_provider", "remember", "recall", "dream engine"],
    "haus-suche": ["haus", "immobil", "miet", "wohn", "camoufox"],
    "dayz": ["dayz", "pbo", "enforce script", "lbmaster", "vppmap"],
    "comfyui": ["comfyui", "stable diffusion", "image gen", "svd"],
    "btquant": ["btquant", "trading", "backtest", "binance"],
    "jrwl-messenger": ["jrwl", "messenger", "double ratchet", "e2e", "x3dh"],
    "linux": ["linux", "bash", "ssh", "docker", "systemd", "cron"],
    "vm": ["vm", "qemu", "kvm", "snapshot", "cloud-init"],
    "hermes": ["hermes", "agent", "skill", "context", "compress"],
    "arxiv": ["arxiv", "paper", "research"],
    "general": [],  # fallback
}

# Group by date+topic
by_date_topic = defaultdict(lambda: defaultdict(list))
for fname, data in real_sessions.items():
    if score_session(fname, data) < 2:
        continue
    # extract topic + date + summary...
    by_date_topic[date][topic].append(record)

# Create one memory per (date, topic) — ~271 for 1,298 sessions
# Store via nm.remember() with label=f"session-archive:{topic}:{date}"
```

**Results**: 1,298 sessions → 271 meaningful memories (2.7 min, 36K connections).

## Pitfalls

1. **`neural_remem` tool may lock DB** - "database is locked" error. Use Python API with `nm.close()` instead, or ensure no other process has the DB open.
2. **`request_dump_*` files are empty** - skip them, not real sessions.
3. **Trivial sessions** - filter out: single message, "test" sessions, very low scores.
4. **Connection column names** - `source_id`/`target_id`, NOT `from_id`/`to_id`
5. **Embedding dimensions** - TF-IDF 384d won't match bge-m3 1024d KNN index. Memories without proper embeddings are invisible to `neural_recall`.
6. **Content escaping** - Use parameterized queries (`?` placeholders) not string interpolation to avoid SQL injection/breaking on quotes.
7. **Salience** - Higher values (1.2-1.5) make memories more important in recall ranking. Default is 1.0.
8. **`neural_remem` silently fails** - returns success but doesn't store. Always verify with `SELECT COUNT(*)` before/after.
