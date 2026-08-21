# Silent-Degradation Map — mazemaker-pro (verified 2026-08-07, THESE B audit)

Session outcome: THESIS B **bestätigt** — ≥5 stille Degradationsmodi nachweisbar. Alle Zeilenangaben aus HEAD (b415570, 2026-08-07). READ-ONLY-Audit; nichts verändert.

## Degradations-Karte (6+ Modi)

| # | Modus | Auslöser | Log-Level | Seit-Commit |
|---|-------|----------|-----------|-------------|
| 1 | GPU→CPU-Fallback Recall | `torch.cuda.is_available()==False` → `self._device=torch.device("cpu")` in `gpu_recall.py:110-113` (auch `load_from_store` :171-174) | **SILENT** am Selektionsort; danach irreführend `INFO "GPU recall ARMED ... on %s"` (`memory_client.py:1696-1699`, device=cpu) | `73462ff` (erstes GPU-Engine-Sync); Init-Pfad erst seit 2026-08-05-Rework laut (vorher: CUDA-OOM → WARN → numpy für Prozesslebensdauer, siehe Kommentar `memory_client.py:1741-1745`) |
| 1b | Remote-Recall tot | Socket/Server weg → `RemoteGpuRecallClient.recall` → `return []` (`embed_provider.py:630-642`); `recall_batch` → `[[],...]` (:644-656); semantic-Kanal wird leer, Fusion läuft mit Restkanälen weiter | **SILENT** | `a4e587f` 2026-05-08 (EMBED_CLIENT_ONLY-Architektur) |
| 1c | recall_batch GPU-Fehler | `except Exception: pass` in `memory_client.py:3322-3323` → per-Query-Recall | **SILENT** | alt (recall_batch-Einführung) |
| 2 | ColBERT-Kanal inert | Kanal „an" (advanced/hybrid weight 0.5, skynet 1.2 — `memory_client.py:1490-1496`), aber Blobs nie geschrieben (MM_COLBERT_ENABLED=0 Default) → `_colbert_score_candidates` gibt bei **jedem** Fehler/leerem Blob-Bestand `{}` zurück ohne Log (`memory_client.py:3258-3300`: Import-Fehler, fetch-Fehler, leere Blobs, encode-Fehler, keine docs — alle still) | **SILENT** (einzige Meldung: `MM_COLBERT_ENABLED=1 ignored — Pro feature` WARN :1524-1527) | `6452a0d` 2026-05-10 (Kanal), `e471436` 2026-05-10 (has_feature-Gate) |
| 2b | DAE-Recall-Kanal strukturell AUS | `channel_weights["dae"]=0.0` auf ALLEN Presets (`memory_client.py:1501-1502`); Standard-Tool `_handle_recall` (`__init__.py:1339-1353`) übergibt weder `enable_dae` noch `dae_weight` — nur `mazemaker_recall_advanced` exponiert die Knöpfe (`__init__.py:1374-1418`); compute.toml `dae_weight=1.0` ist tot; `dae.py:864-866` `wired_to_recall=False`; „channel intentionally unwired pending bench validation" (`dae.py:875`) | **1× INFO** bei Modul-Import, danach still | `108bc06` 2026-05-10 (Scaffold); Compute schreibt seit `1e0d590` 2026-05-18 Rows, Recall konsumiert nie |
| 3 | 3-Slice-Sampling tot (PG) | **HEUTE GEFIXT**: `DreamPostgresStore.sample_for_dream` 3-Slice-Mix existiert (`dream_postgres_store.py:1012-1072`, seit `afec238` 2026-05-07). Historisch: PG nutzte Base-Default → nur recent. RESTRISIKO: `DreamBackend`-Defaults degradieren weiter still — `sample_for_dream` → `get_recent_memories` (`dream_engine.py:201-203`), `get_memory_vectors` → `{}` (:299-301), `get_memory_metadata` → `{}` (:303-312) → supersedes no-op; PG-Vektor-Parsing-Fix erst `a354383` 2026-07-10 | SILENT by design | `afec238` 2026-05-07 |
| 4 | Supersedes-Gate feuert nie | **Ära 1:** PG-Writer fehlte bis `24da5ab` 2026-08-06 → pro Zyklus `pairs_checked~17000, supersedes_found=0` — liest sich als „nichts gefunden", Wahrheit: Writer war tot (AttributeError verschluckt, Kommentar `dream_postgres_store.py:688-694`). **Ära 2:** nach Writer-Fix Explosion 25k→515k Edges in 90 min (`eab7a9f` 2026-08-06) → Gate auf curated-Labels beschränkt (`MAZEMAKER_SUPERSEDES_CURATED_ONLY=1`, `_CURATED_LABEL_RE` `dream_engine.py:37-39`); auf 98%-Autosave-Korpus (5477/214983 curated+Ziffer) ~51 Kandidaten/Sample → feuert praktisch nie | still (Stats-dict falsch lesbar) | `24da5ab`/`eab7a9f` 2026-08-06 |
| 5 | ef_search/Channel-Weights ignoriert | SQLite-HNSW: `ef_construction=200, M=16, set_ef(64)` **hartkodiert** (`memory_client.py:2170-2173`) — kein Knopf; PG-Fix `3215f95` 2026-05-21 bewies 40→500 nötig bei 200k → SQLite-Pfad hat denselben stillen Top-K-Verlust. **Hauptbefund:** compute.toml `[recall]`/`[recall_advanced]` (mode, rerank, colbert_weight 1.5, dae_weight 1.0, candidates_n 512, multi_query, use_hnsw) wird von KEINEM Code gelesen — `compute_config.py` behandelt nur `[dream]`/`[afe]` | SILENT | `3215f95` 2026-05-21 (nur PG), `02fda91` 2026-08-07 (compute.toml-Doku beansprucht „single source of truth") |
| 6 | Rerank fail-closed | advanced/skynet auto-promoten `rerank=True` (`memory_client.py:3857-3861`); CrossEncoder-Load-Fehler → `_reranker_failed=True` OHNE Log (`memory_client.py:3137-3146`); `_rerank_results` gibt still ungerankt zurück (:3160-3162, :3167-3171) | **SILENT** | `6452a0d` 2026-05-10 |
| 7 | `_semantic_candidates`-Kaskade | PG search_semantic→GPU→HNSW→C++→Brute-Force `get_all()`; jeder Fehler `except Exception: pass` (`memory_client.py:2994-3052`) — bei kaputtem/fehlendem PG-HNSW still 75 s/Query (Kommentar :2990-2993) | **SILENT** | `aa9f2ab` 2026-05-17 / `d24a576` 2026-08-06 |

## K2 — Qualitäts-Knöpfe: angenommen aber ignoriert (Dead-Knob-Inventar)

| Knopf | Quelle | Status |
|---|---|---|
| `[recall].mode` (=advanced), `[recall_advanced].rerank/colbert_weight/dae_weight/candidates_n/multi_query/use_hnsw` | compute.toml | **TOT** — kein Leser (nur mcp_schemas-Doku + `_handle_recall_advanced` per-call-kwargs existieren) |
| `[compute].device/strict`, `[embeddings]`, `[storage]`, `[resources]`, `[vault]` | compute.toml | **TOT** — kein Leser |
| `MM_DAE_ENABLED`, `MM_NREM_ENABLED`, `MM_REM_ENABLED`, `MM_INSIGHT_ENABLED`, `MAZEMAKER_AFE_ENABLED`, `MAZEMAKER_SYNTHESIS_ENABLED`, `MAZEMAKER_DERIVED_CLUSTER_TTL_S` | env | **LEGACY/inert** — `warn_ignored_env()` meldet 1× (seit 02fda91/b415570 2026-08-07) |
| `dae_weight`/`enable_dae` | recall-Aufruf | nur via `mazemaker_recall_advanced` erreichbar; Standard-Recall (Hermes/Claude) erreicht DAE-Kanal nie |
| `ef_search` | SQLite-HNSW | kein Knopf; hartkodiert 64 (PG: `MM_HNSW_EF_SEARCH` wirkt, Default 500) |
| `colbert_weight>0` (0.5 advanced / 1.2 skynet) | channel_weights | wirkt nur wenn Blobs existieren; Blob-Write braucht separat `MM_COLBERT_ENABLED=1` AND `has_feature("colbert")` |
| rerank (config.yaml) | config | auto-True in advanced/skynet; fail-closed still bei Load-Fehler |

## K3 — Benchmark-Bedingungen (publiziert vs. Normalbetrieb)

- **R@5=0.8426 / R@10=0.9000** (LongMemEval-oracle Champion, iter100; Bundle `mazemaker-claims-2026-05-19.tar`, Engine HEAD ead3fe7): iter95-JSON `config = {recall_mode: skynet, rerank: true, colbert: true, dae: true, dream: false, limit: 500, sessions_ingested: 25964}` — PG-Backend, p50 1728 ms / p95 3261 ms.
- **LongMemEval-S R@5=0.9787 / R@1=0.8574 / MRR=0.9114**: hybrid + ColBERT@1.5, ephemeraler Harness (pro Frage frischer Engine-State), 470/500 gradeable.
- **skynet R@5=0.9000** (Anchor-Paraphrase-Suite, README:188): Kanal-Defaults semantic 1.0 / bm25 0.9 / entity 1.0 / temporal 0.35 / ppr 0.55 / salience 0.25, p50 339.9 ms („200× latency, recovers most recall").
- **lean R@5=0.60 > skynet 0.42** auf Realprosa (n=200, run-2026-04-28-v7-realistic); Kanal-Ablation: PPR load-bearing (ΔMRR −0.12), salience null/schädlich.
- **EverMemBench**: keine Zahlen im Repo; nur extern referenziert (PG-Normalisierer-Bug, `postgres_store.py:1884`, gefunden 2026-07-03).
- **Normalbetrieb heute**: dream-worker `--retrieval-mode hybrid` (CLI-Default `dream_worker.py:183`), think ppr; mcp/plugin advanced NUR wenn `config.yaml memory.neural.retrieval_mode` gesetzt (hier: keine neural-Sektion → **semantic**); ColBERT nur bei env; **DAE-Recall-Kanal aus**; GPU via kanonischem Worker + thin Clients (`EMBED_CLIENT_ONLY`).
- **Konsequenz:** kein publizierter Wert ist unter Normalbetrieb reproduzierbar (Champion-Konfig skynet+colbert+dae+rerank existiert in Produktion nicht).

## Befund-Muster (was die Stille ausmacht)

1. Nur 2 von 205 `except`-Stellen in den 6 Kerndateien sind wörtlich `pass`-stumm (`embed_provider.py:527,1749`) — Zählen von excepts ist ein schwaches Signal.
2. Stille sitzt in `return {}`/`return []`-Pfaden: ColBERT/DAE-Scorer, Remote-Proxies, Reranker, `add_one` no-op (`gpu_recall.py:340-341`).
3. Log-Level-Täuschung: „ARMED ... on cpu" = INFO; `supersedes_found: 0` liest sich falsch; `wired_to_recall: False` nur in Stats-Endpoint.
4. Fix-Commits erzeugen neue stille Modi (supersedes curated-only-Gate nach Firehose).
