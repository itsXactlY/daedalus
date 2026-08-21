---
name: mazemaker-benchmark-cleanup-sync
description: Clean benchmark/test data from Mazemaker (SQLite + MSSQL) and sync SQLite → MSSQL. Handles schema differences, timestamp conversion, and pyodbc quirks.
version: 1.0
created: 2026-04-21
---

# Mazemaker Benchmark Cleanup + SQLite→MSSQL Sync

## When to Use
Neural memory graph shows benchmark data (labels like `bench-math-*`, `bench-technology-*`, `bench-art-*`) polluting real memories. Or need to sync clean SQLite → MSSQL after cleanup.

## Step 1: Backup Both Databases

```bash
# SQLite backup (WAL checkpoint first)
sqlite3 ~/.mazemaker/data/memory.db "PRAGMA wal_checkpoint(FULL);"
mkdir -p ~/.local/backups/mazemaker
cp ~/.mazemaker/data/memory.db ~/.local/backups/mazemaker/memory-$(date +%Y%m%d_%H%M%S).db

# MSSQL backup (must use /tmp, MSSQL user can't write to /home/)
sqlcmd -S 127.0.0.1 -U sa -P '<password>' -C -Q "
BACKUP DATABASE [NeuralMemory] TO DISK = N'/tmp/NeuralMemory-backup-$(date +%Y%m%d_%H%M%S).bak' 
WITH FORMAT, INIT, COMPRESSION;
"
sudo cp /tmp/NeuralMemory-backup-*.bak /home/
sudo chown alca:alca /home/NeuralMemory-backup-*.bak
```

## Step 2: Clean SQLite

```bash
# Check benchmark count first
sqlite3 ~/.mazemaker/data/memory.db "SELECT COUNT(*) FROM memories WHERE label LIKE 'bench-%';"

# Delete connections to/from benchmark memories
sqlite3 ~/.mazemaker/data/memory.db "
DELETE FROM connections 
WHERE source_id IN (SELECT id FROM memories WHERE label LIKE 'bench-%')
   OR target_id IN (SELECT id FROM memories WHERE label LIKE 'bench-%');
"

# Delete benchmark memories
sqlite3 ~/.mazemaker/data/memory.db "DELETE FROM memories WHERE label LIKE 'bench-%';"

# Clean orphaned connections
sqlite3 ~/.mazemaker/data/memory.db "
DELETE FROM connections 
WHERE source_id NOT IN (SELECT id FROM memories)
   OR target_id NOT IN (SELECT id FROM memories);
"

# Compact
sqlite3 ~/.mazemaker/data/memory.db "VACUUM;"
```

## Step 3: Clean MSSQL (Quick Method)

```bash
sqlcmd -S 127.0.0.1 -U sa -P '<password>' -C -Q "
USE NeuralMemory;
DELETE FROM dbo.connections;
DELETE FROM dbo.dream_insights;
DELETE FROM dbo.dream_sessions;
DELETE FROM dbo.connection_history;
DELETE FROM dbo.memories;
DBCC CHECKIDENT ('dbo.memories', RESEED, 0);
DBCC CHECKIDENT ('dbo.connections', RESEED, 0);
"
```

## Step 4: Sync SQLite → MSSQL (pyodbc)

**CRITICAL SCHEMA DIFFERENCES** (pyodbc will fail without these):

| Column | SQLite | MSSQL |
|--------|--------|-------|
| timestamps | REAL (unix epoch) | datetime2 |
| vector_dim | ❌ not in schema | INT NOT NULL |
| connection type | `edge_type` | `edge_type` |
| connection ts | `created_at` (nullable) | `created_at` (nullable) |

```python
import sqlite3, pyodbc
from datetime import datetime, timezone

SQLITE_DB = "~/.mazemaker/data/memory.db"
EMBEDDING_DIM = 1024  # from neural_graph stats

def epoch_to_dt(epoch):
    if epoch is None: return None
    return datetime.fromtimestamp(float(epoch), tz=timezone.utc)

# Connect
s = sqlite3.connect(SQLITE_DB); s.row_factory = sqlite3.Row
m = pyodbc.connect(
    "DRIVER={ODBC Driver 18 for SQL Server};SERVER=127.0.0.1;"
    "DATABASE=NeuralMemory;UID=sa;PWD=<password>;TrustServerCertificate=yes;"
)

# Sync memories (preserving IDs with IDENTITY_INSERT)
for mem in s.execute("SELECT * FROM memories ORDER BY id"):
    emb = mem['embedding']
    vdim = len(emb)//4 if emb else EMBEDDING_DIM
    m.cursor().execute("""
        SET IDENTITY_INSERT memories ON;
        INSERT INTO memories (id, label, content, embedding, vector_dim, salience, created_at, last_accessed, access_count)
        VALUES (?,?,?,?,?,?,?,?,?);
        SET IDENTITY_INSERT memories OFF;
    """, mem['id'], mem['label'], mem['content'], emb, vdim,
        float(mem['salience'] or 1.0), epoch_to_dt(mem['created_at']),
        epoch_to_dt(mem['last_accessed']), mem['access_count'] or 0)
m.commit()

# Sync connections
for c in s.execute("SELECT source_id, target_id, weight, edge_type FROM connections"):
    m.cursor().execute("""
        INSERT INTO connections (source_id, target_id, weight, edge_type, created_at)
        VALUES (?,?,?,?,?);
    """, c['source_id'], c['target_id'], float(c['weight'] or 1.0),
        c['edge_type'], datetime.now(tz=timezone.utc))
m.commit()
```

## Pitfalls
- **MSSQL backup to /home/ fails** — mssql user has no write permission. Use `/tmp` then `sudo cp`
- **`float incompatible with datetime2`** — SQLite stores epoch floats, MSSQL needs `datetime.fromtimestamp()`
- **`column 'vector_dim' does not allow nulls`** — MSSQL has `vector_dim INT NOT NULL`, SQLite doesn't. Calculate from `len(embedding)//4`
- **`no such column: type`** — SQLite uses `edge_type`, not `type`
- **pyodbc row-by-row insert is slow** for 119K connections (~30s). Use `executemany` or bulk copy for larger datasets
- **`SET IDENTITY_INSERT`** — Required because we preserve original IDs. Must turn OFF after each insert
- **Duplicate connections** — SQLite unique index is on `(source_id, target_id, edge_type)`. MSSQL may skip some NULL edge_type rows
- **MSSQL password** — stored at `memory.neural.dream.mssql.password` in `~/.hermes/config.yaml`

## Verification
```bash
# SQLite
sqlite3 ~/.mazemaker/data/memory.db "SELECT COUNT(*) FROM memories; SELECT COUNT(*) FROM connections; SELECT COUNT(*) FROM memories WHERE label LIKE 'bench-%';"

# MSSQL
sqlcmd -S 127.0.0.1 -U sa -P '<password>' -C -Q "
SELECT COUNT(*) FROM NeuralMemory.dbo.memories;
SELECT COUNT(*) FROM NeuralMemory.dbo.connections;
SELECT COUNT(*) FROM NeuralMemory.dbo.memories WHERE label LIKE 'bench-%';
"
```

## Related
- Neural memories: 24500 (Chrome fix), 24504 (skill link)
- SQLite DB: `~/.mazemaker/data/memory.db`
- MSSQL: `127.0.0.1`, database `NeuralMemory`, user `sa`
- Backups: `~/.local/backups/mazemaker/` (SQLite), `/home/NeuralMemory-backup-*.bak` (MSSQL)
