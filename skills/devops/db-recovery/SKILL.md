---
name: db-recovery
category: devops
description: Recover and sync neural memory databases after system failure (SQLite + MSSQL triangular comparison and merge)
triggers:
  - neural memory corrupted
  - database sync sqlite mssql
  - memory database recovery
  - benchmark data cleanup
  - embedding magnitude mismatch
---

# Neural Memory DB Recovery & Sync

## When to Use
After system failure (BTRFS snapshot restore, disk corruption) where SQLite and MSSQL may be out of sync or contain garbage data.

## Phase 1: Assessment (READ-ONLY)

### Compare all three databases
```python
# memory.db (big, ~248MB) - check freelist bloat
# memory_.db (small, ~55MB) - check if has migration markers
# MSSQL - check for benchmark garbage

# Key metrics:
# - Freelist pages (PRAGMA freelist_count) = dead space
# - connection_history row count = dream engine bloat
# - Label distribution = noise detection
# - Migration markers: "SNAPSHOT RESTORE", "MIGRATION COMPLETE", "FastEmbed"
```

### Determine canonical DB
The DB with migration markers and lower freelist count is canonical. Usually `memory_.db` after fastembed migration.

### Check MSSQL backup
```sql
RESTORE HEADERONLY FROM DISK = '/path/to/backup.bak'
RESTORE FILELISTONLY FROM DISK = '/path/to/backup.bak'
-- If "media set has 2 media families" = striped backup, unusable if only 1 file
```

## Phase 2: Filter Quality MSSQL Memories

### CRITICAL: Strict garbage filter
MSSQL often contains benchmark data that looks like quality memories. Use MULTIPLE filters:

```python
import re
DD_PATTERN = re.compile(r'^DD\d+')  # Catches DD1-DD999

PERSON_NAMES = ['Caroline', 'Melanie', 'Maria', 'John', 'Nate', 'Joanna', 
                'Sarah', 'Mike', 'Emily', 'David']

GARBAGE_LABELS = ['turn-', 'session-summary', 'msg:', 'pre-compress', 
                  'asst-msg', 'user-msg']

GARBAGE_CONTENT = ['[SUPERSEDED]', 'Review the conversation', 
                   'review the conversation', 'based on the system prompt',
                   'welcome to hermes agent', 'type your message',
                   'SYSTEM: If you have nothing new', 'pytest test:']

# Filter logic:
if DD_PATTERN.match(label): skip
if any(name in label for name in PERSON_NAMES): skip
if 'said, "' in content[:100] and 'shared a photo' in content: skip
if content.startswith('[') and 'am on' in content[:60] and 'said,' in content[:200]: skip
if any(label.startswith(g) for g in GARBAGE_LABELS): skip
if any(g in content for g in GARBAGE_CONTENT): skip
if len(content) < 30: skip
```

### Fingerprint deduplication
```python
# Check label + content prefix against existing SQLite
fingerprint = (label, content[:200])
if fingerprint in sqlite_fingerprints: skip
```

## Phase 3: Import & Consolidate

### SQLite operations
```python
# 1. Rename memory.db → memory_old.db (backup)
# 2. Rename memory_.db → memory.db (canonical)
# 3. Import quality MSSQL memories
# 4. VACUUM to reclaim space
# 5. PRAGMA integrity_check
```

### Embedding normalization
**CRITICAL**: All embeddings must have consistent magnitude!
- FastEmbed produces raw vectors (magnitude ~28)
- Old sentence-transformers may have different magnitudes
- For Python path: L2-normalize all to unit vectors
- For C++ path: Keep raw (Hopfield network learns from raw patterns)

```python
# Normalize all embeddings to unit length
for mid, emb in all_embeddings:
    vec = struct.unpack('1024f', emb)
    mag = math.sqrt(sum(v*v for v in vec))
    if mag > 0:
        normalized = [v/mag for v in vec]
        c.execute('UPDATE memories SET embedding=? WHERE id=?', 
                  (struct.pack('1024f', *normalized), mid))
```

## Phase 4: MSSQL Sync

### Correct table structure
```
memories table:    id, label, content, embedding(varbinary), vector_dim, salience, created_at, last_accessed, access_count
NeuralMemory table: surrogate_id, legacy_id, vector_data(varbinary), vector_dim, metadata_json, created_at, updated_at, access_count, last_accessed, content_hash, category, id(computed)
connections table: id, source_id, target_id, weight, edge_type, created_at (FK to memories.id)
```

### Import order (FK constraints!)
1. `SET IDENTITY_INSERT memories ON`
2. INSERT memories with original IDs
3. `SET IDENTITY_INSERT memories OFF`
4. INSERT connections (FK to memories.id)
5. INSERT dream_sessions

### Batch operations
```python
# Use batch_size=100 for memories, 5000 for connections
# Commit every batch to avoid timeout
```

## Phase 5: C++ Bridge Considerations

### Hopfield Network Bias
The C++ bridge's Hopfield network learns patterns from loaded data. If loaded with biased data (e.g., 1000+ benchmark memories), it will ALWAYS return those results with ~0.967 similarity regardless of query.

**Solution**: Set `use_cpp=False` in `__init__.py` until C++ bridge can be retrained/reset. Python path with FastEmbed is 0.5-0.7s recall — fast enough.

### If C++ is required
The C++ bridge code needs modification to:
1. Reset Hopfield network after loading
2. Or use episodic memory (flat vector store) instead of Hopfield
3. Or add a `reset()` method to clear learned patterns

## Common Pitfalls

1. **Wrong MSSQL table**: INSERT into `memories`, NOT `NeuralMemory` (different schema)
2. **FK constraints**: Import memories BEFORE connections
3. **IDENTITY_INSERT**: Must be ON to preserve SQLite IDs
4. **Embedding magnitude**: Must be consistent across ALL memories
5. **C++ Hopfield bias**: Can't be fixed by re-embedding — needs code change
6. **Timeout**: Use background process for re-embedding 2000+ memories
7. **Striped backups**: MSSQL backups with 2+ media families need ALL files
8. **VACUUM fails**: Check integrity first, try REINDEX then VACUUM

## Verification
```python
# 1. Count match
assert mssql_memories == sqlite_memories

# 2. Content match (sample)
assert first_5_content_match

# 3. Embedding magnitude consistency
assert all(magnitude > 20 for raw) or all(magnitude ~1.0 for normalized)

# 4. Recall quality
results = memory.recall('SOLID OOP principles', k=3)
assert 'SOLID' in results[0]['label']  # Not bench-math!

# 5. Performance
assert recall_time < 1.0  # seconds
```
