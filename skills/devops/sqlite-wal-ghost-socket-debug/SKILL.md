---
name: sqlite-wal-ghost-socket-debug
description: Debug SQLite WAL bloat and Unix domain socket ghost connections — when PRAGMA wal_checkpoint returns BUSY and ss shows orphaned socket pairs.
---

# SQLite WAL + Unix Socket Debugging

## Context
When investigating SQLite WAL bloat (19 GB WAL with only 84 MB DB) and ghost socket connections.

## Problem Symptoms
1. `PRAGMA wal_checkpoint(TRUNCATE)` returns `(1, X, Y)` = BUSY, WAL never shrinks
2. `ss -x` shows many ESTABLISHED connections to a Unix socket, all owned by one PID
3. Multiple Python processes have the DB + WAL + SHM files open directly
4. torch CUDA libs mapped in hermes-agent but nvidia-smi shows 0 MiB GPU

## Diagnostic Workflow

### Step 1: WAL Analysis
```bash
sqlite3 ~/.mazemaker/data/memory.db "PRAGMA wal_checkpoint(TRUNCATE)"
ls -lh ~/.mazemaker/data/memory.db*     # WAL size
sqlite3 ~/.mazemaker/data/memory.db "PRAGMA journal_mode"
sqlite3 ~/.mazemaker/data/memory.db "PRAGMA wal_autocheckpoint"
sqlite3 ~/.mazemaker/data/memory.db "PRAGMA page_count"
```

**Return code meanings:** `(0, frames, pages) = OK`, `(1, frames, pages) = BUSY`, `(2, ...) = ERROR`

### Step 2: Process + Socket Investigation
```bash
# Find all processes with DB files open
for pid in $(pgrep -a python | cut -d' ' -f1); do
  count=$(ls /proc/$pid/fd 2>/dev/null | xargs -I{} readlink /proc/$pid/fd/{} 2>/dev/null | grep -c "memory.db" || echo 0)
  [ "$count" -gt 0 ] && echo "PID $pid: $count DB refs"
done

# ss shows ALL sockets on the Unix socket with owner PID
ss -x -p 2>/dev/null | grep embed.sock

# Find KERNEL-LEVEL peer sockets NOT in any /proc/*/fd
# These are client-side sockets that have been closed by the client
# but the server still thinks they're ESTABLISHED (ghost sockets)
```

### Step 3: WAL + Checkpoint
```python
import sqlite3
db = "/path/to/memory.db"
conn = sqlite3.connect(db)
# Try checkpoint
result = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
print(result)  # (1, X, Y) = BUSY, (0, X, Y) = OK
conn.close()
```

### Step 4: wal_autocheckpoint tuning
```python
# Raise from default 1000 pages to 100000 pages (~400 MB)
conn.execute("PRAGMA wal_autocheckpoint=100000")
conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")  # May still return BUSY
```

## Key Findings

### Ghost Socket Root Cause
Unix sockets have 2 sides (server + client). When client calls `close()` but server hasn't called `accept()` on that connection yet:
- The socket pair exists in kernel (`ss` shows ESTABLISHED)
- Client side socket is NOT visible in `/proc/<client_pid>/fd` (closed)
- Server side appears in `/proc/<server_pid>/fd` with accepted fd
- Result: `ss` shows connections from server PID only

If all peer inodes are NOT found in any `/proc/*/fd` → clients have closed their sockets → ghost/orphaned connections.

### WAL Cannot Truncate With Open Readers
WAL TRUNCATE requires ALL connections to close their WAL read transactions. With 4 concurrent sessions, at least one has a long-lived read transaction → checkpoint blocked → WAL grows forever.

### torch CUDA Maps ≠ Model on GPU
Python processes mapping `libtorch_cuda.so` 35x times (full torch) is normal overhead from `import torch`. Does NOT mean the ML model is loaded into GPU VRAM. Check `nvidia-smi --query-compute-apps` to see actual GPU memory consumers.

## Fixes

### WAL Growth Fix
1. Raise `wal_autocheckpoint`: `PRAGMA wal_autocheckpoint=100000`
2. For immediate reclaim: all sessions must close DB connections → then `PRAGMA wal_checkpoint(TRUNCATE)` works
3. Or: switch to `PRAGMA journal_mode=DELETE` (no WAL, no concurrent read perf)

### Ghost Socket Fix
Restart the server process → kills all accepted (ghost) connections. New connections will work properly.

### Proper Architecture
- Shared embed server (one process with model on GPU) + many clients via socket = GOOD
- Multiple processes all direct-loading model = BAD (VRAM duplication)
- Multiple processes all using SQLite WAL directly = WAL bloat (need checkpoint coordination)

## Files Investigated
- `~/.mazemaker/data/memory.db` — main SQLite DB
- `~/projects/neural-memory-adapter/python/memory_client.py` — SQLiteStore with WAL
- `~/.hermes/plugins/memory/mazemaker/embed_provider.py` — SharedEmbedClient + SentenceTransformerBackend
- embed-server.py PID 1687204 — shared embed server with BAAI/bge-m3 on GPU
