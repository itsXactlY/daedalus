# PG Deadlocks durch parallele Schema-Setups — 2026-08-08

Befund: 59 Deadlocks in 6 h im PG-Log (`journalctl --user -u mazemaker-pgvector`),
xact_rollback=12 in pg_stat_database.

## Symptom (Log-Muster)
```
ERROR:  deadlock detected
DETAIL:  Process 333 waits for AccessExclusiveLock on relation 16822 of database 16384; blocked by process 336.
         Process 336 waits for ShareUpdateExclusiveLock on relation 16812 of database 16384; blocked by process 333.
         Process 333:
         CREATE TABLE IF NOT EXISTS dream_sessions (
         ...
         ON dream_sessions(started_at);
```
Relationen: dream_sessions / dream_insights / connection_history (OIDs via
`SELECT oid, relname FROM pg_class WHERE oid IN (16731, 16812, 16822)` auflösen).

## Wurzel
Jeder Container-Prozess (worker, mcp, bake, afe-window) führt beim Start
`_ensure_schema()` aus — `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS`
(im `_DREAM_PG_SCHEMA`-String und im `_BASE_SCHEMA`-Pfad). Diese Statements nehmen
AccessExclusiveLocks. Zwei parallele Container-Starts + ein schreibender Prozess
(die Live-Inserts des anderen Containers) = klassische Lock-Reihenfolge-Kollision.
PG wählt ein Victim und rolled es zurück.

## Fix (a16ccf8)
Session-Level-Advisory-Lock um das Schema-Setup in beiden Stores:
```python
cur.execute("SELECT pg_advisory_lock(%s)", (0x4D415A45,))  # 'MAZE'
try:
    cur.execute(_DREAM_PG_SCHEMA)   # bzw. _ensure_schema_locked(cur) im main-Store
finally:
    cur.execute("SELECT pg_advisory_unlock(%s)", (0x4D415A45,))
```
Der zweite Prozess wartet am Lock, findet alles existierend (IF NOT EXISTS = no-op)
und nimmt gar keine DDL-Locks mehr. Release im finally + automatisch bei
Connection-Close.

Verhaltens-Verifikation (ohne PG, mit Fake-Cursor): `_ensure_schema` auf einem
Fake-Store mit capturing `execute()` aufrufen (die gebundene
`_ensure_schema_locked`-Methode mit auf den Fake binden!) — Call-Order muss sein:
advisory_lock → DDLs → advisory_unlock, genau 1× lock + 1× unlock.

## Bloat-Befunde nach der Retention (gleiche Session)
| Tabelle | live | dead | Autovacuum | Größe | Bewertung |
|---|---|---|---|---|---|
| memories | 215.549 | 20.301 (8,6 %) | NIEMALS | 17 GB | < 20 %-Threshold → normal |
| connection_history | 5.742 | 0 | NIEMALS | 2,1 GB | **Bloat**: Platz der gelöschten 18M Rows nie zurückgegeben → VACUUM FULL |
| dream_sessions | 35.588 | 6.656 (15,8 %) | NIEMALS | 7,4 MB | ok |
| dream_insights | 81.035 | 0 | NIEMALS | 2,2 GB | P9-Retention hält sie |
| connections | 714.935 | 0 | 00:42 | 166 MB | sauber |
| memory_dae_embeddings | 215.417 | 2.113 | 23:11 | 2,3 GB | normal |

Regeln: dead ratio < 20 % ist UNTER der Autovacuum-Schwelle (kein Fehler);
nach großen Retention-DELETEs schrumpft die Tabellengröße nicht — VACUUM FULL
nur im Wartungsfenster (AccessExclusiveLock, nie während Bake/Worker laufen).
"NIEMALS"-Autovacuum bei hoher UPDATE-Rate (touch() auf memories) ist erwartbar,
bis der Threshold erreicht ist.

## Nebenbefund
5 der 1114 Fehlerzeilen waren eigene fehlerhafte psql-Queries (Spaltenname
`meta_key` existiert nicht — die Tabelle heißt `meta(key, value, updated_at)`;
`to_timestamp(timestamp with time zone)` existiert nicht — Spalte ist bereits
timestamptz). Erst `\d <tabelle>` prüfen, dann queryn.
