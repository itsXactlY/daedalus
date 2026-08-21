---
name: debugging
description: Debugging neural memory integration issues — tool calling, embedding backends, conflict detection, cross-repo sync, plugin installation, and configuration. Tested on clean VM.
category: devops
version: 1.1
tags: [neural-memory, debugging, tool-routing, embedding, conflict-detection, cross-repo, plugin, fastembed]
---

# Neural Memory Debugging Guide

## Critical Bugs Found & Fixed (2026-04-21 + 2026-04-23)

### 1. Tool Calling: handle_function_call doesn't route memory tools

**Symptom:** `neural_remember`/`neural_recall`/`neural_think`/`neural_graph` return "Unknown tool" from `registry.dispatch()`.

**Root cause:** Tool schemas are injected into `self.tools` (sent to LLM) but NOT registered in the tool registry. `handle_function_call()` in `model_tools.py` dispatches ALL tools to `registry.dispatch()` which doesn't know about memory tools.

**Fix:** Add `_memory_manager_ref` module variable in `model_tools.py`:
```python
_memory_manager_ref = None

def set_memory_manager(mm):
    global _memory_manager_ref
    _memory_manager_ref = mm
```

In `handle_function_call()`, before `registry.dispatch()`:
```python
if _memory_manager_ref and _memory_manager_ref.has_tool(function_name):
    result = _memory_manager_ref.handle_tool_call(function_name, function_args)
else:
    result = registry.dispatch(...)
```

In `run_agent.py`, after tool injection:
```python
from model_tools import set_memory_manager as _smm
_smm(self._memory_manager)
```

And on shutdown: `_smm(None)`.

**Files:** `model_tools.py`, `run_agent.py`

### 2. Conflict Detection with Hash Backend — Always Same ID

**Symptom:** `neural_remember` always returns the same ID (e.g., 1256). New memories are never created — always superseded.

**Root cause:** `memory_client.py` `remember()` method has `detect_conflicts=True` by default. Hash backend produces fake cosine similarities (many pairs > 0.7). Conflict detection fires for every new memory, supersedes an existing one, returns its ID.

**Fix:** Only enable conflict detection with reliable backends:
```python
_reliable_backends = {'FastEmbedBackend', 'SentenceTransformerBackend'}
_backend_name = type(self.embedder.backend).__name__
_can_detect = _backend_name in _reliable_backends

if detect_conflicts and self._graph_nodes and _can_detect:
    conflicts = self._find_conflicts(text, embedding)
```

**File:** `python/memory_client.py`, `hermes-plugin/memory_client.py`

### 2b. Label-Agnostic Conflict Detection — Same ID for ALL New Memories (2026-04-23)

**Symptom:** `remember()` returns the same ID (1256) for ALL new memories — every new memory overwrites the same record, regardless of content or label.

**Root cause:** TWO compounding bugs in `memory_client.py` `_find_conflicts()`:

1. **Label-agnostic scan**: `_find_conflicts()` searched ALL memories (including `[SUPERSEDED]` chains with accumulated old IDs) and used `_content_differs()` to compare text similarity. Even with FastEmbedBackend, `same label` was NOT checked first — two memories with completely different labels ("test:lang_pref" vs "test:compress") were treated as potential conflicts.

2. **Aggressive `_content_differs()`**: Used a keyword ratio check that returned `True` for ANY two texts with different keywords. "test A" and "test B" differ → `True` → conflict found. The first match in `get_all()` traversal was the oldest `[SUPERSEDED]` memory (id=1256), so every new text matched it first and got assigned id=1256.

**Fix — label-based conflict detection:**
```python
def _find_conflicts(self, label: str, embedding: list[float], text: str):
    """Find memories with same label that should be updated."""
    threshold = self._similarity_threshold
    for mem in self.store.get_all():
        # Skip superseded memories (update chains, not real conflicts)
        if mem.get("label", "").startswith("[SUPERSEDED]"):
            continue
        # DIFFERENT LABEL = different topic, NOT a conflict
        if mem.get("label") != label:
            continue
        # Same label: check embedding similarity
        sim = cosine_similarity([embedding], [self._decode_embedding(mem["embedding"])])[0][0]
        if sim >= threshold and self._content_differs(text, mem["content"]):
            return mem
    return None
```

**Verification after fix:**
```python
# Before: remember() returns same id for all new memories → id=1256
# After:
ids = [nm.remember(f"test content {i}", label=f"test{i}")["id"] for i in range(5)]
print(ids)  # [24569, 24570, 24571, 24572, 24573] — all unique
```

**File:** `python/memory_client.py`

### 2c. chunk_text() Producing Identical Chunks (2026-04-23)

**Symptom:** `chunk_text()` returns chunks that are all identical, even with different text input. `remember_chunked()` creates memories with duplicate IDs.

**Root cause:** `effective_overlap = min(overlap, chunk_size // 2)` with `overlap=200, chunk_size=200` → `effective_overlap=100`. In pathological case (repetitive text), the overlap boundary lands mid-word and barely shifts the start position. The overlap text of chunk N ≈ chunk N-1's overlap → identical chunks.

Also: no word-boundary detection. When `space_idx` found a space at index 1 (very early), the overlap text started mid-word, making alignment unreliable.

**Fix in `neural_memory.py` `chunk_text()`:**
```python
effective_overlap = min(overlap, max(1, chunk_size // 2))

# Find word boundary for clean overlap
space_idx = chunk_text.rfind(' ', 0, effective_overlap)
if space_idx > 0:
    overlap_start = space_idx + 1
    overlap_text = chunk_text[overlap_start:overlap_start + effective_overlap]
else:
    overlap_start = 0
    overlap_text = chunk_text[:effective_overlap]

# Guard: if overlap is nearly identical to start, reduce to 1-char shift
if overlap_text.strip() and prev_tail.strip():
    if overlap_text.strip() == prev_tail.strip():
        effective_overlap = 1
        overlap_text = chunk_text[:1]
```

**Verification:**
```python
chunks = nm.chunk_text(" ".join([f"Sentence {i}." for i in range(50)]), chunk_size=200, overlap=200)
ids = [nm.remember_chunked(c, source_id="test")["id"] for c in chunks]
assert len(set(ids)) == len(ids), f"Duplicate IDs: {ids}"  # All unique
```

**File:** `python/memory_client.py`

### 3. GPU Engine DB Isolation Leak

**Symptom:** `recall()` on a custom DB path returns phantom IDs from production DB.

**Root cause:** `GpuRecallEngine` loads from `~/.mazemaker/gpu_cache/` — a hardcoded global path. When using a custom `db_path`, the GPU engine still returns results from the production cache.

**Fix:** Only load GPU engine with default DB_PATH:
```python
if db_path == DB_PATH:
    try:
        from gpu_recall import GpuRecallEngine
        self._gpu = GpuRecallEngine()
        ...
    except Exception:
        self._gpu = None
```

**File:** `python/memory_client.py`

### 4. Embedder Double-Loading (FastEmbed Loaded Twice)

**Symptom:** FastEmbed model (~500MB) loaded twice — Memory creates EmbeddingProvider, then NeuralMemory creates another one.

**Fix:** NeuralMemory accepts optional `embedder=` parameter:
```python
def __init__(self, ..., embedder=None):
    if embedder is not None:
        self.embedder = embedder
    else:
        from embed_provider import EmbeddingProvider
        self.embedder = EmbeddingProvider(backend=embedding_backend)
```

Memory passes its existing embedder:
```python
self._sqlite_memory = Mazemaker(db_path=..., embedder=self._embedder)
```

**Files:** `python/memory_client.py`, `python/memory_client.py`

### 5. __init__.py _load_config() Not Defined

**Symptom:** `name '_load_config' is not defined` on fresh install.

**Root cause:** `plugins/memory/mazemaker/__init__.py` calls `_load_config()` but the function is actually `get_config()` from `config.py`.

**Fix:** Sync `__init__.py` between neural-memory-adapter and hermes-agent. Both must use `get_config()`.

### 6. FastEmbedBackend Class Missing from Source (CRITICAL — 2026-04-22)

**Symptom:** All `neural_recall` queries return **identical results** regardless of query text. Access logs show query embeddings with many `0.0` values (sparse). Scores clustered around 0.92 for everything.

**Root cause:** `embed_provider.py` has NO `FastEmbedBackend` class. The `EmbeddingProvider.__init__` dispatch:
```python
if backend == "auto":
    self.backend = self._auto_detect()
elif backend == "sentence-transformers":
    ...
elif backend == "tfidf":
    ...
else:
    self.backend = HashBackend()  # "fastembed" lands HERE!
```
There is no `elif backend == "fastembed"` handler. Config says `embedding_backend: fastembed`, code says "kenn ich nicht" → HashBackend.

**Why it's devastating:**
- HashBackend produces ~1.2% non-zero values (12/1024)
- All stored memories get hash-embedded (sparse, pseudo-random)
- Cosine similarity between hash vectors is meaningless
- Every query returns the same top-k by coincidence

**How to detect:**
```python
from embed_provider import EmbeddingProvider
ep = EmbeddingProvider(backend='fastembed')
print(type(ep.backend).__name__)  # If "HashBackend" → BUG
# Should be "FastEmbedBackend"

# Or check stored embeddings:
import sqlite3, struct
conn = sqlite3.connect('~/.mazemaker/data/memory.db')
cur = conn.cursor()
cur.execute("SELECT embedding FROM memories LIMIT 1")
emb = struct.unpack(f'{len(cur.fetchone()[0])//4}f', cur.fetchone()[0])
non_zero = sum(1 for v in emb if abs(v) > 0.001)
print(f"Non-zero: {non_zero}/1024")  # If <50 → hash, should be ~1020
```

**Fix — add FastEmbedBackend class before HashBackend in `embed_provider.py`:**
```python
class FastEmbedBackend:
    MODEL_NAME = "intfloat/multilingual-e5-large"
    def __init__(self, dim: int = DIMENSION):
        self.dim = dim
        self._model = None
        self._load()
    def _load(self):
        from fastembed import TextEmbedding
        self._model = TextEmbedding(model_name=self.MODEL_NAME)
        test = list(self._model.embed(["test"]))
        self.dim = len(test[0])
        print(f"[embed] FastEmbed loaded: {self.MODEL_NAME} ({self.dim}d)")
    def embed(self, text: str) -> list[float]:
        result = list(self._model.embed([text]))
        return result[0].tolist() if hasattr(result[0], 'tolist') else list(result[0])
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        results = list(self._model.embed(texts))
        return [r.tolist() if hasattr(r, 'tolist') else list(r) for r in results]
```

**Fix — add handler in `__init__`:**
```python
elif backend == "fastembed":
    self.backend = FastEmbedBackend()
elif backend == "hash":
    self.backend = HashBackend()
```

**Fix — add to `_auto_detect` as first priority:**
```python
try:
    backend = FastEmbedBackend()
    print(f"[embed] Auto-selected: FastEmbed ({backend.dim}d)")
    return backend
except (ImportError, Exception) as e:
    ...
```

**After fixing — re-embed all memories (use hermes venv, NOT sd-venv):**
```bash
# FastEmbed is in ~/.hermes/venv, NOT ~/sd-venv
# Batch re-embed script — redirect to file to avoid stdout buffering issues
cat > /tmp/reembed.py << 'EOF'
import sys, sqlite3, struct, os, time
sys.path.insert(0, os.path.expanduser('~/projects/neural-memory-adapter/python'))
from embed_provider import EmbeddingProvider
ep = EmbeddingProvider(backend='fastembed')
conn = sqlite3.connect(os.path.expanduser("~/.mazemaker/data/memory.db"))
cur = conn.cursor()
cur.execute("SELECT id, content FROM memories ORDER BY id")
rows = cur.fetchall()
batch_size = 25
for i in range(0, len(rows), batch_size):
    batch = rows[i:i+batch_size]
    embeddings = ep.embed_batch([r[1] for r in batch])
    for (mid, _), emb in zip(batch, embeddings):
        cur.execute("UPDATE memories SET embedding=? WHERE id=?", (struct.pack(f'{len(emb)}f', *emb), mid))
    conn.commit()
    print(f"  {min(i+batch_size, len(rows))}/{len(rows)}")
conn.close()
print("DONE")
EOF
# Run in background with file redirect (terminal tool buffers stdout)
~/.hermes/venv/bin/python /tmp/reembed.py > /tmp/reembed.log 2>&1 &
# Check progress:
tail -f /tmp/reembed.log
```
1392 memories ≈ 96s. ~40K emb/s in batch mode.

**Forensic audit** at `docs/FORENSIC-AUDIT-2026-04-21.md` already documented this exact issue. Source repo (875 lines) lost FastEmbedBackend during sync; deployed version (915 lines) had it. But both ended up at 875 lines — the fix was lost.

**Prevention:** `embed_provider.py` in `python/` is single source of truth (symlinked). Never manually copy between repos.

**After re-embedding — regenerate dashboard:**
```bash
cd ~/projects/neural-memory-adapter/tools/dashboard
~/.hermes/venv/bin/python generate.py
```
The static dashboard HTML embeds `embedding_dim` as JSON. Old dashboards may show stale 384d. Copy regenerated dashboard to wherever it's displayed (e.g. `~/The Architects Palace/`).

---

### 7. Salience Always 1.0 (never updated) — Fixed 2026-04-22

**Symptom:** Dashboard shows `salience=1.0` for almost all memories. No differentiation between important and peripheral memories.

**Root cause:** `INSERT INTO memories (label, content, embedding)` doesn't set salience → defaults to 1.0. `touch()` only updates `access_count` and `last_accessed` — never recomputes salience. No code anywhere adjusts salience after creation.

**Fix — dynamic salience in `touch()` (`memory_client.py`):**
```python
def touch(self, id_: int):
    with self._lock:
        self.conn.execute(
            "UPDATE memories SET last_accessed = unixepoch(), access_count = access_count + 1 WHERE id = ?",
            (id_,)
        )
        # Recompute salience
        row = self.conn.execute(
            "SELECT access_count, (SELECT COUNT(*) FROM connections WHERE source_id = ? OR target_id = ?) as conn_count FROM memories WHERE id = ?",
            (id_, id_, id_)
        ).fetchone()
        if row:
            access_count, conn_count = row[0], row[1]
            import math
            # log-log damping for access (handles 100K+ access counts), log for connections
            salience = 1.0 + 0.25 * math.log1p(math.log1p(access_count)) + 0.15 * math.log1p(conn_count)
            salience = max(0.5, min(3.0, salience))
            self.conn.execute("UPDATE memories SET salience = ? WHERE id = ?", (salience, id_))
        self.conn.commit()
```

**Backfill existing memories:**
```python
import math
for mem_id, access_count, conn_count in rows:
    salience = 1.0 + 0.25 * math.log1p(math.log1p(access_count)) + 0.15 * math.log1p(conn_count)
    cur.execute("UPDATE memories SET salience = ? WHERE id = ?", (max(0.5, min(3.0, salience)), mem_id))
```

**Formula:** `1.0 + 0.25 * log1p(log1p(access)) + 0.15 * log1p(conn_count)` clamped [0.5, 3.0]
- access=0 → 1.0, access=100 → ~1.5, access=10K → ~1.8, access=100K → ~2.0
- Double-log prevents 148K access counts from always hitting max

### 8. Dashboard embedding_dim Hardcoded — Fixed 2026-04-22

**Symptom:** Dashboard shows `384` dim even though all memories are 1024d. Old static HTML or live server serves stale value.

**Root cause:** `live_server.py` and `generate.py` use `EMBEDDING_DIM = 1024` constant instead of reading from DB. If the constant was ever 384, old dashboards still show 384. The systemd service caches the old value until restarted.

**Fix — read from DB dynamically:**
```python
# In read_sqlite():
cur.execute("SELECT length(embedding) FROM memories WHERE embedding IS NOT NULL LIMIT 1")
emb_row = cur.fetchone()
actual_dim = (emb_row[0] // 4) if emb_row else EMBEDDING_DIM
```

**After changes — restart live server:**
```bash
systemctl --user restart neural-dashboard.service
```
The live server caches data in memory. Always restart after code changes. Dashboard also has a restart button (⟳) that calls `POST /api/restart` → systemd restart → auto-reload page.

**After re-embedding — regenerate static dashboard:**
```bash
cd ~/projects/neural-memory-adapter/tools/dashboard
~/.hermes/venv/bin/python generate.py
cp ~/neural_memory_dashboard.html ~/The\ Architects\ Palace/
```

---

## Deployment (v2 — Symlinks, not copies)

As of 2026-04-21: `python/` is single source of truth, deployed via `ln -s`.
No more 3-copy sync. See `neural-memory-file-sync` skill.

Installer detects hermes-agent in: `~/.hermes/hermes-agent`, `~/jack-in-a-box/hermes-agent`, `~/hermes-agent`, etc.


<!-- moved to references/moved-sections.md: ## Embedding Backend Priority -->

## Architecture (v2 — Symlinks, not copies)

```
~/projects/neural-memory-adapter/python/       ← ONE source (21 .py files)
~/.hermes/hermes-agent/plugins/memory/mazemaker/  ← SYMLINKS → source (23 links)
~/.hermes/plugins/memory/mazemaker/               ← LEGACY, cleaned (only plugin.yaml)
```

**Commands:** `bash install.sh install|update|test|verify|uninstall`
**NEVER `cp` files between directories again.** Edit `python/` → live everywhere.
**hermes-agent detection** checks: `~/.hermes/hermes-agent`, `~/jack-in-a-box/hermes-agent`,
`~/hermes-agent`, `~/.hermes/agent`, `/opt/hermes-agent`, `~/projects/hermes-agent`

## File Locations (v2 — Symlinks)
- Plugin source (SINGLE SOURCE OF TRUTH): `~/projects/neural-memory-adapter/python/`
- Deployed (SYMLINKS): `~/.hermes/hermes-agent/plugins/memory/mazemaker/`
- Config: `~/.hermes/config.yaml` (section: `memory.neural`)
- Database: `~/.mazemaker/data/memory.db`
- Installer: `bash install.sh install` (auto-detects hermes-agent)

## Clean VM Requirements

- **4GB RAM minimum** for FastEmbed model download (~500MB)
- **python3-venv** required on Debian 12: `apt install python3.11-venv`
- **--hash-backend** flag for constrained environments (<3GB RAM)
- **Root check** in all installers: `id -u` → `exit 1`

## CRITICAL: Which Python?

Hermes uses `~/.hermes/hermes-agent/venv/bin/python3`, **NOT** system python3 (`/usr/bin/python3`).

```bash
# WRONG (system python — may lack fastembed, pyodbc etc)
python3 -c "import fastembed"  # FAILS

# CORRECT (hermes-agent venv)
~/.hermes/hermes-agent/venv/bin/python3 -c "import fastembed; print(fastembed.__version__)"  # 0.8.0
```

The `hermes` command in PATH points to `~/.local/bin/hermes` → `~/.hermes/hermes-agent/venv/bin/hermes`. The venv has fastembed 0.8.0. System python may have an older version or none at all.

## Interpreting Test Suite Output (2026-04-23)

When running the neural memory test suite, the output often looks alarming but is NOT a problem:

```
Embedding backend: HashBackend (1024d)   ← EXPECTED (system Python has no fastembed)
Embedding backend: FastEmbedBackend (1024d)  ← CORRECT (hermes-agent venv)
Downloading (incomplete total...): 0%| ... | 1.86k/2.25G  ← fastembed cache miss, one-time
```

**Why:** The test suite (`python3 tests/test_upside_down.py`) runs with **system Python** (`/usr/bin/python3` = Python 3.14), which typically lacks fastembed. HashBackend is the intentional fallback. Hermes Agent itself runs with `~/.hermes/hermes-agent/venv/bin/python3` which has fastembed.

**Verifying the real state** (use hermes venv, NOT system python):
```bash
~/.hermes/hermes-agent/venv/bin/python3 -c "
import sys; sys.path.insert(0, '~/projects/neural-memory-adapter/python')
from embed_provider import EmbeddingProvider
p = EmbeddingProvider('auto')
print(f'Backend: {p.backend.__class__.__name__}')  # Should say FastEmbedBackend
"
# Output: Backend: FastEmbedBackend  ← System is FINE
```

## Test Suite

Run upside-down tests:
```bash
cd ~/projects/neural-memory-adapter
python3 tests/test_upside_down.py
```

27 sections, 196+ assertions covering:
- Wrong paths, garbage inputs, empty DB, concurrent access
- Duplicate content, rapid fire stress, corrupted DB
- Embedding backend fallback, MemoryProvider interface
- Installer checks, cross-fork detection, config generation
- File sync, memory lifecycle, dream engine, access logger
- DB schema/WAL, graceful degradation, text processing
- Multiple DB instances, connection graph integrity
- neural_recall deep (k limits, phantom IDs, field validation)
- neural_graph deep (weights, self-loops, top_edges sort)
- neural_think deep (depth levels, ghost IDs)
- DB isolation (no GPU/C++ leak, content purity)

## Upside-Down Test Suite (2026-04-21)

`tests/test_upside_down.py` — 195 assertions, 27 sections.

**Run standalone (no hermes-agent):** 146/146 pass
**Run with hermes-agent on path:** 161/161 pass (additional MemoryProvider tests)

**27 Sections:**
1-12: Original (wrong paths, garbage inputs, empty DB, concurrent, duplicates, rapid fire, corrupted DB, embed fallback, MemoryProvider, installer, cross-fork, config)
13: Cross-fork hermes-agent detection (5 paths)
14: Config.yaml generation (roundtrip, hash backend, dream settings)
15: Plugin file sync (python/ vs hermes-plugin/ — 10 shared files must be identical)
16: Memory lifecycle (full round-trip: init→store→recall→think→graph→close→reopen)
17: Dream engine (dream_now(), stats via SQL)
18: Access logger (correct API signature)
19: DB schema & WAL (tables, columns, indexes, integrity)
20: Graceful degradation (hash fallback, missing deps)
21: Text processing (unicode, special chars, long content)
22: Multiple DB instances (isolation)
23: Connection graph integrity (edges, weights, self-loops)
24: Neural recall deep (k limits, phantom ID detection, field validation, sort order)
25: Neural graph deep (empty/single/many, no self-loops, weights in [0,1], top_edges sorted)
26: Neural think deep (depth levels, ghost IDs, negative IDs, phantom detection)
27: DB isolation (no GPU/C++ leak, content purity across databases)

## C++ Bridge Hopfield Bias (CRITICAL!)

**Symptom:** `recall()` always returns same result (e.g., bench-math-363) with high similarity (~0.967) regardless of query.

**Root cause:** C++ Hopfield network learns from stored data. If benchmark data dominates (1004 bench memories), the network biases towards matching benchmark patterns.

**Fix:** Set `use_cpp=False` in `__init__.py`. Use GPU recall or Python fallback.

**Also related:** Embedding normalization mismatch. If stored embeddings normalized to mag=1.0 but query has mag=28 (raw FastEmbed), cosine similarity breaks. Fix: normalize BOTH or keep BOTH raw.

## MSSQL Backup Pitfall: Striped Backups

MSSQL backups created with `MIRROR TO` or `STRIPES` require ALL media family files to restore. If you only have one file:

```
Msg 3132: The media set has 2 media families but only 1 are provided.
```

**This backup is UNUSABLE.** You cannot partial-restore a striped backup.

**Prevention:**
- Always backup to a single file: `BACKUP DATABASE X TO DISK='...'` (no MIRROR TO)
- Or keep ALL stripe files together
- Verify after backup: `RESTORE VERIFYONLY FROM DISK='...'`

**If stuck with unusable backup:**
- Fall back to SQLite as canonical (it's self-contained)
- Re-sync MSSQL FROM SQLite after recovery

## Database Recovery After BTRFS Snapshot Restore

When a BTRFS snapshot restore rolls back the system but databases may be on different volumes:

1. **Check which DB survived**: MSSQL data at `/var/opt/mssql/` may or may not be on the snapshot volume
2. **SQLite is usually more reliable**: `~/.mazemaker/data/memory.db` is self-contained
3. **Look for `memory_.db`**: Often the post-migration DB (smaller, cleaner, has migration markers)
4. **Migration markers are truth**: DBs with "SNAPSHOT RESTORE", "MIGRATION COMPLETE", "FastEmbed" labels are post-fix state

## Dashboard Regeneration After Embedding Changes

After changing embedding backend or dimension, regenerate the dashboard:

```bash
cd ~/projects/neural-memory-adapter/tools/dashboard
~/.hermes/venv/bin/python generate.py
# Output: ~/neural_memory_dashboard.html
cp ~/neural_memory_dashboard.html ~/The\ Architects\ Palace/neural_memory_dashboard.html
```

The dashboard's `EMBEDDING_DIM` is set in `generate.py:28` and `live_server.py:33` (currently 1024). The generated HTML embeds this in `stats.embedding_dim`. Old static dashboards may show stale values — always regenerate.

**Dashboard templates:** `template.html` (static, used by `generate.py`), `template-live.html` (WebSocket live version).

## Total System Recovery Checklist

After catastrophic failure (snapshot restore, full wipe), restore in this order:

```bash
# 1. hermes-crypto (if project exists)
cd ~/projects/hermes-crypto && git restore . && git pull

# 2. pulse (if project exists)
cd ~/projects/pulse && git add -A && git commit -m "Post-restore cleanup"

# 3. Neural memory — BOTH venvs need packages
source ~/.hermes/venv/bin/activate && pip install fastembed sentence-transformers
source ~/.hermes/hermes-agent/venv/bin/activate && pip install fastembed sentence-transformers

# 4. Config fix
# In ~/.hermes/config.yaml, set: memory.neural.embedding_backend: fastembed

# 5. Tool registration
cp ~/.hermes/tools/neural_tools.py ~/.hermes/hermes-agent/tools/
# Verify: grep neural_tools ~/.hermes/hermes-agent/model_tools.py

# 6. Gateway restart
hermes gateway restart
```

When everything is gone but DB exists at `~/.mazemaker/data/memory.db`:

```bash
# 1. Install deps in BOTH venvs (critical — hermes-agent has its own venv!)
source ~/.hermes/venv/bin/activate && pip install fastembed sentence-transformers
source ~/.hermes/hermes-agent/venv/bin/activate && pip install fastembed sentence-transformers

# 2. Fix config.yaml — embedding_backend must be 'fastembed' or 'auto'
# In ~/.hermes/config.yaml:
#   memory:
#     neural:
#       embedding_backend: fastembed   # NOT 'sentence-transformers'

# 3. Copy neural_tools.py to hermes-agent/tools/
cp ~/.hermes/tools/neural_tools.py ~/.hermes/hermes-agent/tools/

# 4. Ensure model_tools.py has neural_tools in discovery list
# Check: grep neural_tools ~/.hermes/hermes-agent/model_tools.py

# 5. Gateway restart
hermes gateway restart
```

## Triangular Database Comparison (SQLite vs SQLite vs MSSQL)

When recovering from failures, there may be multiple DB copies with different states. Compare WITHOUT writing:

```python
# Get ID sets from each
big_ids = {row[0] for row in big_conn.execute("SELECT id FROM memories").fetchall()}
small_ids = {row[0] for row in small_conn.execute("SELECT id FROM memories").fetchall()}
mssql_ids = {row[0] for row in mssql_cursor.execute("SELECT id FROM memories").fetchall()}

# Set operations reveal truth
only_big = big_ids - small_ids - mssql_ids    # lost data
only_small = small_ids - big_ids               # post-migration additions
only_mssql = mssql_ids - big_ids - small_ids   # potential garbage or new
shared = big_ids & small_ids & mssql_ids       # canonical overlap

# Check freelist (dead space = not vacuumed)
cursor.execute("PRAGMA freelist_count")
freelist_mb = cursor.fetchone()[0] * page_size / 1024 / 1024

# Check for benchmark garbage in MSSQL
# Labels like "DD1:10-D1:12|..." or "Caroline"/"Melanie" = LongMemEval benchmark data
```

**Decision rules:**
- DB with fewest freelist pages = most compact (usually canonical)
- DB with migration markers (SNAPSHOT RESTORE, MIGRATION COMPLETE, FastEmbed) = post-fix state
- MSSQL often accumulates benchmark garbage from `memoryagentbench` runs — filter with:
  - `label LIKE 'DD%'` (dialogue turns)
  - `label LIKE 'turn-%'` (auto-saved conversation noise)
  - `content LIKE '%Caroline%' AND content LIKE '%Melanie%'` (LongMemEval personas)

## Embedding Magnitude Mismatch (Critical!)

After DB merge/rebuild, recall returns wrong results (e.g., always "bench-math-363" regardless of query).

**Root cause:** Mixed embedding models produce different magnitudes:
- Old sentence-transformers: magnitude ~28 (non-normalized)
- FastEmbed: magnitude ~1.0 (L2-normalized)

Cosine similarity with mixed magnitudes = bench entries dominate everything.

**Fix: L2-normalize ALL embeddings after merge:**
```python
import sqlite3, struct
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute('SELECT id, embedding FROM memories WHERE embedding IS NOT NULL')
for mid, emb in c.fetchall():
    vec = list(struct.unpack('1024f', emb))
    mag = sum(v*v for v in vec) ** 0.5
    if mag > 0:
        normalized = [v/mag for v in vec]
        c.execute('UPDATE memories SET embedding=? WHERE id=?', 
                  (struct.pack('1024f', *normalized), mid))
conn.commit()
conn.execute('VACUUM')
conn.close()
```

**Verify:** After normalization, all magnitudes should be 1.0:
```python
vec = struct.unpack('1024f', embedding)
mag = sum(v*v for v in vec) ** 0.5
assert 0.999 < mag < 1.001, f"Bad magnitude: {mag}"
```

## C++ Bridge Stale Cache

After rebuilding the SQLite DB, the C++ bridge (`libneural_memory.so`) may cache old embeddings. Recall returns stale data.

**Symptoms:** Manual cosine search in Python works, but `NeuralMemory.recall()` returns wrong results.

**Fix:** Set `use_cpp=False` in `plugins/memory/mazemaker/__init__.py` line ~391:
```python
self._memory = Mazemaker(
    db_path=self._config["db_path"],
    embedding_backend=self._config["embedding_backend"],
    use_cpp=False,  # C++ bridge has stale cache after DB rebuild
)
```

**Or** rebuild the C++ bridge to re-read the DB.

## MSSQL Import Pitfalls

When syncing SQLite → MSSQL:

1. **Wrong table:** `memories` table (has label, content, embedding as varbinary) NOT `NeuralMemory` table (vector_data, metadata_json)
2. **IDENTITY_INSERT:** Must `SET IDENTITY_INSERT memories ON` to preserve SQLite IDs
3. **FK constraints:** `connections.source_id/target_id` reference `memories.id` — import memories FIRST
4. **Embedding format:** SQLite stores as 4096-byte blob (1024 floats × 4 bytes), MSSQL `memories.embedding` is varbinary — pass bytes directly
5. **vector_dim column:** Must set `vector_dim=1024` alongside embedding
6. **Dream sessions schema mismatch:** SQLite has `started_at/completed_at/nrem_count/rem_count/insight_count`, MSSQL has `phase/memories_processed/connections_strengthened/...` — different columns!

## Benchmark Garbage Filtering (LongMemEval)

MSSQL often accumulates benchmark data from `memoryagentbench` runs. Strict filter:

```python
import re
DD_PATTERN = re.compile(r'^DD\d+')  # Matches DD1-DD999+

skip_if:
- DD_PATTERN.match(label)                    # DD1:10-D1:12|... benchmarks
- any(name in label for name in [            # LongMemEval personas
    'Caroline','Melanie','Maria','John',
    'Nate','Joanna','Sarah','Mike','Emily','David'])
- 'said, "' in content[:100]                 # Dialogue format
  and 'shared a photo' in content
- content.startswith('[') and 'am on' in content[:60]  # Timestamped dialogue
- label.startswith('turn-')                  # Auto-saved conversation noise
- label.startswith('session-summary') and 'SYSTEM:' in content[:200]
```

## Database Rename After Merge

After importing quality MSSQL memories into the smaller DB:
```bash
# 1. Rename big → backup
mv ~/.mazemaker/data/memory.db ~/.mazemaker/memory_old.db

# 2. Rename small → canonical
mv ~/.mazemaker/memory_.db ~/.mazemaker/data/memory.db

# 3. VACUUM to reclaim space (reduces ~55MB → ~34MB)
sqlite3 ~/.mazemaker/data/memory.db "VACUUM;"

# 4. Config already points to ~/.mazemaker/data/memory.db — no change needed
```

## GPU Recall Engine (2026-04)

For sub-100ms recall, use the GPU recall engine (`gpu_recall.py`):
- Loads all embeddings as CUDA tensor (~8.8 MB VRAM for 2264 memories)
- Uses `torch.matmul(all_emb, query)` + `torch.topk`
- Falls back to Python if no CUDA

**Setup:** Re-embed all memories, then cache:
```bash
# Re-embed with GPU (sentence-transformers + CUDA, ~20s for 2264)
# Cache to ~/.mazemaker/gpu_cache/embeddings.npy + metadata.pkl
```

## Verification Commands

```bash
# Verify FastEmbedBackend is loaded (should say FastEmbedBackend, NOT HashBackend)
~/.hermes/hermes-agent/venv/bin/python3 -c "
import sys; sys.path.insert(0, '~/projects/neural-memory-adapter/python')
from embed_provider import EmbeddingProvider
p = EmbeddingProvider('auto')
print(f'Backend: {p.backend.__class__.__name__}')
v = p.embed('test')
non_zero = sum(1 for x in v if abs(x) > 0.001)
print(f'Non-zero: {non_zero}/1024 ({100*non_zero/1024:.1f}%)')
"

# Verify neural tools are registered
cd ~/.hermes && python3 -c "
from tools.registry import registry
for name in ['neural_remember', 'neural_recall', 'neural_think', 'neural_graph']:
    e = registry._tools.get(name)
    print(f'{name}: {e.toolset if e else \"NOT FOUND\"}')"

# Verify plugin __init__.py exists
ls -la ~/.hermes/hermes-agent/plugins/memory/mazemaker/__init__.py
```
