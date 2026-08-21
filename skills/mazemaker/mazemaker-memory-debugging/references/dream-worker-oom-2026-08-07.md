# Dream-Worker OOM 12.9 GB (status=137) — Analyse 2026-08-07 (READ-ONLY)

Korpus zur Analysezeit: 215k memories (1024-d BGE-M3 float32), ~708k connections,
9.1M connection_history rows/Tag (Spitze), 1.6M dream_insights rows/Tag (95% Duplikate).
Crash: status=137 nach ~28 min, Spitze 12.9 GB Host-RAM, Crash-Loop. Container-Limit 16 g
⇒ Kernel-OOM, nicht cgroup.

## In-Code dokumentierte Messungen (Quelle: Code-Kommentare, gelesen 2026-08-07)

- postgres_store.py:1007-1016 — GPU-Arm über `get_all()` auf 215,132 memories: **12.3 GB Peak**,
  Kernel-OOM-Kill; Ursachen: fetchall der ganzen Tabelle + dict pro Zeile + 215,132 × 1024
  Python-Floats ≈ 7 GB Objekte (24 B/Float + 8 B Pointer). Fix: `iter_for_gpu_arm` (Streaming,
  4096 Zeilen/Chunk, 16 MB/Chunk, Bytes auf GPU, Decode on-device).
- gpu_recall.py:176-182, 275-276 — gleiche 12.3-GB-Messung; „the CPU/GPU hybrid that made
  arming cost 12.3 GB“.
- dream_worker.py:167-169 — 5004 Zyklen/Tag (intervall 5 s statt konfigurierter 300 s) ⇒
  9.1M connection_history/Tag, 1.6M dream_insights/Tag.
- dream_postgres_store.py:447-458 — connection_history 18,241,313 Rows in 6 Tagen, ~3M/Tag,
  aus per-edge strengthen-Rows; Fix `MAZEMAKER_DREAM_HISTORY_PER_EDGE=0` (1 Summary-Row).
- dream_engine.py:1932-1948 — SUPERSEDES wuchs 25k → 515k in 90 min (≈8000 Edges/Zyklus),
  Fix: Curated-Gate + Cap 2000.

## RAM-Mathe (Konstanten)

| Form | Größe/Row (1024-d) | 215k Rows |
|---|---|---|
| SQLite-BLOB / np.float32 / pgvector-Wire-Bytes | 4 KB | 0.88 GB |
| Python `list[float]` (28 B/Float + 8 B/Pointer + Overhead) | ~37 KB | **~8.0–9.0 GB** |
| Connections-Dict (4-5 kleine Felder) | ~250–300 B | 708k ≈ 200–400 MB |

## Kandidaten-Ranking

### 1. HNSW-Vollrebuild über `store.get_all()` — memory_client.py:2069 (Trigger :2913-2917)
`_semantic_candidates`: PG-search → GPU → `_ensure_hnsw()`. `_ensure_hnsw` ruft
`store.get_all()` UNBEDINGT (auch für inkrementelles add_items). Dann :2111
`np.asarray(vecs)` + hnswlib `add_items` (M=16, ef=200, Kapazität 2×N).
RAM: 8–9 GB (get_all) + 0.9 GB (asarray) + 2.5–4 GB (hnswlib) ≈ **12–14 GB**.
Zündung: GPU-Recall unarmiert/fehlgeschlagen ⇒ REM-Fallback dream_engine.py:2164-2166
(`[self._memory.recall(q, k=10) for q in queries]`) ⇒ per-Query recall ⇒ HNSW.
Zeitpunkt: REM im 1. Zyklus ≈ 20–28 min auf 215k-Korpus. **Bester Fit für 12.9 GB + 28 min + Crash-Loop.**

### 2. GPU-Arm-Fallback `load_from_store` — gpu_recall.py:260 / memory_client.py:1733-1774
SQLiteStore hat kein `iter_for_gpu_arm` ⇒ Fallback `rows = store.get_all()` (8–9 GB),
dann pro Zeile `torch.as_tensor` (rowvecs, +0.9 GB) + `torch.stack(...).to(cuda)` (+0.9 GB)
⇒ **~10.5–12.3 GB** (die gemessenen 12.3 GB!). Pfad: Cache-Build schlägt fehl
(memory_client.py:1723) oder Stale-Rebuild wirft (:1688-1689, `self._gpu` bleibt None).

### 3. DAE-`get_all()` — dae.py:671
`use_engine_tensor` verlangt `gpu._emb_tensor`; RemoteGpuRecallClient (embed_provider.py:642)
hat nur `_loaded` ⇒ False ⇒ `for m in store.get_all(): vectors[mid]=np.asarray(emb)` (8–9 GB
+ 0.9 GB np). Ohne CUDA zusätzlich `_cpu_mix_per_memory` mit insert_rows-Akkumulation (0.9 GB).
DAE läuft im 1. Zyklus (dream_engine.py:2885-2888: cycle_index==0 passiert Gate) ≈ 25–28 min.
⇒ **~10–11 GB — nahe, aber unter 12.9.**

### 4. build_gpu_cache.build — build_gpu_cache.py:26-96
fetchall(id,label,content,embedding) + contents-Kopie + json.dump aller Inhalte + np.empty 0.88 GB
⇒ **~2.5–3 GB** (Startup). Nicht die Ursache.

### 5. Insight `get_connections()` — dream_engine.py:2266, SQLiteDreamBackend:591, DreamPostgresStore:270
Volltabellen-fetchall ohne LIMIT, aber kleine Felder ⇒ **200–400 MB** (Claude korrekt).

### 6. ColBERT — colbert_helper.py — per-ID über Worker (`/embed_colbert`), fp16 64 KB/Memory,
nur bei MM_COLBERT_ENABLED=1 ⇒ widerlegt.

### Zeitliche Akkumulation
Keine wachsende RAM-Struktur über Zyklen gefunden. `_gpu_ppr_adj`-Rebuilds
(memory_client.py:3980-4058, dirty nach jeder Write-Invalidierung :4060-4063) = Churn
(~200–400 MB/Rebuild), nicht 12 GB. Das 28-min-Muster ist Phasen-Zeitpunkt (REM/DAE), keine Akkumulation.

## Synthesis 0-Proposals (30 Cluster gesehen)

Stats-Lesen: `clusters_synthesised` lokalisiert die Ursache.
1. **TTL-Mismatch** (strukturell): NREM prunt derived:cluster mit 5-min-TTL
   (dream_engine.py:1859-1861, `_prune_old_derived_clusters(keep_seconds=5*60)`),
   Synthesis-Anker-Fenster 3600 s (dream_engine.py:3427, 3434-3443) ⇒ alte Anker ohne
   derived-Memory ⇒ `if not drow: continue` (:3477-3478). Insight-Anti-Replay (6h,
   :2359-2363) ⇒ <30 frische Cluster/Zyklus ⇒ Rest des 30er-Fensters sind Tote-Rows.
2. **AFE-Mitglieder-Gate**: `WHERE m.label LIKE '%::afe::%'` (:3491) + `min_facts=3` (:3428,
   :3494). derived_from-Links capped auf 200 Community-Mitglieder (:2638), meist auto:-Turns;
   AFE-Fakten sind separate ::afe::-Memories. Bench-Logs zeigen real `AFE: written=0`.
3. **LLM-Transport** (synthesis.py:153-240): HTTP zuerst; 404/Timeout ⇒ CLI `ollama run`;
   fehlendes Default-Modell `alibayram/smollm3` ⇒ CLI zieht Modell ⇒ 60-s-Timeout ⇒ `[]`
   (:230-232). „ollama 200 OK“ kann nur der `/api/tags`-Probe sein (:182-188).
4. **Parse/Filter**: kein `[...]` ⇒ `[]` (:256-257); Items ohne evidence_indices verworfen
   (:274-275); `min_evidence=2` (:343/:354) verwirft Single-Evidence; `min_confidence=0.5`
   (:341/:383). conf(1 Evidence, sim 1.0) = 0.82 ⇒ conf ist selten der Filter, min_ev schon.

## Insight-Flush

RAM-sicher (Puffer ≤ 50 Cluster + Bridge-Rows, real 2k–16k kleine Tupel ≈ 5–15 MB; 1
executemany + 1 Commit, SQLiteDreamBackend:1114-1141). Zeitfresser = Write-Amplifikation:
connection_history (24k Rows/Zyklus, 3M/Tag), dream_insights-Explosion, SQLite-WAL,
PG-FK-Verletzung im derived-cluster-Prune („violates foreign key constraint
connections_target_id_fkey“, dream_s_full.log).

## Phasen-Zeiten (Bench-Logs, gleiche Engine-Linie, 33k-334k-Korpus)

- Kompletter Zyklus: 48–162 s; **+400–1100 s wenn DAE läuft** (DAE schreibt 19k–334k Vektoren).
- NREM: 4k verarbeitet, +24k–71k gestärkt, −12k bis −254k geschwächt, ~500–700 geprunt.
- SUPERSEDES: in allen Bench-Logs 0 (Curated-Gate); Produktion bis 2000/Zyklus gecappt.
- REM: 8.5k–17.5k Bridges/Zyklus. INS: communities 1k–13.5k, insights 2k–16k, derived=50.
- AFE: 4–5 s (regex-only). DAE: teuerster Block.
- Produktion 215k/708k: Zyklus ≈ 25–45 min ⇒ REM ~20–28 min, DAE (1. Zyklus) ~25–28 min.

## Offene Punkte / Verifikation

- Welcher get_all()-Pfad im konkreten OOM-Lauf zündet, hängt vom Arm-Zustand ab:
  memprobe/BISECT_PHASES (nrem,supersedes,rem,insight) lokalisieren; Logs nach
  „GPU recall ARMED“, „load_from_store“, „cache STALE“ durchsuchen.
- Bei SQLite-Worker: Cache-Fingerprint (memory_client.py:1651-1671) ⇒ stale bei wachsender
  DB ⇒ Rebuild bei jedem Start (2.5–3 GB) einplanen.
- Fix-Status: PG-Arm streaming (iter_for_gpu_arm) ist FIX; SQLite get_all()-Pfade
  (HNSW, load_from_store-Fallback, DAE) sind Stand 2026-08-07 noch offen.

## Update Abend 2026-08-07 (THESE-E-Verifikation) — AUFLÖSUNG

Der konkrete Kill-Mechanismus der Abend-Kills (12.4–12.8 GB, 3× oomd) war **weder**
Kandidat 1 noch 2/3: Kein HNSW-Build, kein Arm-Fallback, kein DAE (Logs belegen
Streaming-Arm "streamed 215243 vectors onto cuda" + "DAE recall channel intentionally
unwired"). Die Halter waren `_load_from_store()`-Vollmaterialisierung in `_graph_nodes`
(RssAnon 10.4 GB in `Mazemaker.__init__`, nach abgeschlossenem Arm) + Engine-
`_contents/_labels` — gehalten, kein Spike (Kill 30 min nach Zyklusende bei idle).
oomd-Kill-Grund = User-Slice-Druck 83.5–87 % > 80 % > 20 s (nicht das Unit-Limit;
OOMScoreAdjust 500 = designiertes Opfer). Fix 94cdc80 (lazy_graph +
`include_embeddings=not _armed`) committet 21:12 UTC, aber Image (20:25 UTC) war älter
⇒ alle Abend-Runs liefen pre-Fix. Details + Limits-Arithmetik + RAM-Halte-Karte:
`references/dream-worker-steady-state-2026-08-07.md`.
