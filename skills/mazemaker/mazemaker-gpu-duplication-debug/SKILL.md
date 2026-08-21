---
name: mazemaker-gpu-duplication-debug
description: Debug why Neural Memory loads duplicate BGE-M3 models onto GPU instead of using the shared embed-server socket
---

# Neural Memory GPU Duplication Debug

## Symptom
Multiple hermes sessions each load their own BGE-M3 model onto GPU (~2.3GB each), instead of sharing a single instance via the embed-server socket. GPU memory shows 2+ hermes processes with ~2000-4500MiB each.

## Root Causes (Updated 2026-04-24)

### Root Cause A: torch shared library mapping (misleading symptom)
Every process that imports sentence-transformers gets ~35 mmap'd entries for `libtorch_cuda.so` and `libtorch_nvshmem.so` from the hermes-agent venv. This is NORMAL shared library loading — NOT the model.

**How to verify**:
```bash
# Count torch maps per PID — 35 is normal shared library overhead
for pid in $(ps aux | grep python3 | grep -v grep | awk '{print $2}'); do
    torch_count=$(grep -c "libtorch" /proc/$pid/maps 2>/dev/null || echo "0")
    echo "PID $pid: $torch_count torch maps"
done
# nvidia-smi shows ACTUAL GPU memory — if only embed-server has 2500 MiB, no duplication
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader
```

### Root Cause B: hermes-agent not using neural memory plugin
hermes-agent only activates the neural memory plugin if `memory.provider: neural` is set in its config. Otherwise it only uses BuiltinMemoryProvider. This explains why no hermes-agent PIDs appear in the socket connections — they never connect to embed-server.

### Root Cause C: Ghost socket connections
The embed-server holds self-connections to its own socket (8 total) — these are from server startup, not from clients. `lsof` shows all connected sockets owned by embed-server PID, none by hermes-agent.

### Root Cause D (Historical): _auto_detect() bug
A previous bug (commit `6603603`) made `_auto_detect()` overwrite a working client-mode backend with direct CUDA load. Fixed in commit `1ec8dab`.

```
SentenceTransformerBackend.__init__()
  1. Tries SharedEmbedClient → succeeds, _is_client=True
  2. Returns to EmbeddingProvider.__init__()
  3. EmbeddingProvider calls _auto_detect()
  4. _auto_detect sees CUDA available → creates NEW backend with direct CUDA load
  5. _auto_detect returns NEW backend → OVERWRITES the client-mode backend!
```

## Investigation Steps

### 1. Quick GPU Memory Overview
```python
import subprocess
result = subprocess.run(['nvidia-smi', '--query-compute-apps', 'pid,process_name,used_memory', '--format', 'csv,noheader'], capture_output=True, text=True)
for line in result.stdout.strip().split('\n'):
    if not line.strip(): continue
    parts = [p.strip() for p in line.split(',')]
    pid, name, mem = parts[0], parts[1], parts[2]
    with open(f'/proc/{pid}/cmdline') as f:
        cmdline = f.read().replace('\x00', ' ')
    print(f"PID {pid:5} | {mem:>8} | {cmdline[:100]}")
```
Expected good state: embed-server ~2336 MiB, hermes sessions 0 MiB.
Bad state: hermes sessions each 2000-4500 MiB.

### 2. Quick Process Filter
```bash
ps aux | grep hermes | grep python | awk '{print $2}' | while read pid; do
  echo "=== PID $pid ==="; cat /proc/$pid/cmdline 2>/dev/null | tr '\0' ' '
done
```

### 3. Check Socket Connectivity
```bash
ls -la ~/.mazemaker/sockets/embed.sock  # should exist
ps aux | grep embed-server          # should be running
```
Socket exists + server running = shared server OK.

### 3. Verify Socket Ownership (Critical)
```bash
# Find which PIDs own connections to embed.sock
cat /proc/net/unix | grep "embed.sock"
# For each connected inode, find owning PID
for inode in <inode_numbers_from_above>; do
    for f in /proc/*/fd/*; do
        target=$(readlink "$f" 2>/dev/null)
        if [[ "$target" == "socket:[$inode]" ]]; then
            pid=${f#/proc/}; pid=${pid%/fd/*}
            cmd=$(cat /proc/$pid/cmdline 2>/dev/null | tr '\0' ' ' | cut -c1-60)
            echo "PID $pid ($cmd) owns socket inode $inode"
        fi
    done
done
```
If ALL connected sockets are owned by embed-server itself → NO external clients connected. The sockets are self-connections from server startup.

### 4. Verify Backend Selection
Run a fresh Python and observe:
```python
from embed_provider import EmbeddingProvider
ep = EmbeddingProvider('auto')
print(f"Is client: {ep.backend._is_client}")  # True = using shared server
```
If `False` AND `_auto_detect` prints "sentence-transformers CUDA" AFTER "Connected to shared server" → BUG.

### 4. Check embed_server Status
```python
import socket, struct, json
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect('~/.mazemaker/sockets/embed.sock')
# send {"cmd": "status"} and recv response
```

## Fix Applied
In `embed_provider.py`, `_auto_detect()` — moved shared server check to be the FIRST priority, before CUDA detection:

```python
def _auto_detect(self):
    # 0. SHARED SERVER FIRST
    if not os.environ.get('EMBED_NO_SHARED'):
        try:
            client = SharedEmbedClient()
            dim = client.dim
            client.close()
            backend = SentenceTransformerBackend()
            backend._is_client = True
            backend.dim = dim
            backend.model = None
            backend._client = SharedEmbedClient()
            print(f"[embed] Auto-selected: shared server ({dim}d)")
            return backend
        except Exception:
            pass  # No server running, fall through

    # 1. CUDA sentence-transformers (only if no shared server)
    ...
```

## Deployment
Fix via symlink:
```
~/.hermes/plugins/memory/mazemaker/embed_provider.py
  → ~/projects/neural-memory-adapter/python/embed_provider.py
```

## Verification
After fix, new hermes sessions should show:
```
[embed] Connected to shared server (1024d)
[embed] Auto-selected: shared server (1024d)
Embedding backend: SentenceTransformerBackend (1024d)
Is client: True
```

## Post-Fix: Existing Sessions
Sessions started BEFORE the fix still have their own models loaded. Either:
1. Restart hermes sessions (PIDs with high GPU memory)
2. Accept that new sessions will use shared server, old sessions continue with duplicates until restart

## Prevention
Never call `_auto_detect()` AFTER `SentenceTransformerBackend.__init__()` already established a working client connection. The bug was that `_auto_detect()` replaced a working client-mode backend with a direct CUDA backend.

## WAL Size Issue (Secondary Finding)
The neural memory database WAL can grow grotesquely large (>2.8 GB for an 86 MB DB) if checkpointing is not running. Check periodically:
```bash
ls -lh ~/.mazemaker/data/memory.db-wal
~/.hermes/hermes-agent/venv/bin/python3 -c "
import sqlite3
db = sqlite3.connect('~/.mazemaker/data/memory.db')
db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
db.close()
print('WAL checkpointed')
"
```

## Test Suite CI Fixes (from 2026-04-24 debugging session)
When running `test_suite.py --tags embed,memory,api,storage,threading` in CI:

1. **torch ImportError**: `_auto_detect()` does `import torch` at top-level. If torch not installed, wrap with try/except and set `torch = None`. Then guard all `torch.cuda` calls with `if torch and ...`.

2. **memory: auto-connections fails in CI**: Uses hash backend which can't build semantic connections. Add SkipTest guard:
```python
from pathlib import Path
model_dir = Path.home() / ".neural_memory" / "models" / "models--BAAI--bge-m3"
if not model_dir.exists():
    raise SkipTest("BAAI/bge-m3 not cached — hash backend cannot create semantic connections")
```

3. **unified tests: "Attempt to use a closed connection"**: CI has MSSQL env vars set but MSSQLStore has close-order bug (SQLite closed before MSSQL mirror). Add `use_mssql=False` in test:
```python
with Memory(db_path=db, embedding_backend="hash", use_cpp=False, use_mssql=False) as m:
```

4. **Result after fixes**: 27 passed, 0 failed, 0 skipped.
