# Connection-Pool-Leak in dream_stats (2026-08-08, fix d9be763)

## Symptom
The pod looked hung while doing NOTHING: every new Postgres connection failed
with `sorry, too many clients already` — even psql could not get in.

## Root cause
`memory_client.py` dream_stats() (the `mazemaker_dream_stats` tool path) did,
inline, per call:

    stats = DreamPostgresStore().get_dream_stats()

Each `DreamPostgresStore` builds a `ConnectionPool(min_size=1, max_size=8)`.
Nothing ever closed it, and psycopg_pool starts a worker thread per pool, so
the object is not collected promptly either — the connections simply stay
open. Every dream_stats call therefore leaked up to 8 connections.

## Measured
- 100 of 100 Postgres backends held, EVERY ONE idle, ages staggered
  10 / 11 / 12 / 15 / 25 minutes.
- 100 / pool max 8 ≈ 13 leaked instances — matches the tool-call count.
- xact_rollback / deadlock counters were NOT the cause; this is a pure
  connection-exhaustion leak.

## Fix
Create once, reuse:

    if getattr(self, "_dream_stats_backend", None) is None:
        self._dream_stats_backend = DreamPostgresStore()
    stats = self._dream_stats_backend.get_dream_stats()

## Audit rule (applies to any psycopg/DB store)
Audit EVERY `= Store()` / `= DreamPostgresStore()` instantiation site:

    grep -rn '= DreamPostgresStore()\|= PostgresStore()' python/*.py | grep -v 'self\.'

- assign-to-self (mazemaker.py:138, memory_client.py:1426) → fine
- once-per-process (dream_worker.py:319, dream_engine.py:1408) → fine
- one-shot scripts (migrate_*.py, postgres_store.py `__main__`) → fine
- **bare inline instantiation in a per-call path (tools, stats, health,
  status endpoints) → LEAK.** psycopg_pool's worker thread keeps the object
  alive even after the caller drops it, so GC does not save you.

## Verification
After the fix, `SELECT count(*) FROM pg_stat_activity` should stay flat (7
normal connections, not climbing per dream_stats call); `pg_stat_database`
deadlocks/xact_rollback unchanged.
