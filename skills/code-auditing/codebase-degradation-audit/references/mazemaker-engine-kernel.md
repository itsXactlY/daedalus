# Mazemaker Engine Kernel Audit — 2026-08-07

Repo: /home/alca/projects/mazemaker-pro (master @ b415570, 430 commits)
Older fork: /home/alca/projects/mazemaker ("Mazemaker Community — free edition", diverged at 7be1904)
Corpus at audit: ~215,132 memories, dim 1024, MM_DB_BACKEND=postgres
Pod was DOWN at audit time (only mazemaker.target active) — all measurements come from code comments and commit bodies.

## Architecture (3 layers)
hermes-agent → MemoryProvider (python/__init__.py) → Memory (mazemaker.py) → store (SQLiteStore/PG) + GpuRecallEngine (gpu_recall.py) + DreamEngine (dream_engine.py, 7 phases: NREM→SUPERSEDES→REM→Insight→AFE→Synthesis→DAE).
Embedding: SharedEmbedServer on UNIX socket (~/.mazemaker/engine/embed.sock). Since 2026-08-07 the dream_worker publishes a recall-only server (52e8e15); mcp/wonderland are thin clients (EMBED_CLIENT_ONLY=1, EMBED_BACKEND=http).

## Bottleneck ranking @215k (top 10)
1. DAE bulk compute — O(n·K) + 215k-row upsert; **193.7 s/run, every 5 cycles** — dream_engine.py:2912, dae.py:601
2. get_all() with vectors — O(n), 7.05 GB transient Python floats — postgres_store.py:969, memory_client.py:532
3. GPU-arm fallback (no iter_for_gpu_arm = SQLite/community) — 12.3 GB peak — gpu_recall.py:259–331
4. _ensure_hnsw rebuild — O(n log n): get_all + np.asarray + index ≈ 11–12 GB, minutes — memory_client.py:2130, 2171
5. NREM think_ids loop — 2000 × 20-iter GPU sparse PPR (~2M nnz) ≈ 16 s/cycle — dream_engine.py:1699, memory_client.py:4308
6. REM recall_batch — 800 queries × 1024×215k matmul ≈ 12 s/cycle — dream_engine.py:2199
7. _semantic_candidates brute force — get_all + Python cosine: **75 s (PG) / 57.8 s (CPU-numpy)** — memory_client.py:3047–3052
8. Supersedes ingest — O(window=2000) pure-Python cosine per remember — memory_client.py:2488–2508
9. ColBERT rerank (weight 0.5 active in advanced/hybrid presets) — memory_client.py:3242, colbert_helper.py:422
10. Hybrid recall full chain ≈ 0.7–1.4 s/angle — memory_client.py:3616–3779

## Silent-degradation map (key entries)
- GPU→CPU tensor: `torch.cuda.is_available()==False`, NO log — gpu_recall.py:110, since 73462ff (2026-04-20)
- GPU→numpy brute force: arm failure; warning "*** RECALL NOW RUNS ON CPU/NUMPY ***" since afbcbc0 (08-05); was silent before (aa9f2ab, 05-17)
- hnswlib missing → get_all brute force: NO log — since 717589b (04-30)
- `except: pass` after GPU recall call: NO log — memory_client.py:3018
- ColBERT numpy fallback: silent (except: pass) — colbert_helper.py:462; model-load failures log warning
- DAE numpy fallback: DEBUG only — dae.py:312 (debug doesn't count)
- EMBED_BACKEND=http silently ignored → second bge-m3 loaded — fixed d8fa3d6 (08-07)
- FTS index 'simple' vs query 'english' → 6.5 s seq-scan vs 95 ms — fixed 5d637e9 (08-07)
- Supersedes writer on PG was DEAD until 24da5ab (08-06): stats lied ("pairs_checked 17708, found 0"); then firehose 25k→515k edges in 90 min → curated-only gate eab7a9f
- GPU-cache fingerprint check was a permanent no-op (`.conn` absent on PG) — memory_client.py:1656–1661, since 751bcf7
- NREM dead-man switch (a90528b, 07-09): pgvector API change deleted a 1M-edge graph in <1 day before it existed

## Config lies (keys read by ZERO code — verified by grep)
- compute.toml `[recall].mode=advanced` and `[recall_advanced].{colbert_enabled, colbert_weight=1.5, dae_weight=1.0, candidates_n=512, ...}`
- `MM_RETRIEVAL_MODE=hybrid` (set in mcp.container) — read by no python file
- `MAZEMAKER_DAE_WEIGHT` / `MAZEMAKER_COLBERT_WEIGHT` (runtime.env) — only per-call MCP tool kwargs, no defaults (__init__.py:1386–1412)
- `NEURAL_MEMORY_RETRIEVAL_MODE` — only read by ingest_pulse.py
- REAL modes: dream_worker default "hybrid" (dream_worker.py:187), mcp = "semantic" (config.py:32 default; hermes config.yaml has no memory.neural section)
- Consequence: no cross-encoder rerank, no PPR, no BM25 fusion in mcp; ColBERT channel weight 0.5 in advanced/hybrid, 0.0 in semantic
- hnswlib `set_ef(64)` (memory_client.py:2173) vs PG `hnsw.ef_search=500` (postgres_store.py:313) — CPU index silently misses top-K

## get_all() cost math @215,132
- PG wire bytes: 0.88 GB raw → `_vec_to_list`/`.to_list()` → list[float]: 215,132×1024×32 B = **7.05 GB**; dicts+strings ≈ 0.3–0.6 GB; np.asarray 0.88 GB; torch tensor 0.88 GB; hnswlib 2.5–4 GB; _graph_nodes retention 7.05 GB
- Old arm peak **12.3 GB** (7 kernel OOM kills 2026-08-07); graph steady state 12.9 GB (systemd-oomd kills at 12.7–12.9, OOMScoreAdjust=500, container cap 16g, host 31g)
- Streaming arm (PG ONLY): `iter_for_gpu_arm` postgres_store.py:1009 — raw wire bytes, 16 MB/chunk, GPU decodes via `view(-1,4).flip(-1)` (38a0efc: 12.3 GB → 1.07 GB peak, 6.3 s)
- SQLite has NO iter_for_gpu_arm → gpu_recall.py:259 fallback still materialises 7–12.3 GB (community edition too)
- `_load_from_store` (94cdc80, 08-07): `get_all(include_embeddings=not _armed)` + `get_many` top-up for last 2000 ids → steady state 1.43 GB

## Git timeline of degradation (mazemaker-pro)
- 8773f3c 04-09: initial commit — get_all brute force in recall
- 73462ff 04-20: GPU recall engine (numpy cache path np.load→torch)
- 717589b 04-30: V3.1 squash — _ensure_hnsw (ef=64), brute-force fallback remains
- a4e587f 05-08: socket remote recall ("one canonical engine")
- 108bc06/6452a0d 05-10: DAE scaffold (unwired) + ColBERT channel
- aa9f2ab 05-17: DAE phase wired into dream cycle + CPU/numpy warning
- 1e0d590 05-18: **load_from_store via get_all() — the 12.3-GB path, live until 08-07**
- 0c4ed60 06-03: DAE store-unwrap fix → DAE actually writes on PG (204,105 vectors) → production-active
- 1e7fe70/2584039/a90528b 07-09: pgvector Vector compat + NREM dead-man switch
- 08-04 (operator drop-in): dae-off.conf MM_DAE_ENABLED=0 (after 193.7 s/249.3 s cycle, OOM restart 23)
- afbcbc0/a2e7b9b 08-05: third device-selection site + GPU-first resolution
- 24da5ab/ba0704a/eab7a9f 08-06: PG supersedes writer + curated-only gate; dae-off.conf → `.disabled-20260806` (DAE re-enabled)
- a906fe7/38a0efc 08-07: streaming arm + GPU decode (12.3 → 1.07 GB)
- 52e8e15/abc6df2 08-07: recall server decoupled from embed server; neighbours_by_vector over socket
- 94cdc80 08-07: graph load without vectors (12.9 → 1.43 GB)
- 5d637e9/38a1848/1f895f1 08-07: FTS index fix, 3M audit rows/day stopped, HOT-update indexes
- 02fda91/b415570 08-07: compute.toml single source of truth — but only [dream]/[afe] wired; [recall] section remains dead

## DAE analysis
- Config chain: JWT compute claim → license-client → ~/.mazemaker/compute.toml → mounted into containers → `compute_config.flag("dream","dae_enabled")` → `_phase_dae` (dream_engine.py:2936)
- [dream].dae_enabled=true, dae_recompute_every=5; runtime.env MM_DAE_ENABLED now inert (warn_ignored_env)
- Active: 06-03→08-04, then 08-06→now (drop-in neutralised by rename)
- Cost: 193.7 s per run every ~25 min; full-corpus upsert (fillfactor 70, dae.py:124)
- **Recall channel DEAD**: channel weight 0.0 (memory_client.py:1501–1502), `wired_to_recall: False` (dae.py:865); compute.toml dae_weight=1.0 read by no code

## Cross-repo divergence
- Community repo (mazemaker): NO gpu_recall.py, colbert_helper.py, dae.py, postgres_store.py, dream_postgres_store.py
- memory_client.py: 275 diff lines (pro: include_embeddings flag, streaming arm, neighbours_by_vector, _load_from_store top-up); dream_engine.py: 1669 lines
- Same commit messages, different hashes (a9e5673 vs afbcbc0; d32b48b vs 8ebfe6a) = asymmetric cherry-picks
- Community keeps the 7–12.3 GB get_all path and 75 s brute force — perf fixes are pro-only
- Deployment: mazemaker-pro via install.sh → local images (localhost/mazemaker-v2-*:latest/gpu); community repo is source distribution only

## Operator artifacts
- `~/.mazemaker/dropin-backup-20260807-222412.tar.gz` contains dae-off.conf.disabled-20260806, colbert.conf, memory-16g.conf — extract to /tmp to read
- `~/.config/containers/systemd/`: mazemaker.pod; mazemaker-dream-worker.container (16g cap, MemoryHigh=12G, OOMScoreAdjust=500, StopTimeout=150, BindsTo=mazemaker-dream.target); mazemaker-mcp.container (MemoryMax=4G since thin-client 08-07; was 16G); mazemaker-embedding-worker.container (MemoryMax=3G)
- compute.toml + runtime.env + db.env in ~/.mazemaker/ (generated by license-client from JWT compute claim)
- Key env on pods: MM_COLBERT_ENABLED=1 (both), MM_DREAM_DISABLED=1 (mcp), MAZEMAKER_AFE_LLM_FALLBACK=0 (dream-worker, nightly window sets 1)
