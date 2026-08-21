# debugging — Detailed Sections

Sections moved out of SKILL.md to keep the core playbook lean. Load with
`skill_view(file_path='references/moved-sections.md')`.

---

## Embedding Backend Priority

```
1. FastEmbed    (intfloat/multilingual-e5-large, ONNX, ~50ms)
2. SentenceTransformers (BAAI/bge-m3 1024d, CUDA, ~200ms)  
3. TFIDF        (numpy only)
4. Hash         (instant, zero deps)
```

`auto` picks the best available. Hash backend works everywhere but produces unreliable similarity scores — never use for conflict detection.

### 9. Dream Worker — SQLite Dual-Backend Support (2026-04-22)

**Problem:** `dream_worker.py` was hardcoded to MSSQL only. DreamWorker.__init__ imported DreamMSSQLStore unconditionally. SQLite fallback didn't work.

**Root causes (multiple):**

#### 9a. SQLiteDreamBackend missing `.conn` property
DreamWorker accesses `self.store.conn.cursor()` directly. SQLiteDreamBackend had no persistent connection — only `_connect()` returning new connections each time.

**Fix in `dream_engine.py`:**
```python
class SQLiteDreamBackend(DreamBackend):
    def __init__(self, db_path):
        self._db_path = db_path
        self._persistent_conn = None
        self._ensure_tables()

    @property
    def conn(self):
        """Persistent connection for DreamWorker compatibility (like MSSQLStore.conn)."""
        if self._persistent_conn is None:
            self._persistent_conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._persistent_conn.row_factory = sqlite3.Row
        return self._persistent_conn

    def close(self):
        if self._persistent_conn:
            self._persistent_conn.close()
            self._persistent_conn = None
```

#### 9b. EmbedProvider class name wrong
`dream_worker.py` imported `EmbedProvider` from `embed_provider.py`, but the class is named `EmbeddingProvider`.

**Fix:** Change `DreamWorker.__init__`:
```python
from embed_provider import EmbeddingProvider as _EP
self.embedder = _EP()
```

#### 9c. cursor.execute() needs tuple args for SQLite
MSSQL pyodbc accepts `cursor.execute(sql, arg1, arg2)`. SQLite requires `cursor.execute(sql, (arg1, arg2))`.

**Fix:** All cursor.execute calls must use tuple args:
```python
# WRONG (works with pyodbc, crashes with sqlite3):
cursor.execute("SELECT ... WHERE id = ?", mid, mid)
# RIGHT:
cursor.execute("SELECT ... WHERE id = ?", (mid, mid))
```

Found in: phase_nrem (line ~232, ~255), phase_rem (via store methods), _extract_theme.

#### 9d. SELECT TOP N is MSSQL-only
`_extract_theme` used `SELECT TOP 50 content FROM memories WHERE id IN (...)`. SQLite doesn't support TOP.

**Fix — dialect-aware:**
```python
if self._backend_type == "mssql":
    cursor.execute(f"SELECT TOP 50 content FROM memories WHERE id IN ({placeholders})")
else:
    cursor.execute(f"SELECT content FROM memories WHERE id IN ({placeholders}) LIMIT 50")
```

#### 9e. MERGE is MSSQL-only
`log_connection_change` in SQLiteDreamBackend used `MERGE ... WHEN MATCHED ... WHEN NOT MATCHED` — MSSQL syntax.

**Fix:** Simple INSERT (connection_history just logs changes):
```python
conn.execute(
    "INSERT INTO connection_history (source_id, target_id, old_weight, new_weight, reason, changed_at) "
    "VALUES (?, ?, ?, ?, ?, ?)",
    (source_id, target_id, old_weight, new_weight, reason, time.time())
)
```

#### 9f. ON CONFLICT requires UNIQUE constraint
`add_bridge` used `ON CONFLICT(source_id, target_id) DO UPDATE` but connections table has no unique constraint on (source_id, target_id).

**Fix:** Check-then-insert (already had the check):
```python
if not existing:
    conn.execute(
        "INSERT INTO connections (source_id, target_id, weight, edge_type, created_at) "
        "VALUES (?, ?, ?, 'bridge', ?)",
        (source_id, target_id, weight, time.time())
    )
```

#### 9g. Column name mismatches between schema and code
- Connections table has `edge_type`, not `bridge`
- dream_insights has `insight_type` and `source_memory_id`, not `type` and `memory_id`

Always check `PRAGMA table_info(tablename)` against the code.

**Fix:** Auto-detect backend in DreamWorker:
```python
class DreamWorker:
    def __init__(self, backend="auto", db_path="", mssql_config=None):
        if backend == "auto":
            backend = self._detect_backend()
        if backend == "sqlite":
            from dream_engine import SQLiteDreamBackend
            self.store = SQLiteDreamBackend(db_path or "~/.mazemaker/data/memory.db")
            self._backend_type = "sqlite"
        else:
            from dream_mssql_store import DreamMSSQLStore
            self.store = DreamMSSQLStore()
            self._backend_type = "mssql"

    @staticmethod
    def _detect_backend():
        try:
            import pyodbc
            from dream_mssql_store import DreamMSSQLStore
            store = DreamMSSQLStore()
            store.close()
            return "mssql"
        except Exception:
            return "sqlite"
```

**SUPERSEDED 2026-05-08.** `dream_worker.py` is now a host-side daemon already running on a 5-minute cycle (managed manually, not via systemd at this time). The CLI flags listed above (`--backend sqlite|mssql|auto`, `--db`, `--idle`) are GONE. The current dream_worker accepts only `--max-memories`, `--max-isolated`, `--cycle-interval`, `--log-level`. MSSQL backend is gone entirely (V2 stack uses SQLite hot + optional pgvector for tier upgrades, not MSSQL).

To trigger a cycle from the agent, call the MCP tool:
```
mazemaker_dream(phase='all'|'nrem'|'rem'|'insight')
```
Do NOT shell out to `python dream_worker.py` from a skill — that spawns its own embedding model on GPU (~2 GB extra VRAM) and contends with the host daemon for the SQLite WAL lock.

---

### 10. Cython Import Error from setup_fast.py (2026-04-22)

**Symptom:** `plugins.memory - DEBUG - Failed to load submodule plugins.memory.neural.setup_fast: No module named 'Cython'`

**Root cause:** Plugin loader in `plugins/memory/__init__.py` (line 151) scans ALL `.py` files in the plugin dir:
```python
for sub_file in provider_dir.glob("*.py"):
```
`setup_fast.py` is a Cython build script (`from Cython.Build import cythonize`). If it's symlinked into the plugin dir, the loader tries to import it as a submodule → fails on systems without Cython.

**Impact:** DEBUG-level only — not fatal. But clutters logs and confuses diagnostics.

**Fix:** `install.sh` `create_symlinks()` now excludes build/test scripts:
```bash
case "$BASENAME" in
    setup_fast.py|setup.py|demo.py|test_suite.py|test_integration.py)
        continue ;;
esac
```
Pushed in commit `a7d5050`. If VM has old installer, either update or manually `rm` the offending symlink:
```bash
rm ~/.hermes/hermes-agent/plugins/memory/mazemaker/setup_fast.py
```

### 11. Missing __init__.py on VM — Plugin Completely Ignored (2026-04-22)

**Symptom:** Test FAIL: `Hermes plugin installed: Missing: ~/.hermes/hermes-agent/plugins/memory/mazemaker/__init__.py`. Neural Memory tools not registered, no memory at all.

### 12. Symlink Import Problem in `is_available()` — Tools Never Registered (2026-04-23)

**Symptom:** `neural_remember`/`neural_recall`/`neural_think`/`neural_graph` NOT FOUND even after all other fixes. `is_available()` returns `False` even though `Memory()` works fine in isolation.

**Root cause:** The neural plugin uses **symlinks** to `~/projects/neural-memory-adapter/python/`. Python resolves `__file__` through symlinks to the real target directory — but `sys.path` only contained the symlink directory. When `is_available()` tried `from memory_client import Memory`, Python looked in the symlink dir for `memory_client`, `embed_provider`, etc. — not found → `is_available() = False`.

**File:** `~/.hermes/plugins/memory/mazemaker/__init__.py` — `NeuralMemoryProvider.is_available()`

**Fix:**
```python
# Resolve symlinks so imports work when running from the symlink
plugin_dir = str(Path(__file__).resolve().parent)
real_project_dir = str(Path(__file__).resolve().parent.parent.parent / "neural-memory-adapter" / "python")

for p in (plugin_dir, real_project_dir):
    if p not in sys.path:
        sys.path.insert(0, p)
```

### 13. `tools.neural_tools` Missing from Tool Discovery — Plugin Tools Never Loaded (2026-04-23)

**Symptom:** `neural_remember`/`neural_recall`/`neural_think`/`neural_graph` return "Unknown tool" — NOT in tool registry at all.

**Root cause:** `model_tools.py` `_discover_tools()` imports 20 tool modules explicitly. `tools.neural_tools` was NOT in the list — it existed on disk but was never imported at startup.

**File:** `~/.hermes/model_tools.py` — `_discover_tools()`

**Fix:** Add to `_modules` list:
```python
"tools.neural_tools",  # Neural memory tools (semantic storage/recall)
```

**Verification:**
```bash
cd ~/.hermes && python3 -c "
import model_tools
from tools.registry import registry
for name in ['neural_remember', 'neural_recall', 'neural_think', 'neural_graph']:
    e = registry._tools.get(name)
    print(f'{name}: {e.toolset if e else \"NOT FOUND\"}')"
# Should output: memory, memory, memory, memory
```

**Root cause:** Plugin loader requires `__init__.py` (line 108-111):
```python
init_file = provider_dir / "__init__.py"
if not init_file.exists():
    return None  # Plugin completely skipped
```
On the VM, the symlink is missing. Most likely cause: VM has an older clone of `neural-memory` repo that predates the `__init__.py` addition (commit `e4f33d9`).

**How to detect:**
```bash
ls -la ~/.hermes/hermes-agent/plugins/memory/mazemaker/__init__.py
# If missing or broken symlink → this bug
```

**Fix on VM:**
```bash
cd ~/jack-in-a-box/neural-memory
git pull origin master
bash install.sh install  # or manually: ln -s ~/jack-in-a-box/neural-memory/python/__init__.py ~/.hermes/hermes-agent/plugins/memory/mazemaker/__init__.py
```

**Why this breaks the entire hermes-agent <-> wonderland chain:**
No `__init__.py` → plugin not loaded → neural_remember/recall/think/graph tools not registered → LLM agent has zero memory capability → agent works but is amnesiac.

---
