---
name: runtime-snapshot-engine
category: software-development
description: Self-versioning state snapshots for ~/.daedalus internal state with WAL, branching, and auto-pruning
version: 1.0.0
tags: [snapshot, versioning, WAL, branching, content-addressed, daedalus-core]
priority: critical
created: 2026-04-20
---

# Runtime Snapshot Engine

Self-versioning state snapshots for the ~/.daedalus internal state directory. Provides git-like version control for runtime configuration, memory, and agent state without external dependencies.

## Core Concepts

### Content-Addressed Storage
- All snapshot data identified by SHA-256 hash of contents
- Automatic deduplication: identical content stored once regardless of branch/snapshot name
- Storage layout: `~/.daedalus/snapshots/objects/{hash_prefix}/{hash}`
- Enables efficient diff and rewind operations

### Write-Ahead Log (WAL)
The WAL ensures crash-safe state transitions:

```
Functions:
  wal_append(entry)      - Append operation to log with timestamp
  wal_flush()            - Force flush pending entries to disk
  wal_recover()          - Replay WAL on startup after crash
  wal_dedup(entry)       - Skip duplicate entries during replay
  wal_auto_prune(hours)  - Remove entries older than threshold (default: 72h)
```

WAL file location: `~/.daedalus/snapshots/wal.log`
Format: `{timestamp}|{operation}|{hash}|{metadata_json}`

### Branching
Git-like branching for snapshot timelines:

```
Functions:
  create_branch(name, from_ref=None)  - Create new branch from current or specified ref
  switch_branch(name)                  - Switch active branch (updates HEAD)
  list_branches()                      - List all branches with current marked
  delete_branch(name)                  - Remove branch (cannot delete protected)
```

Protected branches (cannot be pruned or deleted):
- `main` - Primary production state
- `stable` - Last known-good configuration

### Auto-Pruning
Retention strategy to prevent unbounded storage growth:

- Default retention: 3 days (72 hours)
- Prune candidates: snapshots older than retention on non-protected branches
- Protected branches are NEVER pruned
- Content-addressed objects pruned only when no branch references them

## Critical Pitfalls

### 1. SQLite Safe Copy
**NEVER snapshot a live SQLite database directly.** The journal/WAL files may be mid-transaction.

Correct pattern:
```python
import shutil
import sqlite3

def safe_snapshot_sqlite(db_path, snapshot_dir):
    # Close any open connections first
    # OR use VACUUM INTO for atomic copy
    conn = sqlite3.connect(db_path)
    conn.execute(f"VACUUM INTO '{snapshot_dir}/safe_copy.db'")
    conn.close()
    # NOW snapshot the safe copy
```

### 2. Global Variable Scoping
Snapshot state must NOT be stored in module-level globals. Multiple agent instances share the Python process and will corrupt each other's state.

WRONG:
```python
_current_branch = "main"  # Global - shared across agents!

def switch_branch(name):
    global _current_branch
    _current_branch = name
```

CORRECT:
```python
class SnapshotEngine:
    def __init__(self, daedalus_root):
        self._current_branch = "main"  # Instance-scoped
    
    def switch_branch(self, name):
        self._current_branch = name
```

### 3. Branch Protection in Prune
The prune function MUST check branch protection before deleting. A bug here destroys production state.

```python
def prune_snapshot(snapshot_ref):
    branch = get_branch_for_ref(snapshot_ref)
    if branch in PROTECTED_BRANCHES:
        raise ProtectedBranchError(f"Cannot prune from {branch}")
    # ... proceed with prune
```

## CLI Integration

### Commands (in run_agent.py)

```
/snapshot list              - List recent snapshots with timestamps
/snapshot create [msg]      - Create snapshot with optional message
/snapshot rewind <ref>      - Restore state to snapshot ref
/snapshot diff <a> <b>      - Show differences between two snapshots
/snapshot prune [hours]     - Prune snapshots older than hours (default: 72)
/snapshot head              - Show current HEAD snapshot

Aliases: /snap = /snapshot
```

### Debounced Hook Integration Pattern

Snapshots should NOT fire on every state change. Use debouncing in run_agent.py:

```python
import asyncio
from functools import partial

class SnapshotHook:
    def __init__(self, engine, debounce_seconds=5.0):
        self.engine = engine
        self.debounce = debounce_seconds
        self._timer = None
        self._pending = False
    
    def on_state_change(self, change_type, metadata):
        """Called by agent on any state mutation."""
        self._pending = True
        if self._timer:
            self._timer.cancel()
        self._timer = asyncio.get_event_loop().call_later(
            self.debounce,
            self._flush_snapshot
        )
    
    def _flush_snapshot(self):
        if self._pending:
            self.engine.create_snapshot("auto: debounced state change")
            self._pending = False
```

Integration point in run_agent.py agent loop:
```python
snapshot_hook = SnapshotHook(snapshot_engine)

# After any state mutation:
snapshot_hook.on_state_change("memory_update", {"file": filepath})
snapshot_hook.on_state_change("config_change", {"key": key})
```

## Storage Layout

```
~/.daedalus/snapshots/
  HEAD                    # Current branch/ref pointer
  branches/
    main                  # Branch ref files
    stable
    dev-*
  objects/
    ab/cdef1234...        # Content-addressed storage
  wal.log                 # Write-ahead log
  meta/
    snapshots.json        # Snapshot metadata index
    branches.json         # Branch configuration
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Snapshot list empty after crash | WAL not replayed | Run `wal_recover()` on startup |
| Duplicate snapshots | Debounce too short | Increase debounce_seconds |
| Cannot switch branch | Dirty working state | Create snapshot first |
| Prune deletes protected | Bug in branch check | Verify PROTECTED_BRANCHES set |
| SQLite corruption | Live DB snapshotted | Use VACUUM INTO pattern |
