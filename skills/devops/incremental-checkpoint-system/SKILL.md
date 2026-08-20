---
name: incremental-checkpoint-system
description: "Incremental checkpoint/snapshot system — base + append-only deltas instead of full file rewrites"
tags: [checkpoint, snapshot, batch-processing, fault-tolerance, resume]
---

# Incremental Checkpoint System

Replace monolithic checkpoint files with a base + append-only deltas pattern.

## Problem

Traditional checkpoint systems rewrite the FULL state file after every unit of progress:
- 1000 completed items = full 1000-entry list rewritten each time
- File I/O grows linearly with progress
- Risk of corruption on crash mid-write (atomic writes help but still wasteful)

## Solution: Base + Deltas

### File Layout
```
checkpoint_base.json       # Written ONCE at run start
checkpoint_deltas.jsonl    # Append-only, one line per unit of progress
```

### Base File (written once)
```python
{
    "run_name": "my_run",
    "completed_prompts": [],   # Empty at start, or pre-populated on resume
    "batch_stats": {},
    "created_at": "2026-04-19T...",
    "format": "incremental_v1"
}
```

### Deltas File (append-only JSONL)
```json
{"batch_num": 0, "completed_prompts": [0,1,2], "batch_stats": {"processed":3,"skipped":0}, "timestamp": "..."}
{"batch_num": 1, "completed_prompts": [3,4,5], "batch_stats": {"processed":3,"skipped":0}, "timestamp": "..."}
```

Each delta is ~150-200 bytes regardless of total progress size.

## Implementation Pattern

### 1. Init base (once at run start)
```python
def _init_checkpoint_base(self, checkpoint_data):
    base = {
        "run_name": checkpoint_data["run_name"],
        "completed_prompts": list(checkpoint_data.get("completed_prompts", [])),
        "batch_stats": dict(checkpoint_data.get("batch_stats", {})),
        "created_at": datetime.now().isoformat(),
        "format": "incremental_v1",
    }
    atomic_json_write(self.checkpoint_base_file, base)
```

### 2. Append delta (per unit of progress)
```python
def _append_checkpoint_delta(self, batch_num, new_completed, batch_stats, lock=None):
    delta = {
        "batch_num": batch_num,
        "completed_prompts": sorted(new_completed),
        "batch_stats": batch_stats,
        "timestamp": datetime.now().isoformat(),
    }
    line = json.dumps(delta, ensure_ascii=False) + "\n"

    def _append():
        with open(self.checkpoint_deltas_file, 'a', encoding='utf-8') as f:
            f.write(line)

    if lock:
        with lock:
            _append()
    else:
        _append()
```

### 3. Load + reconstruct state (on resume)
```python
def _load_checkpoint(self):
    # Try incremental format first
    if self.checkpoint_base_file.exists():
        base = json.load(open(self.checkpoint_base_file))
        completed = set(base.get("completed_prompts", []))
        batch_stats = dict(base.get("batch_stats", {}))

        if self.checkpoint_deltas_file.exists():
            for line in open(self.checkpoint_deltas_file):
                if line.strip():
                    delta = json.loads(line)
                    completed.update(delta.get("completed_prompts", []))
                    bnum = delta.get("batch_num")
                    if bnum is not None:
                        batch_stats[str(bnum)] = delta.get("batch_stats", {})

        return {"completed_prompts": sorted(completed), "batch_stats": batch_stats, ...}

    # Fallback to legacy monolithic format
    if self.checkpoint_file.exists():
        return json.load(open(self.checkpoint_file))

    return {"completed_prompts": [], "batch_stats": {}, ...}
```

### 4. In processing loop
```python
for result in pool.imap_unordered(worker, tasks):
    # ... process result ...
    
    # APPEND delta — never rewrite
    self._append_checkpoint_delta(
        batch_num=result["batch_num"],
        new_completed=result["completed_prompts"],
        batch_stats=batch_stat_entry,
        lock=checkpoint_lock,
    )
```

## Key Properties

- **Append-only**: Deltas file only grows by appending lines. Never seeks or rewrites.
- **Lock-safe**: Append is a single write operation. Even with multiprocessing Lock, it's fast.
- **Crash-safe**: If process dies mid-append, you lose at most one delta line (the incomplete one). All prior deltas are intact.
- **Backward compatible**: Load function checks for legacy format as fallback.
- **Constant I/O per checkpoint**: Always ~200 bytes written regardless of total progress.

## When to Use

- Batch processing with many items (100+)
- Long-running jobs where checkpoint frequency matters
- Multiprocessing environments (append is lock-friendly)
- Resume-from-crash scenarios

## When NOT to Use

- Few items (< 20) — overhead isn't worth it
- State that can't be expressed as deltas (use full snapshots)
- Read-heavy checkpoint access (reconstructing from deltas is O(n) on deltas count)
