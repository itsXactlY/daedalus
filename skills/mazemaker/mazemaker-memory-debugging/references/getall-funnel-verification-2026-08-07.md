# get_all-Funnel-Verifikation (THESE A) — 2026-08-07, HEAD b415570 (READ-ONLY audit)

Verification that `get_all()` Python-float materialization is THE corpus-scale bottleneck and that no
correctly chunked path exists for SQLite. Corpus: 215,132 memories × 1024-d float32 BGE-M3.

## Urteil

BESTÄTIGT: jede korpus-skalierende Operation, die nicht über den armierten GPU-Tensor läuft, fällt in
`get_all()` zurück. Die 2026-08-07-Fixes heilten exakt zwei Stellen (PG-GPU-Arm, `_load_from_store`);
HNSW, SQLite-Arm-Fallback, DAE-CPU, Brute-Force und FTS-Fallbacks materialisieren weiterhin.
Präzisierungen: (1) "1f1beb1" existiert nicht — GPU-native Decode ist `38a0efc`; (2) PG hat mit
`iter_for_gpu_arm` (Arm) + `search_semantic` (In-DB-pgvector-HNSW) korrekte Nicht-Materialisierungs-Pfade —
"kein einziger" gilt exakt für den SQLite-Defaultpfad.

## Call-Site-Inventar (K1, beide Repos)

mazemaker-pro/python (heiß = Recall/Remember/Dream-Zyklus):
- dae.py:671 `for m in store.get_all():` — HEISS, DAE-CPU-Pfad (kein GPU-Engine-Tensor; RemoteGpuRecallClient embed_provider.py:642 hat kein `_emb_tensor`). Einziger Umweg: dae.py:665-669 Engine-Tensor-Sentinels.
- gpu_recall.py:260 `rows = store.get_all()` — HEISS (einmalig pro Prozess), Arm-Fallback für Stores ohne `iter_for_gpu_arm` (SQLite/MSSQL).
- memory_client.py:1114/:1157 `for m in self.get_all():` — WARM, search_bm25/search_entity FTS-Fallback; FALLBACK_SCAN_CAP=10k begrenzt nur die Scan-Schleife, NICHT die get_all()-Materialisierung.
- memory_client.py:1927/:1930 `get_all(include_embeddings=not _armed)` — HEISS, `_load_from_store` (Startup); geheilt wenn armiert (94cdc80).
- memory_client.py:2130 `mems = self.store.get_all()` — HEISS, `_ensure_hnsw`; UNBEDINGT auch für inkrementelle adds (Entscheidung can_increment erst :2146); Zündung über `_semantic_candidates` :3022 und auto-connect :2580.
- memory_client.py:3048 `for mem in self.store.get_all():` — HEISS, `_semantic_candidates`-Brute-Force (letzte Stufe der Kette PG-native → GPU → HNSW → C++).
- memory_client.py:4838 `for r in store.get_all():` — KALT-WARM, afe_facts-Fallback nur für Stores ohne search_by_label_prefix.
- test_suite.py:187 — KALT (Tests). postgres_store.py:992 — eigene Definition.
- KEIN Funnel: `_find_conflicts` memory_client.py:2656 ist DEAD CODE (nie aufgerufen); remember() nutzt indexed `find_by_label` (2221-2260).

Alt-Repo (~/projects/mazemaker, Vorbild-Zustand): 1065/1108 (FTS-Fallbacks), 1814 (`_load_from_store` mit
BEDINGUNGSLOSEM get_all — der 12,9-GB-Zustand vor 94cdc80), 1984 (`_ensure_hnsw`), 2465 (toter
`_find_conflicts`), 2828 (Brute-Force), 4592 (afe_facts). dream_engine.py/synthesis.py/colbert_helper.py/
dream_postgres_store.py: KEIN get_all.

## RAM-Rechnung (215.132 × 1024-d float32)

| Pfad | Datei:Zeile | Peak Host-RAM |
|---|---|---|
| get_all (SQLite/PG) | memory_client.py:532-556 / postgres_store.py:969-993 | 7,3–8,5 GB (7,05 GB @32 B; 7,93 GB @36 B + dicts) |
| _ensure_hnsw (jeder Aufruf, auch inkrementell) | memory_client.py:2130-2172 | 9–11,5 GB (get_all + 0,88 GB asarray + ~0,97 GB hnswlib); Messfamilie 12,3/12,9 GB |
| _semantic_candidates Brute-Force | memory_client.py:3048 | ~8,5 GB |
| _load_from_store unarmiert | memory_client.py:1927/1930 | 14–16 GB (7–8 transient + 7–8 retiniert in _graph_nodes); gemessen 10,4–12,9 GB steady |
| _load_from_store armiert | memory_client.py:1927 | ~0,5–1 GB ✓ geheilt |
| GPU-Arm-Fallback SQLite | gpu_recall.py:260-320 | ~9–9,5 GB (get_all + torch.as_tensor CPU + stack) |
| GPU-Arm PG-Streaming | gpu_recall.py:186-257 + postgres_store.py:1009 | ~1,1–2 GB ✓ geheilt (gemessen 1,07 GB) |
| GPU-Arm np.load-Cache | gpu_recall.py:93-146 | ~1,8 GB ✓ (aber stale-gefährdet: Fingerprint memory_client.py:1651-1675) |
| build_gpu_cache | build_gpu_cache.py:26-92 | ~2,5–3 GB (fetchall Roh-BLOBs + np.frombuffer, KEIN Python-Float, aber nicht gechunkt) |
| DAE-CPU | dae.py:671-676 | ~8,7–9,5 GB; Kommentar: "chunk on >100k corpora is future work" |

## Git-Einführung (K2)

- `_ensure_hnsw`-get_all: **717589b** (2026-04-30, "Mazemaker V3.1 — full release squash (126 commits → 1)").
  git blame auf :2130 zeigt bis HEAD b415570 weiterhin 717589b → von ALLEN 2026-08-07-Fixes unberührt.
- GPU-Arm-Fallback-get_all: **1e0d590** (2026-05-18, "engine: GPU recall cache cross-DB fix + DAE writes + ColBERT bake") — der 12,3-GB-Pfad war vor a906fe7 nachweislich drin: `git show a906fe7^:python/gpu_recall.py` zeigt get_all() + `.to_list()`/`np.asarray` + `vecs`-Liste + `torch.tensor(arr)`.
- DAE-get_all: **6046063c** (2026-05-21).
- Fix-Kette 2026-08-07: **a906fe7** 06:40 "stream the GPU arm..." (dokumentiert 7 Kernel-OOM-Kills, mcp-Spike 2026-07-21) → **38a0efc** 10:31 "decode the corpus ON the GPU" (gemessen vor 12,3 GB / nach 1,07 GB Peak) → **52e8e15** 10:52 "decouple recall server from embed server" → **94cdc80** 21:12 "stop holding the whole corpus as Python objects — 12.9 GB to 1.43 GB".
- **"1f1beb1" existiert in KEINEM der beiden Repos** (`git rev-list --all | grep` = 0 Treffer) — korrekt ist 38a0efc.

## Chunking-Infrastruktur (K3)

- `fetchmany`: **0 Vorkommen** in mazemaker-pro/python. Kein yield-per-row-, kein page-, kein chunk-Primitiv in SQLiteStore.
- `iter_for_gpu_arm`: nur postgres_store.py:1009; einziger Konsument gpu_recall.py:186 (getattr).
- SQLite fehlen `search_semantic` (nur PG :896) und `count_all` (nur PG :1084); `get_many` (memory_client.py:622) ist id-gebunden, nur für den 2000er-Top-up in _load_from_store.
- SQLite-Streams `stream_missing_colbert` (:807) / `stream_long_memories_for_afe` (:825) sind KEINE Vektor-Streams.
- Chunking-Fix-Rechnung: Keyset-Pagination à la PG (4096 Zeilen, 16,8 MB/Chunk Rohbytes, on-device-Decode) ⇒ Host-Peak ≈ Baseline 1–2 GB + 17 MB + GPU-Tensor 0,88 GB ⇒ **~2–3 GB statt 12,9 GB**. Das Muster existiert (PG-Arm + np.frombuffer in build_gpu_cache), ist aber nicht auf SQLite übertragen.
